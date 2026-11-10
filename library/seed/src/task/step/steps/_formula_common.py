"""Formula arithmetic shared by the b50 ligand MS operators."""
from __future__ import annotations

import re

import numpy as np

from src.core import Form, StepError

_ELEMENT_RE = re.compile(r"([A-Z][a-z]?)(\d*)")
_ELEMENT_COLUMNS = ("C", "H", "N", "O", "P", "S", "F", "Cl", "Br", "I")
_HALOGENS = ("F", "Cl", "Br", "I")
_NOMINAL = {
    "C": 12, "H": 1, "N": 14, "O": 16, "P": 31, "S": 32,
    "F": 19, "Cl": 35, "Br": 79, "I": 127,
}


def parse_formula(text: str) -> dict:
    """Parse a plain Hill formula such as ``C9H8O4`` into element counts."""
    value = str(text).strip()
    if not value:
        raise ValueError("empty formula")
    pos = 0
    counts: dict[str, int] = {}
    for match in _ELEMENT_RE.finditer(value):
        if match.start() != pos:
            raise ValueError(f"invalid formula {text!r}: unexpected text at {pos}")
        symbol = match.group(1)
        number = int(match.group(2) or "1")
        if number <= 0:
            raise ValueError(f"invalid formula {text!r}: non-positive count")
        counts[symbol] = counts.get(symbol, 0) + number
        pos = match.end()
    if pos != len(value) or not counts:
        raise ValueError(f"invalid formula {text!r}")
    return counts


def _periodic_table():
    from rdkit.Chem import GetPeriodicTable

    return GetPeriodicTable()


def exact_mass(counts: dict) -> float:
    table = _periodic_table()
    return float(sum(amount * table.GetMostCommonIsotopeMass(symbol) for symbol, amount in counts.items()))


def average_mass(counts: dict) -> float:
    table = _periodic_table()
    return float(sum(amount * table.GetAtomicWeight(symbol) for symbol, amount in counts.items()))


def nominal_mass(counts: dict) -> int:
    unknown = [symbol for symbol in counts if symbol not in _NOMINAL]
    if unknown:
        raise ValueError(f"no nominal mass for {unknown}")
    return int(sum(amount * _NOMINAL[symbol] for symbol, amount in counts.items()))


def doubl_bond_equivalents(counts: dict) -> float:
    carbon = counts.get("C", 0)
    hydrogen = counts.get("H", 0)
    nitrogen = counts.get("N", 0)
    halogen = sum(counts.get(symbol, 0) for symbol in _HALOGENS)
    return float(carbon - (hydrogen + halogen) / 2.0 + nitrogen / 2.0 + 1.0)


def axis_names(form: Form, molecule_dim: str) -> list[str]:
    labels = form.labels.get(molecule_dim)
    count = int(form.data.shape[0])
    if isinstance(labels, dict):
        pairs = sorted(labels.items(), key=lambda item: item[1])
        if len(pairs) == count:
            return [str(name) for name, _ in pairs]
    if isinstance(labels, (list, tuple)) and len(labels) == count:
        return [str(name) for name in labels]
    return [f"molecule_{index + 1}" for index in range(count)]


def formulas_from_form(form: Form, operator: str, molecule_dim: str = "molecule") -> tuple[list[str], list[str]]:
    info = form.info or {}
    formulas = info.get("formula")
    if formulas is None:
        raise StepError(f"{operator}: input Form has no info['formula'] list")
    formulas = [str(item) for item in formulas]
    if len(formulas) != int(form.data.shape[0]):
        raise StepError(f"{operator}: {len(formulas)} formulas for {form.data.shape[0]} rows")
    return axis_names(form, molecule_dim), formulas


def parsed_counts(operator: str, formulas: list[str]) -> list[dict]:
    rows = []
    for formula in formulas:
        try:
            rows.append(parse_formula(formula))
        except ValueError as error:
            raise StepError(f"{operator}: {error}") from error
    return rows
