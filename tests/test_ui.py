"""界面冒烟测试：脚本能不能跑起来（能抓到导入路径、参数名这类低级错误）。

用 Streamlit 官方的 AppTest 在无浏览器环境下执行整份脚本 —— 比"手动打开网页看一眼"
可靠，因为它在 CI 或纯命令行里也能跑。

两个场景：
    ① 正常：索引在 → 三个页签都在，没有异常
    ② 索引缺失：给出「先跑 build_index.py」的提示，而不是崩一堆栈

索引路径通过环境变量 BIO_AI_INDEX 指到临时目录，所以测试不依赖仓库里那份
gitignore 掉的索引 —— CI 上也能完整跑过。
"""

import sys
from pathlib import Path

import pytest

pytest.importorskip("streamlit", reason="未安装 streamlit，跳过界面冒烟测试")

from streamlit.testing.v1 import AppTest       # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "ui" / "app.py"
sys.path.insert(0, str(ROOT / "rag"))

from store import BM25Index                    # noqa: E402

CHUNKS = ["TP53 编码 p53 蛋白，是重要的抑癌基因。", "单细胞测序可以解析肿瘤内部的细胞异质性。"]
META = [{"source": "PubMed", "sid": "1", "title": "TP53 与肿瘤", "extra": "Nature",
         "year": "2024", "url": "https://pubmed.ncbi.nlm.nih.gov/1/", "chunk": 1},
        {"source": "UniProt", "sid": "P04637", "title": "TP53 蛋白功能", "extra": "Homo sapiens",
         "year": "", "url": "", "chunk": 1}]


def tiny_index(tmp_path: Path) -> Path:
    path = tmp_path / "bm25.json"
    BM25Index().build(CHUNKS, META).save(path, source="测试语料")
    return path


def test_ui_renders_without_exception(tmp_path, monkeypatch):
    monkeypatch.setenv("BIO_AI_INDEX", str(tiny_index(tmp_path)))
    import streamlit as st
    st.cache_resource.clear()
    at = AppTest.from_file(str(APP), default_timeout=120).run()
    assert not at.exception, f"界面脚本报错：{[e.value for e in at.exception]}"
    labels = [tab.label for tab in at.tabs]
    assert "问答" in labels and "速读报告" in labels


def test_ui_shows_hint_when_index_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("BIO_AI_INDEX", str(tmp_path / "not-built-yet.json"))
    import streamlit as st
    st.cache_resource.clear()
    at = AppTest.from_file(str(APP), default_timeout=120).run()
    assert not at.exception
    assert any("还没建索引" in e.value for e in at.error)
