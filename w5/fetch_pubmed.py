"""从 PubMed 拉一批摘要，作为 RAG 的语料（真实生物医药文本）。

用法：
    python w5/fetch_pubmed.py                       # 默认主题、100 篇
    python w5/fetch_pubmed.py 150 "single-cell RNA sequencing cancer"

产物：
    w5/data/pubmed.jsonl    每行一篇：pmid / title / abstract / journal / year
"""

import json
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
DATA = Path(__file__).resolve().parent / "data"
OUT = DATA / "pubmed.jsonl"
DEFAULT_QUERY = "single-cell RNA sequencing AND cancer"


def fetch(url, timeout=90, retries=3):
    """带重试的下载（NCBI 会间歇性超时）。"""
    req = urllib.request.Request(url, headers={"User-Agent": "w5-learning-script"})
    for attempt in range(1, retries + 1):
        try:
            return urllib.request.urlopen(req, timeout=timeout).read()
        except Exception as e:
            print(f"    ✗ 第 {attempt}/{retries} 次失败：{type(e).__name__}: {str(e)[:60]}")
            if attempt == retries:
                raise
            time.sleep(3 * attempt)


def search_pmids(query, limit):
    url = f"{EUTILS}/esearch.fcgi?" + urllib.parse.urlencode(
        {"db": "pubmed", "term": query, "retmax": limit, "retmode": "json", "sort": "relevance"})
    data = json.loads(fetch(url).decode("utf-8"))
    result = data["esearchresult"]
    print(f"命中 {int(result['count']):,} 篇，本次取 {len(result['idlist'])} 篇")
    return result["idlist"]


def parse_articles(xml_bytes):
    """把 PubMed XML 拆成 [{pmid, title, abstract, journal, year}, ...]"""
    root = ET.fromstring(xml_bytes)
    out = []
    for art in root.findall(".//PubmedArticle"):
        def text(xpath):
            node = art.find(xpath)
            return "".join(node.itertext()).strip() if node is not None else ""

        title = text(".//ArticleTitle")
        abstract = " ".join("".join(node.itertext()).strip()
                            for node in art.findall(".//Abstract/AbstractText"))
        out.append({
            "pmid": text(".//PMID"),
            "title": title,
            "abstract": abstract,
            "journal": text(".//Journal/Title"),
            "year": text(".//JournalIssue/PubDate/Year") or text(".//ArticleDate/Year"),
        })
    return [a for a in out if a["abstract"]]


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    query = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_QUERY
    print(f"主题：{query}")

    pmids = search_pmids(query, limit)
    articles = []
    for i in range(0, len(pmids), 50):                 # 每批 50 篇，中间停 0.5s
        batch = pmids[i:i + 50]
        url = f"{EUTILS}/efetch.fcgi?" + urllib.parse.urlencode(
            {"db": "pubmed", "id": ",".join(batch), "rettype": "abstract", "retmode": "xml"})
        articles.extend(parse_articles(fetch(url)))
        print(f"  批次 {i // 50 + 1}：已解析 {len(articles)} 篇")
        if i + 50 < len(pmids):
            time.sleep(0.5)

    DATA.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        for a in articles:
            f.write(json.dumps(a, ensure_ascii=False) + "\n")

    years = [a["year"] for a in articles if a["year"]]
    print(f"写入 {OUT} —— {len(articles)} 篇（年份 {min(years)}–{max(years)}）" if years
          else f"写入 {OUT} —— {len(articles)} 篇")
    return 0


if __name__ == "__main__":
    sys.exit(main())
