"""语料加载：把不同来源的记录统一成同一种形状。

多源语料的字段名各不相同（PubMed 有 pmid/abstract/journal，UniProt 有 accession/function，
PDB 有 entry id/title/method），如果让检索层去认这些差异，每加一个数据源就要改一遍检索代码。
所以这里做一层归一化，检索层只管收 `Record`。

统一后的字段：
    sid     该来源内部的唯一编号（PMID / UniProt accession / PDB ID）
    source  来源名，用于在回答里标出处
    title   标题（信息密度最高的一句，会并进正文参与检索）
    text    正文（摘要 / 功能注释 / 结构描述）
    extra   来源特有的补充（期刊 / 物种 / 实验方法）
    year    年份，没有就留空
    url     原文链接
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"


@dataclass
class Record:
    sid: str
    source: str
    title: str
    text: str
    extra: str = ""
    year: str = ""
    url: str = ""
    tags: list = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)


def _norm_pubmed(d: dict) -> Record:
    return Record(sid=str(d.get("pmid", "")), source="PubMed", title=d.get("title", ""),
                  text=d.get("abstract", ""), extra=d.get("journal", ""),
                  year=str(d.get("year", "")), url=f"https://pubmed.ncbi.nlm.nih.gov/{d.get('pmid', '')}/")


def _norm_uniprot(d: dict) -> Record:
    """UniProt 原生字段 → 统一记录。"""
    title = f"{d.get('gene', '')} {d.get('protein', '')}".strip()
    body = d.get("function", "")
    if d.get("keywords"):
        body += " 关键词：" + "、".join(d["keywords"]) + "。"
    if d.get("length"):
        body += f"（{d['length']} 个氨基酸）"
    acc = d.get("accession", "")
    return Record(sid=str(acc), source="UniProt", title=title, text=body,
                  extra=d.get("organism", ""), year="",
                  url=f"https://www.uniprot.org/uniprotkb/{acc}/entry",
                  tags=d.get("keywords", []) or [])


def _norm_pdb(d: dict) -> Record:
    return Record(sid=str(d.get("pdb_id", "")), source="PDB", title=d.get("title", ""),
                  text=d.get("description", ""), extra=d.get("method", ""), year=str(d.get("year", "")),
                  url=f"https://www.rcsb.org/structure/{d.get('pdb_id', '')}")


# 文件名 → 归一化函数。加新数据源时只在这里登记一行。
LOADERS = {
    "pubmed.jsonl": _norm_pubmed,
    "uniprot.jsonl": _norm_uniprot,
    "pdb.jsonl": _norm_pdb,
}


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_records(datadir: Path = DATA) -> list[Record]:
    """读取 datadir 下所有已登记的语料文件，返回统一记录。"""
    records: list[Record] = []
    for name, loader in LOADERS.items():
        for raw in read_jsonl(Path(datadir) / name):
            try:
                rec = loader(raw)
            except Exception as exc:                     # 单条坏数据不该毁掉整个语料
                print(f"  跳过 {name} 里的一条记录：{exc}")
                continue
            if rec.text.strip():
                records.append(rec)
    return records


def write_jsonl(records: list[Record], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec.as_dict(), ensure_ascii=False) + "\n")
    return path


def stats(records: list[Record]) -> dict:
    by_source: dict[str, int] = {}
    for rec in records:
        by_source[rec.source] = by_source.get(rec.source, 0) + 1
    return {"总记录": len(records), "按来源": by_source}


# 来源名 → 归一化函数，供"手上已有一条原生记录"时直接转换（如 PubMed 在线取回的结果）
BY_SOURCE = {"PubMed": _norm_pubmed, "UniProt": _norm_uniprot, "PDB": _norm_pdb}


def to_record(source: str, d: dict) -> Record:
    fn = BY_SOURCE.get(source)
    if fn:
        return fn(d)
    return Record(sid=str(d.get("sid", "")), source=source, title=d.get("title", ""),
                  text=d.get("text", ""), extra=d.get("extra", ""), year=str(d.get("year", "")),
                  url=d.get("url", ""))
