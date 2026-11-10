"""Shared helpers for chemistry operators that read a SMILES Form.

The readers emit one row per molecule and one ``field`` column per token
(``molecule``, ``smiles``, ``length``, ``heavy_atoms``).  String columns are
label encoded, so the SMILES text is recovered from ``form.info["encoders"]``.
"""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError

ELEMENTS = ("C", "H", "N", "O", "S", "P", "F", "Cl", "Br", "I")


def molecule_names(form: Form, molecule_dim: str) -> list[str]:
    """Return molecule labels ordered by their axis position."""
    labels = form.labels.get(molecule_dim) or {}
    if labels:
        pairs = sorted(((int(position), str(name)) for name, position in labels.items()))
        return [name for _, name in pairs]
    return [f"molecule:{index}" for index in range(int(np.asarray(form.data).shape[0]))]


def smiles_column(form: Form, field_dim: str, operator: str) -> list[str]:
    """Decode the ``smiles`` column of a SMILES Form."""
    labels = form.labels.get(field_dim) or {}
    if "smiles" not in labels:
        raise StepError(
            f"{operator}: the input form has no 'smiles' column on dim '{field_dim}'"
        )
    index = int(labels["smiles"])
    codes = np.asarray(form.data)[:, index]
    encoder = ((form.info or {}).get("encoders") or {}).get(field_dim, {}).get("smiles")
    if encoder is None:
        raise StepError(
            f"{operator}: the 'smiles' column is not label encoded; "
            "connect a SMILES reader output"
        )
    try:
        values = encoder.inverse_transform(codes)
    except Exception as error:  # noqa: BLE001 - encoder implementations vary
        raise StepError(f"{operator}: cannot decode the 'smiles' column: {error}") from error
    return [str(value) for value in values]


def build_molecules(
    form: Form,
    operator: str,
    molecule_dim: str = "molecule",
    field_dim: str = "field",
):
    """Return ``(names, smiles, rdkit molecules)`` for one SMILES Form."""
    from rdkit import Chem

    names = molecule_names(form, molecule_dim)
    texts = smiles_column(form, field_dim, operator)
    if len(names) != len(texts):
        raise StepError(
            f"{operator}: molecule labels ({len(names)}) do not match SMILES "
            f"rows ({len(texts)})"
        )
    if not texts:
        raise StepError(f"{operator}: the input form has no molecules")
    molecules = []
    for name, text in zip(names, texts):
        molecule = Chem.MolFromSmiles(text)
        if molecule is None:
            raise StepError(
                f"{operator}: cannot parse SMILES '{text}' for molecule '{name}'"
            )
        molecules.append(molecule)
    return names, texts, molecules


def axis_labels(names: list[str], dimension: str) -> dict[str, int]:
    if len(names) != len(set(names)):
        raise StepError("rdkit: molecule labels on the input axis must be unique")
    return {name: position for position, name in enumerate(names)}
