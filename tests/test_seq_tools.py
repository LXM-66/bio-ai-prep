"""序列工具的已知输入 → 已知输出（GC 含量、反向互补、密码子翻译）。"""

from gc_content import gc_content, read_fasta
from rev_comp import rev_comp, translate


def test_gc_content_boundaries():
    assert gc_content("GGCC") == 1.0
    assert gc_content("ATAT") == 0.0
    assert gc_content("ATGC") == 0.5
    assert gc_content("") == 0.0            # 空序列不能除以零


def test_gc_content_denominator_is_full_length():
    # 注意：非 ACGT 字符（如 N、-）也计入分母 —— 对含 N 的真实序列，
    # 严格算法应当剔除它们；这里保持"所见即所算"，由调用方决定是否先清理。
    assert abs(gc_content("ATGC-NN") - 2 / 7) < 1e-9


def test_rev_comp_known_case():
    assert rev_comp("ATGCGT") == "ACGCAT"
    assert rev_comp("AAAA") == "TTTT"
    assert rev_comp("") == ""


def test_translate_stops_at_stop_codon():
    assert translate("ATGGCCTAA") == "MA"      # ATG=M, GCC=A, TAA=停止
    assert translate("ATGGCCTAGG") == "MA"     # TAG 也是停止密码子
    assert translate("GGG") == "G"


def test_read_fasta_parses_records(tmp_path):
    path = tmp_path / "t.fasta"
    path.write_text(">seq1 描述\nATGC\nAAAA\n>seq2\nGGCC\n", encoding="utf-8")
    seqs = read_fasta(path)
    assert list(seqs) == ["seq1", "seq2"]      # 只取名字第一段，注释不进名字
    assert seqs["seq1"] == "ATGCAAAA"
    assert seqs["seq2"] == "GGCC"
