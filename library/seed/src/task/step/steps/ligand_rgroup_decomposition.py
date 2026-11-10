"""R-group decomposition of molecules against a supplied scaffold."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._ligand_common import axis_labels, build_molecules


def _substituent_heavy_atoms(smiles: str) -> int:
    from rdkit import Chem

    molecule = Chem.MolFromSmiles(smiles)
    if molecule is None:
        return 0
    return sum(1 for atom in molecule.GetAtoms() if atom.GetAtomicNum() != 0)


class LigandRgroupDecompositionStep(Step):
    provider = "operon-core"
    """Per-R-group heavy-atom counts against a dummy-labelled scaffold."""
    parameters_file = "ligand_rgroup_decomposition.LigandRgroupDecompositionStep.parameters.json"
    definition = {
        "protocol_revision": "3.7",
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
            "outputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
        },
        "protocol_version": 3,
        "version": "1.0.0",
        "id": "ligand_rgroup_decomposition",
        "kind": "operator",
        "title": "Ligand R-group decomposition",
        "description": "Match molecules to a dummy-labelled scaffold and report heavy-atom counts for every R group.",
        "category": "Chemistry",
        "icon": "Puzzle",
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
            raise StepError("ligand_rgroup_decomposition: a SMILES form input is required")
        form = inputs[0]
        params = ctx.step_params
        molecule_dim = str(params.get("molecule_dim", "molecule") or "molecule")
        field_dim = str(params.get("field_dim", "field") or "field")
        out_name = str(params.get("output", "rgroups") or "rgroups")
        scaffold_text = str(params.get("scaffold", "") or "").strip()
        if not scaffold_text:
            raise StepError(
                "ligand_rgroup_decomposition: scaffold is required, for example "
                "'c1ccccc1[*:1]'"
            )
        if list(form.dims) != [molecule_dim, field_dim]:
            raise StepError(
                "ligand_rgroup_decomposition: expected a form with dims "
                f"[{molecule_dim}, {field_dim}], got {list(form.dims)}"
            )

        try:
            from rdkit import Chem
            from rdkit.Chem import rdRGroupDecomposition as rdRGD
        except ImportError as error:  # pragma: no cover - dependency guard
            raise StepError(f"ligand_rgroup_decomposition: rdkit is required ({error})") from error

        scaffold = Chem.MolFromSmiles(scaffold_text)
        if scaffold is None:
            raise StepError(
                f"ligand_rgroup_decomposition: cannot parse scaffold '{scaffold_text}'"
            )
        dummy_labels = sorted(
            {
                int(atom.GetAtomMapNum())
                for atom in scaffold.GetAtoms()
                if atom.GetAtomicNum() == 0 and int(atom.GetAtomMapNum()) > 0
            }
        )
        if not dummy_labels:
            raise StepError(
                "ligand_rgroup_decomposition: the scaffold needs at least one "
                "dummy atom with a map number, for example [*:1]"
            )

        names, _texts, molecules = build_molecules(
            form, "ligand_rgroup_decomposition", molecule_dim, field_dim
        )
        rows, unmatched = rdRGD.RGroupDecompose([scaffold], molecules, asSmiles=True)
        unmatched_set = {int(index) for index in unmatched}
        if len(rows) != len(molecules) - len(unmatched_set):
            raise StepError(
                "ligand_rgroup_decomposition: RDKit returned an unexpected number "
                f"of matches ({len(rows)} rows for {len(molecules)} molecules)"
            )

        rgroup_names = sorted(
            {key for row in rows for key in row if key != "Core"},
            key=lambda name: (len(name), name),
        )
        if not rgroup_names:
            rgroup_names = [f"R{label}" for label in dummy_labels]

        matched: list[float] = []
        rgroup_smiles: list[dict[str, str]] = []
        matrix: list[list[float]] = []
        matched_rows = iter(rows)
        for index in range(len(molecules)):
            if index in unmatched_set:
                matched.append(0.0)
                rgroup_smiles.append({})
                matrix.append([0.0] * (len(rgroup_names) + 2))
                continue
            row = next(matched_rows)
            matched.append(1.0)
            values = {key: value for key, value in row.items() if key != "Core"}
            rgroup_smiles.append({key: str(value) for key, value in values.items()})
            matrix.append(
                [float(_substituent_heavy_atoms(values.get(name, ""))) for name in rgroup_names]
                + [1.0, float(len(values))]
            )

        columns = rgroup_names + ["matched", "n_rgroups"]
        out = Form(
            data=np.asarray(matrix, dtype=np.float32),
            dims=[molecule_dim, "rgroup"],
            labels={
                molecule_dim: axis_labels(names, molecule_dim),
                "rgroup": {name: position for position, name in enumerate(columns)},
            },
            info={
                "missing_code": np.nan,
                "n_molecules": len(molecules),
                "scaffold": scaffold_text,
                "rgroup_columns": rgroup_names,
                "matched": [bool(value) for value in matched],
                "rgroup_smiles": rgroup_smiles,
                "value_definition": "heavy atoms in each substituent; dummy atoms excluded",
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_molecules": len(molecules),
            "n_matched": int(sum(matched)),
            "scaffold": scaffold_text,
            "rgroup_columns": rgroup_names,
            "rgroup_smiles": rgroup_smiles,
        }
        print(
            f"[ligand_rgroup_decomposition] {len(molecules)} molecules, "
            f"{int(sum(matched))} matched"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
