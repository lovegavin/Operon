"""Isotope envelope of molecules in a SMILES Form."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._ligand_common import axis_labels, build_molecules

_PROTON_MASS = 1.007276466621


def _element_isotopes(atomic_number: int) -> list[tuple[float, float]]:
    from rdkit import Chem

    table = Chem.GetPeriodicTable()
    isotopes: list[tuple[float, float]] = []
    for isotope in range(1, 300):
        mass = float(table.GetMassForIsotope(atomic_number, isotope))
        abundance = float(table.GetAbundanceForIsotope(atomic_number, isotope))
        if mass > 0.0 and abundance > 0.0:
            isotopes.append((mass, abundance / 100.0))
    if not isotopes:
        mass = float(table.GetMostCommonIsotopeMass(atomic_number))
        isotopes.append((mass, 1.0))
    return isotopes


def _convolve(distribution: list[tuple[float, float]], isotopes: list[tuple[float, float]]):
    merged: list[list[float]] = []
    for mass, probability in distribution:
        for isotope_mass, isotope_probability in isotopes:
            merged.append([mass + isotope_mass, probability * isotope_probability])
    merged.sort(key=lambda item: item[0])
    collapsed: list[list[float]] = []
    for mass, probability in merged:
        if collapsed and abs(mass - collapsed[-1][0]) < 1e-6:
            collapsed[-1][1] += probability
        else:
            collapsed.append([mass, probability])
    if len(collapsed) > 4096:
        collapsed.sort(key=lambda item: item[1], reverse=True)
        collapsed = collapsed[:2048]
        collapsed.sort(key=lambda item: item[0])
    return collapsed


class LigandIsotopePatternStep(Step):
    provider = "operon-core"
    """Theoretical isotope envelope from natural abundances."""
    parameters_file = "ligand_isotope_pattern.LigandIsotopePatternStep.parameters.json"
    definition = {
        "protocol_revision": "3.7",
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
            "outputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
        },
        "protocol_version": 3,
        "version": "1.0.0",
        "id": "ligand_isotope_pattern",
        "kind": "operator",
        "title": "Ligand isotope pattern",
        "description": "Theoretical isotope envelope (m/z and relative abundance) from natural isotope abundances.",
        "category": "Chemistry",
        "icon": "Waves",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [
                        {"param": "molecule_dim", "default": "molecule"},
                        {"param": "field_dim", "default": "field"},
                    ],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                }
            ],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
            },
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.24", "rdkit>=2022.9"],
        "dependency_imports": ["rdkit"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx: Context, inputs) -> None:
        if not inputs:
            raise StepError("ligand_isotope_pattern: a SMILES form input is required")
        form = inputs[0]
        params = ctx.step_params
        molecule_dim = str(params.get("molecule_dim", "molecule") or "molecule")
        field_dim = str(params.get("field_dim", "field") or "field")
        out_name = str(params.get("output", "isotopes") or "isotopes")
        max_peaks = int(params.get("max_peaks", 6))
        min_relative = float(params.get("min_relative_abundance", 0.001))
        charge = int(params.get("charge", 1))
        if max_peaks < 1 or max_peaks > 50:
            raise StepError("ligand_isotope_pattern: max_peaks must be between 1 and 50")
        if not 0.0 <= min_relative <= 1.0:
            raise StepError(
                "ligand_isotope_pattern: min_relative_abundance must be between 0 and 1"
            )
        if charge < 1 or charge > 8:
            raise StepError("ligand_isotope_pattern: charge must be between 1 and 8")
        if list(form.dims) != [molecule_dim, field_dim]:
            raise StepError(
                "ligand_isotope_pattern: expected a form with dims "
                f"[{molecule_dim}, {field_dim}], got {list(form.dims)}"
            )

        try:
            from rdkit.Chem import rdMolDescriptors
        except ImportError as error:  # pragma: no cover - dependency guard
            raise StepError(f"ligand_isotope_pattern: rdkit is required ({error})") from error

        names, _texts, molecules = build_molecules(
            form, "ligand_isotope_pattern", molecule_dim, field_dim
        )
        matrix: list[list[float]] = []
        formulas: list[str] = []
        n_peaks: list[int] = []
        isotope_lists: list[list[float]] = []
        for molecule in molecules:
            distribution = [[0.0, 1.0]]
            hydrogen = _element_isotopes(1)
            for atom in molecule.GetAtoms():
                atomic_number = int(atom.GetAtomicNum())
                if atomic_number <= 1:
                    continue
                distribution = _convolve(distribution, _element_isotopes(atomic_number))
                for _ in range(int(atom.GetTotalNumHs(includeNeighbors=True))):
                    distribution = _convolve(distribution, hydrogen)
            top = max(probability for _mass, probability in distribution)
            peaks = [
                (mass, probability / top)
                for mass, probability in distribution
                if probability / top >= min_relative
            ]
            peaks.sort(key=lambda item: item[1], reverse=True)
            peaks = peaks[:max_peaks]
            peaks.sort(key=lambda item: item[0])
            peaks = [
                ((mass + charge * _PROTON_MASS) / charge, probability)
                for mass, probability in peaks
            ]
            n_peaks.append(len(peaks))
            formulas.append(rdMolDescriptors.CalcMolFormula(molecule))
            isotope_lists.append([round(value, 6) for mass, probability in peaks for value in (mass, probability)])
            mz_row = [mass for mass, _probability in peaks]
            rel_row = [probability for _mass, probability in peaks]
            mz_row.extend([0.0] * (max_peaks - len(mz_row)))
            rel_row.extend([0.0] * (max_peaks - len(rel_row)))
            row = mz_row + rel_row
            matrix.append(row)

        labels = [f"mz_{index}" for index in range(max_peaks)] + [
            f"rel_{index}" for index in range(max_peaks)
        ]
        out = Form(
            data=np.asarray(matrix, dtype=np.float32),
            dims=[molecule_dim, "feature"],
            labels={
                molecule_dim: axis_labels(names, molecule_dim),
                "feature": {name: position for position, name in enumerate(labels)},
            },
            info={
                "missing_code": np.nan,
                "n_molecules": len(molecules),
                "formula": formulas,
                "n_peaks": n_peaks,
                "peaks": isotope_lists,
                "charge": charge,
                "proton_mass": _PROTON_MASS,
                "value_definition": "m/z assumes [M+zH]z+; rel is relative to the base peak",
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_molecules": len(molecules),
            "formula": formulas,
            "n_peaks": n_peaks,
            "peaks": isotope_lists,
            "charge": charge,
        }
        print(f"[ligand_isotope_pattern] {len(molecules)} molecules, charge {charge}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
