"""Double-bond equivalents (rings plus double bonds) from a Hill formula."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._formula_common import doubl_bond_equivalents, formulas_from_form, parsed_counts

_STATISTICS = ("dbe", "dbe_rounded", "integer_dbe", "halogen_count", "dbe_minus_halogen")


class LigandDbeStep(Step):
    provider = "operon-core"
    """Ligand double-bond equivalents"""
    parameters_file = "ligand_dbe.LigandDbeStep.parameters.json"
    definition = {
        "protocol_revision": "3.7",
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
            "outputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
        },
        "protocol_version": 3,
        "version": "1.0.0",
        "id": "ligand_dbe",
        "kind": "operator",
        "title": "Ligand double-bond equivalents",
        "description": "Ring-plus-double-bond equivalents and their integrality from formula element counts.",
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
            raise StepError("ligand_dbe: a Form input with info['formula'] is required")
        form = inputs[0]
        params = ctx.step_params
        molecule_dim = str(params.get("molecule_dim", "molecule") or "molecule")
        field_dim = str(params.get("field_dim", "field") or "field")
        out_name = str(params.get("output", "dbe") or "dbe")
        names, formulas = formulas_from_form(form, "ligand_dbe", molecule_dim)
        counts = parsed_counts("ligand_dbe", formulas)
        rows = []
        for formula, elements in zip(formulas, counts):
            value = doubl_bond_equivalents(elements)
            halogen = float(sum(elements.get(symbol, 0) for symbol in ("F", "Cl", "Br", "I")))
            rows.append([value, float(round(value)), float(abs(value - round(value)) < 1e-9), halogen, float(elements.get("C", 0)) - (float(elements.get("H", 0)) + halogen) / 2.0 + elements.get("N", 0) / 2.0 + 1.0])
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
                "dbe_definition": "C - (H + X)/2 + N/2 + 1",
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_molecules": len(formulas),
            "formula": formulas,
            "statistics": list(_STATISTICS),
        }
        print(f"[ligand_dbe] {len(formulas)} molecules")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
