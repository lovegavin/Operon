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

def test_proteinmpnn_unit_files_are_root_relative() -> None:
    manifest = json.loads((STEPS / "resources.json").read_text(encoding="utf-8"))
    entry = next(item for item in manifest["resources"] if item["id"] == "proteinmpnn")
    unit = next(item for item in entry["units"] if item["name"] == "ProteinMPNN")
    files = [
        str(item.get("path") or item.get("name")) if isinstance(item, dict) else str(item)
        for item in unit["files"]
    ]
    assert files and all(not path.startswith("ProteinMPNN/") for path in files)
    assert entry["link_root"] == ""

def test_proteinmpnn_falls_back_to_the_installed_resource(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("OPERON_PROTEINMPNN_PATH", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    root = tmp_path / ".local" / "share" / "operon" / "resources" / "proteinmpnn"
    (root / "vanilla_model_weights").mkdir(parents=True)
    (root / "protein_mpnn_run.py").write_text("", encoding="utf-8")
    (root / "vanilla_model_weights" / "v_48_020.pt").write_text("", encoding="utf-8")
    from src.task.step.steps._protein_common import resolve_proteinmpnn_path

    assert resolve_proteinmpnn_path("") == root
    assert resolve_proteinmpnn_path(str(tmp_path / "explicit")) == tmp_path / "explicit"
