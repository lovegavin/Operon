"""Per-molecule molecular formula and element counts from a SMILES Form."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._ligand_common import ELEMENTS, axis_labels, build_molecules

_STATISTICS = ELEMENTS + ("other", "heavy_atoms", "total_atoms", "formal_charge")


class LigandMolecularFormulaStep(Step):
    provider = "operon-core"
    """Hill-formula strings plus element counts for small molecules."""
    parameters_file = "ligand_molecular_formula.LigandMolecularFormulaStep.parameters.json"
    definition = {
        "protocol_revision": "3.7",
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
            "outputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
        },
        "protocol_version": 3,
        "version": "1.0.0",
        "id": "ligand_molecular_formula",
        "kind": "operator",
        "title": "Ligand molecular formula",
        "description": "Hill-notation molecular formula and per-element atom counts for every molecule in a SMILES form.",
        "category": "Chemistry",
        "icon": "Formula",
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
            raise StepError("ligand_molecular_formula: a SMILES form input is required")
        form = inputs[0]
        params = ctx.step_params
        molecule_dim = str(params.get("molecule_dim", "molecule") or "molecule")
        field_dim = str(params.get("field_dim", "field") or "field")
        out_name = str(params.get("output", "formula") or "formula")
        if list(form.dims) != [molecule_dim, field_dim]:
            raise StepError(
                "ligand_molecular_formula: expected a form with dims "
                f"[{molecule_dim}, {field_dim}], got {list(form.dims)}"
            )

        try:
            from rdkit.Chem import rdMolDescriptors
        except ImportError as error:  # pragma: no cover - dependency guard
            raise StepError(f"ligand_molecular_formula: rdkit is required ({error})") from error

        names, _texts, molecules = build_molecules(form, "ligand_molecular_formula", molecule_dim, field_dim)
        rows: list[list[float]] = []
        formulas: list[str] = []
        for molecule in molecules:
            counts = {symbol: 0 for symbol in ELEMENTS}
            other = 0
            for atom in molecule.GetAtoms():
                symbol = atom.GetSymbol()
                if symbol in counts:
                    counts[symbol] += 1
                else:
                    other += 1
            heavy = int(molecule.GetNumHeavyAtoms())
            total = int(molecule.GetNumAtoms()) + sum(
                int(atom.GetTotalNumHs(includeNeighbors=False)) for atom in molecule.GetAtoms()
            )
            charge = int(sum(atom.GetFormalCharge() for atom in molecule.GetAtoms()))
            formula = rdMolDescriptors.CalcMolFormula(molecule)
            formulas.append(formula)
            rows.append(
                [float(counts[symbol]) for symbol in ELEMENTS]
                + [float(other), float(heavy), float(total), float(charge)]
            )

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
                "elements": list(ELEMENTS),
                "notation": "Hill",
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_molecules": len(molecules),
            "formula": formulas,
            "statistics": list(_STATISTICS),
        }
        print(f"[ligand_molecular_formula] {len(molecules)} molecules")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
