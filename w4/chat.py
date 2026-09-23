"""W4：命令行对话脚本 —— 多轮上下文 + 流式输出 + 每次调用的 Token 与花费。

用法：
    python w4/chat.py                      # 交互式（输入 /exit 退出）
    echo "用一句话解释什么是 RAG" | python w4/chat.py     # 管道输入也行

脚本内命令：
    /cost    本次会话累计花了多少
    /reset   清空上下文（重新开始聊）
    /exit    退出

API key 来源（按顺序找）：环境变量 DEEPSEEK_API_KEY → 仓库根目录的 .env 文件。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from llm import DeepSeek, DeepSeekError, is_peak  # noqa: E402

SYSTEM = ("你是生物医药领域的助手。回答简洁准确，涉及专业概念时给一句通俗解释，"
          "不确定的地方要说明不确定。")

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def load_env():
    """把 .env 里的 KEY=VALUE 读进环境变量（已存在的环境变量优先）。"""
    import os
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def main():
    load_env()
    try:
        bot = DeepSeek(model="deepseek-flash")
    except DeepSeekError as e:
        print(f"启动失败：{e}")
        return 1

    messages = [{"role": "system", "content": SYSTEM}]
    total_cost = 0.0
    turns = 0
    print(f"模型 {bot.model}｜当前是{'高峰' if is_peak() else '空闲'}时段"
          f"（空闲时段价格减半）｜输入 /cost /reset /exit")

    while True:
        try:
            user = input("\n你> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user:
            continue
        if user in ("/exit", "/quit"):
            break
        if user == "/reset":
            messages = [{"role": "system", "content": SYSTEM}]
            print("上下文已清空")
            continue
        if user == "/cost":
            print(f"本次会话：{turns} 轮，累计 {total_cost:.6f} 元")
            continue

        messages.append({"role": "user", "content": user})
        print("AI> ", end="", flush=True)
        try:
            reply = ""
            for piece in bot.stream(messages):
                reply += piece
                print(piece, end="", flush=True)
        except DeepSeekError as e:
            print(f"\n[调用失败] {e}")
            messages.pop()                    # 失败的那轮不进上下文，避免污染
            continue

        print()
        u = bot.last_usage
        total_cost += u["cost_cny"]
        turns += 1
        print(f"    ↑ {u['prompt_tokens']} + {u['completion_tokens']} tokens"
              f"（缓存命中 {u['cache_hit_tokens']}）｜{u['seconds']}s｜{u['cost_cny']:.6f} 元")
        messages.append({"role": "assistant", "content": reply})

    if turns:
        print(f"\n本次对话 {turns} 轮，合计 {total_cost:.6f} 元（明细已记到 w4/logs/usage.csv）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
