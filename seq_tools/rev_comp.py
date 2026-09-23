def rev_comp(seq):
    """反向互补链：先倒序，再做 A<->T、C<->G 替换。"""
    table = str.maketrans("ATCG", "TAGC")
    return seq.translate(table)[::-1]

test = "ATGCGT"
print("原链:", test)
print("互补:", rev_comp(test))
BASES = "TCAG"
AAS = "FFLLSSSSYY**CC*WLLLLPPPPHHQQRRRRIIIMTTTTNNKKSSRRVVVVAAAADDEEGGGG"

CODON = {}
for i, b1 in enumerate(BASES):
    for j, b2 in enumerate(BASES):
        for k, b3 in enumerate(BASES):
            CODON[b1 + b2 + b3] = AAS[i * 16 + j * 4 + k]
def translate(seq):
    """DNA 翻译成蛋白质。每 3 个碱基一个密码子，遇到终止密码子就停。"""
    protein = []                             
    for i in range(0, len(seq) - 2, 3):       
        codon = seq[i:i + 3]                  
        aa = CODON.get(codon, "?")            
        if aa == "*":                         
            break                             
        protein.append(aa)                  
    return "".join(protein)                  
print(translate("ATGGCCTAA"))     # 应该输出 MA
print(translate("ATGGCCTAGG"))    # 应该输出 MA（TAG 也是终止）
