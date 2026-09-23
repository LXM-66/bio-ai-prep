"""让 pytest 能找到各模块（这些脚本是按"直接跑"组织的，不是安装成包）。"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for sub in ("rag", "seq_tools", "llm_client", "common"):
    p = str(ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)
