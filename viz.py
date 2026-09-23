"""全仓库统一的出图规范 —— 一处改，所有图一起变。

用法（notebook 或脚本里）：

    from viz import apply_style, save, PALETTE
    apply_style()
    fig, ax = plt.subplots(...)
    save(fig, OUT / "fig1.png")

规范内容：中文字体、去上/右边框、浅灰网格、统一字号与配色、统一导出 dpi。
"""

import matplotlib.pyplot as plt

# 统一配色：主色（蓝）、辅色（绿/橙/紫/红），按顺序取用
PALETTE = ["#4C8BF5", "#59C3A5", "#F0A35E", "#8E7CC3", "#D9534F"]
DPI = 150


def apply_style():
    """套用全仓库统一的 matplotlib 样式。"""
    plt.rcParams.update({
        # 中文能正常显示（Windows 自带雅黑；不列 SimHei —— 它没有粗体字重，会触发 findfont 报警）
        "font.family": ["Microsoft YaHei", "Noto Sans SC", "DejaVu Sans"],
        "axes.unicode_minus": False,
        # 图幅与导出
        "figure.dpi": 110,
        "savefig.dpi": DPI,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        # 标题与轴标签
        "axes.titlesize": 12,
        "axes.titleweight": "bold",
        "axes.labelsize": 10,
        "axes.edgecolor": "#CCCCCC",
        # 少即是多：去掉上/右边框，留浅网格当参考线
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": "#ECECEC",
        "grid.linewidth": 0.8,
        # 刻度与图例
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "legend.frameon": False,
        "legend.fontsize": 9,
    })


def save(fig, path):
    """按统一 dpi 导出，自动收紧边距。"""
    fig.tight_layout()
    fig.savefig(path, dpi=DPI, bbox_inches="tight", facecolor="white")
    return path
