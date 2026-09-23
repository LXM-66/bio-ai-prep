"""从 UniProt 取蛋白条目（功能注释、所属物种、关键词）→ rag/data/uniprot.jsonl

UniProt 的 REST 接口不需要 key，只要求礼貌调用（别并发打、出错退避重试）。

用法：
    python rag/fetch_uniprot.py                       # 默认取 40 条人工审阅的肿瘤相关蛋白
    python rag/fetch_uniprot.py 30 "gene:TP53"
    python rag/fetch_uniprot.py 20 "keyword:apoptosis AND organism_id:9606"
"""

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

API = "https://rest.uniprot.org/uniprotkb/search"
OUT = Path(__file__).resolve().parent / "data" / "uniprot.jsonl"
DEFAULT_QUERY = "reviewed:true AND organism_id:9606 AND (keyword:cancer OR keyword:apoptosis)"
FIELDS = "accession,id,protein_name,organism_name,keyword,cc_function"


def fetch(url: str, tries: int = 3) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "bio-ai-prep/1.0 (learning project)"})
    for attempt in range(1, tries + 1):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read()
        except Exception as exc:
            if attempt == tries:
                raise
            print(f"  [重试 {attempt}/{tries - 1}] {exc}")
            time.sleep(3 * attempt)
    return b""


def parse(entries: list[dict]) -> list[dict]:
    """UniProt API 的返回 → 本仓库的原生字段（由 corpus.py 归一化）。"""
    out: list[dict] = []
    for e in entries:
        acc = e.get("primaryAccession", "")
        prot = (e.get("proteinDescription", {}).get("recommendedName", {}) or {}).get("fullName", {})
        name = prot.get("value", "") or e.get("uniProtkbId", "")
        genes = "/".join(g.get("geneName", {}).get("value", "") for g in e.get("genes", []) if g.get("geneName"))
        organism = (e.get("organism") or {}).get("scientificName", "")
        keywords = [k.get("name", "") for k in e.get("keywords", [])][:8]
        function = ""
        for comment in e.get("comments", []):
            if comment.get("commentType") == "FUNCTION":
                texts = comment.get("texts", [])
                if texts:
                    function = texts[0].get("value", "")
                    break
        if not function:
            continue                                     # 没有功能注释的条目对问答没价值
        out.append({"accession": acc, "protein": name, "gene": genes, "organism": organism,
                    "function": function, "keywords": keywords,
                    "length": (e.get("sequence") or {}).get("length", "")})
    return out


def dump(rows: list[dict], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("limit", nargs="?", type=int, default=40)
    ap.add_argument("query", nargs="?", default=DEFAULT_QUERY)
    args = ap.parse_args()

    url = API + "?" + urllib.parse.urlencode(
        {"query": args.query, "format": "json", "size": min(args.limit, 100), "fields": FIELDS})
    data = json.loads(fetch(url).decode("utf-8"))
    entries = data.get("results", [])
    total = data.get("totalResults")
    total_txt = f"{int(total):,}" if str(total).isdigit() else "?"
    print(f"命中 {total_txt} 条，本次取 {len(entries)} 条")

    rows = parse(entries)
    dump(rows, OUT)
    print(f"写入 {OUT}（{len(rows)} 条｜{OUT.stat().st_size / 1024:.0f} KB）")
    print("示例：" + "；".join(f"{r['accession']} {r['gene']} {r['protein']}" for r in rows[:3]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
