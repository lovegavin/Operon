"""Shared physicochemical helpers for the b52 protein property panel."""
from __future__ import annotations

import math

from ._protein_motifs import sanitize

KYTE_DOOLITTLE = {
    "A": 1.8, "R": -4.5, "N": -3.5, "D": -3.5, "C": 2.5, "Q": -3.5,
    "E": -3.5, "G": -0.4, "H": -3.2, "I": 4.5, "L": 3.8, "K": -3.9,
    "M": 1.9, "F": 2.8, "P": -1.6, "S": -0.8, "T": -0.7, "W": -0.9,
    "Y": -1.3, "V": 4.2,
}
PKA = {
    "Nterm": 8.60, "Cterm": 3.60, "D": 3.90, "E": 4.10, "C": 8.50,
    "Y": 10.10, "H": 6.50, "K": 10.80, "R": 12.50,
}
HYDROPHOBIC = set("AILMFVW")


def gravy(seq: str) -> float:
    seq = sanitize(seq)
    return sum(KYTE_DOOLITTLE.get(a, 0.0) for a in seq) / len(seq)


def gravy_windows(seq: str, width: int = 9):
    seq = sanitize(seq)
    return [sum(KYTE_DOOLITTLE.get(a, 0.0) for a in seq[i:i + width]) / width
            for i in range(0, len(seq) - width + 1)]


def charge_at_ph(seq: str, ph: float) -> float:
    seq = sanitize(seq)
    charge = 1.0 / (1.0 + 10 ** (ph - PKA["Nterm"]))
    charge -= 1.0 / (1.0 + 10 ** (PKA["Cterm"] - ph))
    for aa in seq:
        if aa in ("K", "R", "H"):
            charge += 1.0 / (1.0 + 10 ** (ph - PKA[aa]))
        elif aa in ("D", "E", "C", "Y"):
            charge -= 1.0 / (1.0 + 10 ** (PKA[aa] - ph))
    return charge


def hydrophobic_moment(seq: str, angle: float = 100.0, width: int = 18) -> float:
    seq = sanitize(seq)
    best = 0.0
    theta = math.radians(angle)
    for start in range(0, max(1, len(seq) - width + 1)):
        window = seq[start:start + width]
        if len(window) < 4:
            continue
        x = sum(KYTE_DOOLITTLE.get(a, 0.0) * math.cos(i * theta) for i, a in enumerate(window))
        y = sum(KYTE_DOOLITTLE.get(a, 0.0) * math.sin(i * theta) for i, a in enumerate(window))
        best = max(best, math.hypot(x, y) / len(window))
    return best


def longest_hydrophobic_run(seq: str) -> int:
    best = run = 0
    for aa in seq:
        if aa in HYDROPHOBIC:
            run += 1
            best = max(best, run)
        else:
            run = 0
    return best
