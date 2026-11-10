"""BRICS fragmentation statistics for molecules in a SMILES Form."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._ligand_common import axis_labels, build_molecules

_STATISTICS = (
    "n_fragments",
    "n_unique_fragments",
    "mean_fragment_heavy_atoms",
    "max_fragment_heavy_atoms",
    "min_fragment_heavy_atoms",
)


def _fragment_heavy_atoms(smiles: str) -> int:
    from rdkit import Chem

    fragment = Chem.MolFromSmiles(smiles)
    if fragment is None:
        return 0
    heavy = 0
    for atom in fragment.GetAtoms():
        if atom.GetAtomicNum() == 0:
            continue
        heavy += 1
    return heavy


class LigandBricsFragmentsStep(Step):
    provider = "operon-core"
    """BRICS retrosynthetic fragment counts and heavy-atom statistics."""
    parameters_file = "ligand_brics_fragments.LigandBricsFragmentsStep.parameters.json"
    definition = {
        "protocol_revision": "3.7",
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
            "outputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
        },
        "protocol_version": 3,
        "version": "1.0.0",
        "id": "ligand_brics_fragments",
        "kind": "operator",
        "title": "Ligand BRICS fragments",
        "description": "BRICS decomposition of each molecule with fragment counts and fragment heavy-atom statistics.",
        "category": "Chemistry",
        "icon": "Scissors",
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
            raise StepError("ligand_brics_fragments: a SMILES form input is required")
        form = inputs[0]
        params = ctx.step_params
        molecule_dim = str(params.get("molecule_dim", "molecule") or "molecule")
        field_dim = str(params.get("field_dim", "field") or "field")
        out_name = str(params.get("output", "brics") or "brics")
        if list(form.dims) != [molecule_dim, field_dim]:
            raise StepError(
                "ligand_brics_fragments: expected a form with dims "
                f"[{molecule_dim}, {field_dim}], got {list(form.dims)}"
            )

        try:
            from rdkit.Chem import BRICS
        except ImportError as error:  # pragma: no cover - dependency guard
            raise StepError(f"ligand_brics_fragments: rdkit is required ({error})") from error

        names, _texts, molecules = build_molecules(form, "ligand_brics_fragments", molecule_dim, field_dim)
        rows: list[list[float]] = []
        fragments_per_molecule: list[list[str]] = []
        for molecule in molecules:
            fragments = sorted(BRICS.BRICSDecompose(molecule))
            sizes = [_fragment_heavy_atoms(fragment) for fragment in fragments]
            rows.append(
                [
                    float(len(fragments)),
                    float(len(set(fragments))),
                    float(np.mean(sizes)) if sizes else 0.0,
                    float(max(sizes)) if sizes else 0.0,
                    float(min(sizes)) if sizes else 0.0,
                ]
            )
            fragments_per_molecule.append(fragments)

        out = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=[molecule_dim, "statistic"],
            labels={
                molecule_dim: axis_labels(names, molecule_dim),
                "statistic": {name: position for position, name in enumerate(_STATISTICS)},
            },
            info={
                "missing_code": np.nan,
                "n_molecules": len(molecules),
                "fragments": fragments_per_molecule,
                "fragment_definition": "BRICS bonds with dummy labels retained",
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_molecules": len(molecules),
            "fragments": fragments_per_molecule,
            "statistics": list(_STATISTICS),
        }
        print(f"[ligand_brics_fragments] {len(molecules)} molecules")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
