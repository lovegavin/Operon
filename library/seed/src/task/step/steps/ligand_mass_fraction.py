"""Element mass fractions from average atomic weights."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

def _weight(symbol: str) -> float:
    from rdkit.Chem import GetPeriodicTable

    return float(GetPeriodicTable().GetAtomicWeight(symbol))

from ._formula_common import average_mass, formulas_from_form, parsed_counts, _ELEMENT_COLUMNS

_STATISTICS = ("C", "H", "N", "O", "P", "S", "halogens", "other", "total_mass")


class LigandMassFractionStep(Step):
    provider = "operon-core"
    """Ligand element mass fraction"""
    parameters_file = "ligand_mass_fraction.LigandMassFractionStep.parameters.json"
    definition = {
        "protocol_revision": "3.7",
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
            "outputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
        },
        "protocol_version": 3,
        "version": "1.0.0",
        "id": "ligand_mass_fraction",
        "kind": "operator",
        "title": "Ligand element mass fraction",
        "description": "Average-mass fraction of each element in a Hill formula.",
        "category": "Chemistry",
        "icon": "FlaskConical",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [
                        {"param": "molecule_dim", "default": "molecule"},
                        {"param": "statistic_dim", "default": "statistic"},
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
            raise StepError("ligand_mass_fraction: a Form input with info['formula'] is required")
        form = inputs[0]
        params = ctx.step_params
        molecule_dim = str(params.get("molecule_dim", "molecule") or "molecule")
        field_dim = str(params.get("field_dim", "field") or "field")
        out_name = str(params.get("output", "mass_fraction") or "mass_fraction")
        names, formulas = formulas_from_form(form, "ligand_mass_fraction", molecule_dim)
        counts = parsed_counts("ligand_mass_fraction", formulas)
        rows = []
        for formula, elements in zip(formulas, counts):
            total = average_mass(elements)
            values = [elements.get(symbol, 0) * _weight(symbol) / total for symbol in ("C", "H", "N", "O", "P", "S")]
            halogen = sum(elements.get(symbol, 0) * _weight(symbol) for symbol in ("F", "Cl", "Br", "I"))
            other = sum(amount * _weight(symbol) for symbol, amount in elements.items() if symbol not in ("C", "H", "N", "O", "P", "S", "F", "Cl", "Br", "I"))
            rows.append(values + [halogen / total, other / total, total])
        out = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=[molecule_dim, "statistic"],
            labels={
                molecule_dim: {name: index for index, name in enumerate(names)},
                "statistic": {name: index for index, name in enumerate(_STATISTICS)},
            },
            info={
                "missing_code": np.nan,
                "formula": formulas,
                "n_molecules": len(formulas),
                "unit": "fraction of average molecular mass",
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_molecules": len(formulas),
            "formula": formulas,
            "statistics": list(_STATISTICS),
        }
        print(f"[ligand_mass_fraction] {len(formulas)} molecules")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
