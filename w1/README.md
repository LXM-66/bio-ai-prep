# W1 练习清单（2026-09-22 起）

目标：3 个 30 行以内的小脚本，**每个都自己敲一遍**（不要复制黏贴）。
仓库里已有 `gc_content.py`（第 1 个，我写的参考实现），你把它读懂、改掉下面 3 个练手点就算消化。

## 环境（已配好）

- 解释器：`.venv\Scripts\python.exe`（VS Code 里 `Ctrl+Shift+P` → Python: Select Interpreter 选它）
- 终端跑脚本：`python w1/文件名.py`

## 脚本 2：`w1/translate.py` —— DNA 翻译 + 反向互补

要练的东西：**字典、循环、字符串切片、函数**

要求（≤30 行）：

1. 写 `rev_comp(seq)`：返回反向互补链（A↔T、C↔G，并倒序）
2. 写 `translate(seq)`：按密码子表（3 个碱基一组）翻译成氨基酸，遇到 `TAA/TAG/TGA` 就停
3. 用 `w1/sample.fasta` 的序列跑一遍，打印每条序列的反向互补和翻译结果

跑通标志：

```
$ python w1/translate.py
seq1_demo 反向互补: ... 翻译: MRT*
```

## 脚本 3：`w1/fasta_to_csv.py` —— 把统计结果写成 CSV

要练的东西：**文件读写、csv 模块、try/except、参数处理**

要求（≤30 行）：

1. 复用 `gc_content.py` 里的 `read_fasta()`（`from gc_content import read_fasta`）
2. 统计每条序列的 名字 / 长度 / GC 含量
3. 结果写到 `w1/out/stats.csv`，表头 `name,length,gc`
4. 文件不存在时不要崩，打印一句提示并退出（返回码 1）

## 交作业

每写完一个就提交一次：

```bash
git add w1/xxx.py
git commit -m "feat(w1): 完成 xxx 脚本"
git push
```

## 卡住时的排查顺序

1. 看报错最后一行（`Error` 或 `Traceback` 上面那句）
2. `print()` 出中间变量，确认值和你以为的一样
3. 还是不行，把报错原文贴给我
