"""Nitrogen-rule parity check from nominal mass and nitrogen count."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._formula_common import formulas_from_form, nominal_mass, parsed_counts

_STATISTICS = ("nominal_mass", "nitrogen_count", "even_mass", "even_nitrogen", "rule_ok", "nominal_minus_exact")


class LigandNitrogenRuleStep(Step):
    provider = "operon-core"
    """Ligand nitrogen rule"""
    parameters_file = "ligand_nitrogen_rule.LigandNitrogenRuleStep.parameters.json"
    definition = {
        "protocol_revision": "3.7",
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
            "outputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
        },
        "protocol_version": 3,
        "version": "1.0.0",
        "id": "ligand_nitrogen_rule",
        "kind": "operator",
        "title": "Ligand nitrogen rule",
        "description": "Nominal mass and nitrogen-rule parity test for a neutral Hill formula.",
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
            raise StepError("ligand_nitrogen_rule: a Form input with info['formula'] is required")
        form = inputs[0]
        params = ctx.step_params
        molecule_dim = str(params.get("molecule_dim", "molecule") or "molecule")
        field_dim = str(params.get("field_dim", "field") or "field")
        out_name = str(params.get("output", "nitrogen_rule") or "nitrogen_rule")
        names, formulas = formulas_from_form(form, "ligand_nitrogen_rule", molecule_dim)
        counts = parsed_counts("ligand_nitrogen_rule", formulas)
        rows = []
        for formula, elements in zip(formulas, counts):
            mass = nominal_mass(elements)
            nitrogen = int(elements.get("N", 0))
            even_mass = mass % 2 == 0
            even_nitrogen = nitrogen % 2 == 0
            rows.append([float(mass), float(nitrogen), float(even_mass), float(even_nitrogen), float(even_mass == even_nitrogen), 0.0])
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
                "rule": "a neutral closed-shell molecule has an even nominal mass iff it has an even number of nitrogen atoms",
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_molecules": len(formulas),
            "formula": formulas,
            "statistics": list(_STATISTICS),
        }
        print(f"[ligand_nitrogen_rule] {len(formulas)} molecules")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
