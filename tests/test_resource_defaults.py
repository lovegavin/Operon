"""Resource defaults must point at the tree the installer actually populates."""
from __future__ import annotations

import json
from pathlib import Path

from src.task.step.steps._protein_common import proteinmpnn_layout

STEPS = Path(__file__).resolve().parents[1] / "library/seed/src/task/step/steps"


def test_proteinmpnn_layout_accepts_a_copied_checkout(tmp_path: Path) -> None:
    (tmp_path / "protein_mpnn_run.py").write_text("", encoding="utf-8")
    root, weights = proteinmpnn_layout(tmp_path)
    assert root == tmp_path
    assert weights == tmp_path / "vanilla_model_weights"


def test_proteinmpnn_layout_accepts_a_linked_checkout(tmp_path: Path) -> None:
    nested = tmp_path / "ProteinMPNN"
    nested.mkdir()
    (nested / "protein_mpnn_run.py").write_text("", encoding="utf-8")
    root, weights = proteinmpnn_layout(tmp_path)
    assert root == nested
    assert weights == nested / "vanilla_model_weights"


def test_proteinmpnn_layout_reports_the_copied_path_when_absent(tmp_path: Path) -> None:
    root, weights = proteinmpnn_layout(tmp_path)
    assert root == tmp_path
    assert weights == tmp_path / "vanilla_model_weights"


def test_alphafold2_probes_match_the_official_bundle_names() -> None:
    manifest = json.loads((STEPS / "resources.json").read_text(encoding="utf-8"))
    entry = next(item for item in manifest["resources"] if item["id"] == "alphafold2")
    files = [str(name) for name in entry["files"]]
    assert "bfd/bfd-first_non_consensus_sequences.fasta" not in files
    assert "mgnify/mgy_clusters.fa" not in files
    assert any(name.startswith("bfd/") and name.endswith(".ffdata") for name in files)
    assert "mgnify/mgy_clusters_2022_05.fa" in files


def test_proteinmpnn_manifest_names_the_weights_it_resolves() -> None:
    manifest = json.loads((STEPS / "resources.json").read_text(encoding="utf-8"))
    entry = next(item for item in manifest["resources"] if item["id"] == "proteinmpnn")
    assert "vanilla_model_weights/v_48_020.pt" in [str(name) for name in entry["files"]]
    assert "protein_mpnn_run.py" in [str(name) for name in entry["files"]]
