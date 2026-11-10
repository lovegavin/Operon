"""Monoisotopic, average and nominal mass for molecules in a SMILES Form."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._ligand_common import axis_labels, build_molecules

_STATISTICS = ("exact_mass", "average_mass", "nominal_mass", "formal_charge", "heavy_atoms")


class LigandExactMassStep(Step):
    provider = "operon-core"
    """Exact (monoisotopic) and average molecular mass."""
    parameters_file = "ligand_exact_mass.LigandExactMassStep.parameters.json"
    definition = {
        "protocol_revision": "3.7",
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
            "outputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
        },
        "protocol_version": 3,
        "version": "1.0.0",
        "id": "ligand_exact_mass",
        "kind": "operator",
        "title": "Ligand exact mass",
        "description": "Monoisotopic, average and nominal molecular mass, formal charge and heavy-atom count per molecule.",
        "category": "Chemistry",
        "icon": "Scale",
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
            raise StepError("ligand_exact_mass: a SMILES form input is required")
        form = inputs[0]
        params = ctx.step_params
        molecule_dim = str(params.get("molecule_dim", "molecule") or "molecule")
        field_dim = str(params.get("field_dim", "field") or "field")
        out_name = str(params.get("output", "mass") or "mass")
        if list(form.dims) != [molecule_dim, field_dim]:
            raise StepError(
                "ligand_exact_mass: expected a form with dims "
                f"[{molecule_dim}, {field_dim}], got {list(form.dims)}"
            )

        try:
            from rdkit.Chem import Descriptors, rdMolDescriptors
        except ImportError as error:  # pragma: no cover - dependency guard
            raise StepError(f"ligand_exact_mass: rdkit is required ({error})") from error

        names, _texts, molecules = build_molecules(form, "ligand_exact_mass", molecule_dim, field_dim)
        rows: list[list[float]] = []
        formulas: list[str] = []
        for molecule in molecules:
            exact = float(rdMolDescriptors.CalcExactMolWt(molecule))
            average = float(Descriptors.MolWt(molecule))
            charge = int(sum(atom.GetFormalCharge() for atom in molecule.GetAtoms()))
            rows.append(
                [
                    exact,
                    average,
                    float(int(round(exact))),
                    float(charge),
                    float(molecule.GetNumHeavyAtoms()),
                ]
            )
            formulas.append(rdMolDescriptors.CalcMolFormula(molecule))

        out = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=[molecule_dim, "statistic"],
            labels={
                molecule_dim: axis_labels(names, molecule_dim),
                "statistic": {name: position for position, name in enumerate(_STATISTICS)},
            },
            info={
                "missing_code": np.nan,
                "formula": formulas,
                "n_molecules": len(molecules),
                "unit": "dalton",
                "mass_definition": "exact is monoisotopic, average uses natural abundances",
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_molecules": len(molecules),
            "formula": formulas,
            "statistics": list(_STATISTICS),
            "unit": "dalton",
        }
        print(f"[ligand_exact_mass] {len(molecules)} molecules")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
