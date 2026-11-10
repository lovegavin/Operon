"""Convert a neutral formula mass into an adduct m/z."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

_ADDUCTS = {
    "[M+H]+": (1.007276466621, 1),
    "[M-H]-": (-1.007276466621, 1),
    "[M+Na]+": (22.989218, 1),
    "[M+NH4]+": (18.033823, 1),
    "[M+2H]2+": (2 * 1.007276466621, 2),
}


def adduct_shift(name: str):
    if name not in _ADDUCTS:
        raise StepError(f"ligand_adduct_mz: unsupported adduct {name!r}")
    return _ADDUCTS[name]

from ._formula_common import exact_mass, formulas_from_form, parsed_counts

_STATISTICS = ("neutral_exact_mass", "[M+H]+", "[M-H]-", "[M+Na]+", "[M+NH4]+", "[M+2H]2+")


class LigandAdductMzStep(Step):
    provider = "operon-core"
    """Ligand adduct m/z"""
    parameters_file = "ligand_adduct_mz.LigandAdductMzStep.parameters.json"
    definition = {
        "protocol_revision": "3.7",
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
            "outputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
        },
        "protocol_version": 3,
        "version": "1.0.0",
        "id": "ligand_adduct_mz",
        "kind": "operator",
        "title": "Ligand adduct m/z",
        "description": "Neutral monoisotopic mass and five common adduct m/z values for a Hill formula.",
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
            raise StepError("ligand_adduct_mz: a Form input with info['formula'] is required")
        form = inputs[0]
        params = ctx.step_params
        molecule_dim = str(params.get("molecule_dim", "molecule") or "molecule")
        field_dim = str(params.get("field_dim", "field") or "field")
        out_name = str(params.get("output", "adduct_mz") or "adduct_mz")
        names, formulas = formulas_from_form(form, "ligand_adduct_mz", molecule_dim)
        counts = parsed_counts("ligand_adduct_mz", formulas)
        rows = []
        for formula, elements in zip(formulas, counts):
            neutral = exact_mass(elements)
            rows.append([neutral] + [(neutral + delta) / abs(charge) for delta, charge in _ADDUCTS.values()])
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
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_molecules": len(formulas),
            "formula": formulas,
            "statistics": list(_STATISTICS),
        }
        print(f"[ligand_adduct_mz] {len(formulas)} molecules")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
