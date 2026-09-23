"""从 NCBI 拉一批人类 RefSeq mRNA 记录，存成 CSV 供 pandas 分析（W2）。

用法：
    python w2/fetch_dataset.py            # 默认 500 条
    python w2/fetch_dataset.py 200

产物：
    w2/data/ncbi_raw.csv   原始表（故意不洗，留着给 pandas 练手）
"""

import csv
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
OUT = Path(__file__).resolve().parent / "data" / "ncbi_raw.csv"
QUERY = 'Homo sapiens[Organism] AND RefSeq[Filter] AND mRNA[Filter]'


def eutils(endpoint, **params):
    """调一个 E-utilities 接口，返回解析后的 JSON（网络抖动自动重试 3 次）。"""
    params.setdefault("retmode", "json")
    url = f"{EUTILS}/{endpoint}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "w2-learning-script"})
    for attempt in range(1, 4):
        try:
            return json.loads(urllib.request.urlopen(req, timeout=40).read().decode("utf-8"))
        except Exception as e:
            print(f"  第 {attempt} 次失败：{type(e).__name__}，重试…")
            if attempt == 3:
                raise
            time.sleep(3)


def search_ids(limit):
    """先问有多少条命中，再取前 limit 个编号。"""
    r = eutils("esearch.fcgi", db="nuccore", term=QUERY, retmax=0)
    total = int(r["esearchresult"]["count"])
    r = eutils("esearch.fcgi", db="nuccore", term=QUERY, retmax=limit, sort="pub date")
    print(f"命中 {total:,} 条，本次取 {limit} 条")
    return r["esearchresult"]["idlist"]


def summarize(ids):
    """拿一批编号换摘要信息（每 200 个一批，遵守 ≤3 次/秒的礼节）。"""
    out = []
    for i in range(0, len(ids), 200):
        chunk = ids[i:i + 200]
        r = eutils("esummary.fcgi", db="nuccore", id=",".join(chunk))
        out.extend(r["result"].values())
        time.sleep(0.4)
    return [x for x in out if isinstance(x, dict) and x.get("accessionversion")]


def gene_from_title(title):
    """从 "Homo sapiens tumor protein p53 (TP53), transcript variant 1, mRNA" 里抠出 TP53。"""
    m = re.search(r"\(([^()]+)\)", title or "")
    return m.group(1) if m else ""


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    ids = search_ids(limit)
    records = summarize(ids)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["accession", "gene", "length", "moltype", "organism", "created", "title"])
        for r in records:
            w.writerow([
                r.get("accessionversion", ""),
                gene_from_title(r.get("title", "")),
                r.get("slen", ""),                      # 有的记录没有长度，故意留空
                r.get("moltype", ""),
                r.get("organism", ""),
                r.get("createdate", ""),
                (r.get("title", "") or "").strip(),
            ])

    print(f"写入 {OUT} —— {len(records)} 行")
    return 0


if __name__ == "__main__":
    sys.exit(main())
