"""Parse a Hill formula into element counts and atom totals."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._formula_common import formulas_from_form, parsed_counts, _ELEMENT_COLUMNS

_STATISTICS = ("C", "H", "N", "O", "P", "S", "F", "Cl", "Br", "I", "other_atoms", "heavy_atoms", "total_atoms", "distinct_elements")


class LigandFormulaParseStep(Step):
    provider = "operon-core"
    """Ligand formula parse"""
    parameters_file = "ligand_formula_parse.LigandFormulaParseStep.parameters.json"
    definition = {
        "protocol_revision": "3.7",
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
            "outputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
        },
        "protocol_version": 3,
        "version": "1.0.0",
        "id": "ligand_formula_parse",
        "kind": "operator",
        "title": "Ligand formula parse",
        "description": "Element counts, heavy-atom and total-atom counts parsed from a Hill molecular formula.",
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
            raise StepError("ligand_formula_parse: a Form input with info['formula'] is required")
        form = inputs[0]
        params = ctx.step_params
        molecule_dim = str(params.get("molecule_dim", "molecule") or "molecule")
        field_dim = str(params.get("field_dim", "field") or "field")
        out_name = str(params.get("output", "formula_parse") or "formula_parse")
        names, formulas = formulas_from_form(form, "ligand_formula_parse", molecule_dim)
        counts = parsed_counts("ligand_formula_parse", formulas)
        rows = []
        for formula, elements in zip(formulas, counts):
            values = [float(elements.get(symbol, 0)) for symbol in _ELEMENT_COLUMNS]
            other = float(sum(amount for symbol, amount in elements.items() if symbol not in _ELEMENT_COLUMNS))
            heavy = float(sum(amount for symbol, amount in elements.items() if symbol != "H"))
            total = float(sum(elements.values()))
            rows.append(values + [other, heavy, total, float(len(elements))])
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
                "elements": [dict(sorted(elements.items())) for elements in counts],
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_molecules": len(formulas),
            "formula": formulas,
            "statistics": list(_STATISTICS),
        }
        print(f"[ligand_formula_parse] {len(formulas)} molecules")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
