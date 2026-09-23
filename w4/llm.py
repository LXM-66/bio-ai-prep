"""DeepSeek API 的最小可用封装：流式输出 / 超时 / 重试 / Token 与成本统计。

只用标准库（urllib、json），不引第三方 SDK —— 这样能看清 HTTP 和 SSE 到底发生了什么。
配合 `w4/chat.py` 使用，后续 W5 的 RAG 原型也直接复用它。

用法：
    from llm import DeepSeek

    bot = DeepSeek()                        # 自动读环境变量 DEEPSEEK_API_KEY
    for piece in bot.stream([{"role": "user", "content": "你好"}]):
        print(piece, end="", flush=True)
    print(bot.last_usage)                   # 本次的 token 与花费
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-flash"            # 旧名 deepseek-v4-flash 也能调用
LOG = Path(__file__).resolve().parent / "logs" / "usage.csv"
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def load_env(path: Path | None = None) -> None:
    """把 .env 里的 KEY=VALUE 读进环境变量（已存在的环境变量优先）。"""
    path = path or ENV_FILE
    if not Path(path).exists():
        return
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())

# 官方价目表（元 / 百万 tokens）
# 来源：https://api-docs.deepseek.com/zh-cn/quick_start/pricing
PRICES = {
    "deepseek-flash":  {"cache_hit": 0.02, "cache_miss": 1.0, "output": 4.0},
    "deepseek-v4-pro": {"cache_hit": 0.15, "cache_miss": 4.5, "output": 13.5},
}
# 高峰期：周一至周五 9:00–12:00、14:00–18:00（北京时间）；其余时段价格减半
PEAK_HOURS = ((9, 12), (14, 18))


def is_peak(when: datetime | None = None) -> bool:
    """现在是高峰时段吗（法定节假日这里不判，简化处理）。"""
    when = when or datetime.now()
    return when.weekday() < 5 and any(start <= when.hour < end for start, end in PEAK_HOURS)


class DeepSeekError(RuntimeError):
    """请求彻底失败（重试用尽）时抛出。"""


class DeepSeek:
    """一次实例 = 一个模型配置；`last_usage` 保存最近一次的 token 与花费。"""

    def __init__(self, api_key: str | None = None, model: str = DEFAULT_MODEL,
                 base_url: str = BASE_URL, timeout: int = 60, max_retries: int = 3):
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        if not self.api_key:
            raise DeepSeekError("没有 API key：设环境变量 DEEPSEEK_API_KEY，或在仓库根建 .env 文件")
        if model not in PRICES:
            raise DeepSeekError(f"未知模型 {model}，已知：{list(PRICES)}")
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.last_usage: dict | None = None

    # ── 内部：带重试的请求 ───────────────────────────────────────────────
    def _open(self, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.api_key}"},
            method="POST",
        )
        last_err = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return urllib.request.urlopen(req, timeout=self.timeout)
            except urllib.error.HTTPError as e:            # 4xx/5xx
                detail = e.read().decode("utf-8", "ignore")[:200]
                last_err = f"HTTP {e.code}: {detail}"
                if e.code < 500 and e.code != 429:         # 参数错、key 错 —— 重试没意义
                    raise DeepSeekError(last_err) from e
            except Exception as e:                         # 超时、断网、DNS
                last_err = f"{type(e).__name__}: {e}"

            wait = 2 ** (attempt - 1)                      # 1s → 2s → 4s
            if attempt < self.max_retries:
                print(f"  [重试 {attempt}/{self.max_retries - 1}] {last_err} —— {wait}s 后再试")
                time.sleep(wait)
        raise DeepSeekError(f"重试 {self.max_retries} 次仍失败：{last_err}")

    # ── 计价 ────────────────────────────────────────────────────────────
    def _cost(self, usage: dict, peak: bool) -> float:
        price = PRICES[self.model]
        hit = usage.get("prompt_cache_hit_tokens") or 0
        miss = usage.get("prompt_cache_miss_tokens")
        if miss is None:                                   # 有些响应只给总数
            miss = max((usage.get("prompt_tokens") or 0) - hit, 0)
        out = usage.get("completion_tokens") or 0
        discount = 1.0 if peak else 0.5                    # 空闲时段半价
        return (hit / 1e6 * price["cache_hit"]
                + miss / 1e6 * price["cache_miss"]
                + out / 1e6 * price["output"]) * discount

    def _record(self, usage: dict, peak: bool, elapsed: float):
        cost = self._cost(usage, peak)
        self.last_usage = {
            "model": self.model,
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "cache_hit_tokens": usage.get("prompt_cache_hit_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "peak": peak,
            "cost_cny": round(cost, 6),
            "seconds": round(elapsed, 2),
        }
        LOG.parent.mkdir(parents=True, exist_ok=True)
        new = not LOG.exists()
        with LOG.open("a", newline="", encoding="utf-8") as f:
            import csv
            w = csv.writer(f)
            if new:
                w.writerow(["ts", "model", "prompt_tokens", "cache_hit_tokens",
                            "completion_tokens", "peak", "cost_cny", "seconds"])
            w.writerow([datetime.now().isoformat(timespec="seconds"), self.model,
                        self.last_usage["prompt_tokens"], self.last_usage["cache_hit_tokens"],
                        self.last_usage["completion_tokens"], peak,
                        self.last_usage["cost_cny"], self.last_usage["seconds"]])
        return self.last_usage

    # ── 对外：流式 / 一次性 ─────────────────────────────────────────────
    def stream(self, messages: list[dict], temperature: float = 0.3, **kw):
        """逐段产出文本（生成器）；跑完后 `last_usage` 就是这次的花费。"""
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},   # 让最后一个包带上用量
            "temperature": temperature,
            **kw,
        }
        peak, start, usage = is_peak(), time.time(), {}
        resp = self._open(payload)

        for raw in resp:                                  # SSE：一行一个 data: {...}
            line = raw.decode("utf-8", "ignore").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
            except json.JSONDecodeError:
                continue
            if chunk.get("usage"):
                usage = chunk["usage"]
            for choice in chunk.get("choices") or []:
                piece = (choice.get("delta") or {}).get("content")
                if piece:
                    yield piece

        self._record(usage, peak, time.time() - start)

    def chat(self, messages: list[dict], **kw) -> str:
        """一次性拿完整回复（内部仍是流式，只是帮你拼好）。"""
        return "".join(self.stream(messages, **kw))
