"""界面冒烟测试：脚本能不能跑起来（能抓到导入路径、参数名这类低级错误）。

用 Streamlit 官方的 AppTest 在无浏览器环境下执行整份脚本 —— 比"手动打开网页看一眼"
可靠，因为它在 CI 或纯命令行里也能跑。
"""

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parent.parent / "ui" / "app.py"


def test_ui_renders_without_exception():
    at = AppTest.from_file(str(APP), default_timeout=120).run()
    assert not at.exception, f"界面脚本报错：{[e.value for e in at.exception]}"
    # 三个页签都应在
    labels = [t for tab in at.tabs for t in [tab.label]]
    assert "问答" in labels and "速读报告" in labels
