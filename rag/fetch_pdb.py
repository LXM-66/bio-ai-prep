"""从 RCSB PDB 取蛋白结构条目（标题、实验方法、分辨率、配体、引用）→ rag/data/pdb.jsonl

先按关键词做全文检索拿到 PDB ID 列表，再逐个取条目元数据。
RCSB 的检索接口是 POST JSON，不需要 key。

用法：
    python rag/fetch_pdb.py                          # 默认查 "tumor suppressor" 取 20 个结构
    python rag/fetch_pdb.py 15 "single-cell RNA sequencing"
    python rag/fetch_pdb.py 10 "CRISPR Cas9"
"""

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

SEARCH = "https://search.rcsb.org/rcsbsearch/v2/query"
ENTRY = "https://data.rcsb.org/rest/v1/core/entry/"
OUT = Path(__file__).resolve().parent / "data" / "pdb.jsonl"


def request(url: str, payload: dict | None = None, tries: int = 3) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json", "User-Agent": "bio-ai-prep/1.0"})
    for attempt in range(1, tries + 1):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            if attempt == tries:
                raise
            print(f"  [重试 {attempt}/{tries - 1}] {exc}")
            time.sleep(3 * attempt)
    return {}


def search_ids(query: str, limit: int) -> list[str]:
    payload = {"query": {"type": "terminal", "service": "full_text", "parameters": {"value": query}},
               "return_type": "entry",
               "request_options": {"paginate": {"start": 0, "rows": limit}}}
    result = request(SEARCH, payload)
    return [r["identifier"] for r in result.get("result_set", [])]


def one_entry(pdb_id: str) -> dict | None:
    d = request(ENTRY + pdb_id)
    if not d:
        return None
    title = (d.get("struct") or {}).get("title", "")
    method = next((m.get("method", "") for m in d.get("exptl", [])), "")
    res = (d.get("rcsb_entry_info") or {}).get("resolution_combined") or []
    res_txt = f"分辨率 {res[0]:.2f} Å" if res else "分辨率未标注"
    year = str((d.get("rcsb_accession_info") or {}).get("initial_release_date", ""))[:4]
    polymers = (d.get("rcsb_entry_info") or {}).get("polymer_entity_count", "?")
    ligands = (d.get("rcsb_entry_info") or {}).get("nonpolymer_entity_count", 0)
    citation = ((d.get("rcsb_primary_citation") or {}).get("title") or "")
    body = (f"实验方法：{method or '未知'}，{res_txt}；含 {polymers} 条聚合物链、{ligands} 个非聚合物配体。")
    if citation:
        body += f" 主要引用论文：{citation}。"
    if not title:
        return None
    return {"pdb_id": pdb_id, "title": title, "description": body, "method": method or "", "year": year}


def dump(rows: list[dict], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("limit", nargs="?", type=int, default=20)
    ap.add_argument("query", nargs="?", default="tumor suppressor")
    args = ap.parse_args()

    ids = search_ids(args.query, args.limit)
    print(f"检索「{args.query}」→ {len(ids)} 个结构")
    rows = []
    for i, pdb_id in enumerate(ids, 1):
        row = one_entry(pdb_id)
        if row:
            rows.append(row)
        time.sleep(0.2)                                  # 别把公共接口打急
        if i % 5 == 0:
            print(f"  已取 {i}/{len(ids)}")
    dump(rows, OUT)
    print(f"写入 {OUT}（{len(rows)} 条｜{OUT.stat().st_size / 1024:.0f} KB）")
    print("示例：" + "；".join(f"{r['pdb_id']} {r['title'][:50]}" for r in rows[:2]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
