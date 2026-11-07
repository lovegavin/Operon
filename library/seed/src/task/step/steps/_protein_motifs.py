"""Motif and composition helpers shared by protein panel operators."""
from __future__ import annotations

import re

AA_SET = set("ACDEFGHIKLMNPQRSTVWY")
MONO_NLS = re.compile(r"[KR][KR].[KR]")
BIPARTITE_NLS = re.compile(r"[KR]{2}.{10,12}[KR]{3,5}")
PTS1 = re.compile(r"[SAC][KRH][LM]$")
PKA = re.compile(r"[RK][RK].[ST]")
CK2 = re.compile(r"[ST]..[DE]")
CDK = re.compile(r"[ST]P.[KR]")
NGLYC = re.compile(r"N[^P][ST]")


def sanitize(sequence: str) -> str:
    return "".join(ch if ch in AA_SET else "X" for ch in sequence.upper())


def count_matches(pattern: re.Pattern[str], sequence: str) -> int:
    return sum(1 for i in range(len(sequence)) if pattern.match(sequence, i))


def aliphatic_index(sequence: str) -> float:
    n = len(sequence)
    if n == 0:
        return float("nan")
    a = sequence.count("A")
    v = sequence.count("V")
    il = sequence.count("I") + sequence.count("L")
    return 100.0 * (a + 2.9 * v + 3.9 * il) / n
