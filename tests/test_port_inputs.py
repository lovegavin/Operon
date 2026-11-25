"""Port resolution: run data arrives as a form or file_artifact, never a path."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.core import FileArtifact, StepError
from src.reader import read_source
from src.task.step.steps import _port_inputs

PDB = (
    "ATOM      1  N   ALA A   1      11.104   6.134  -6.504  1.00  0.00           N\n"
    "ATOM      2  CA  ALA A   1      11.639   6.071  -5.147  1.00  0.00           C\n"
    "ATOM      3  C   ALA A   1      13.149   6.103  -5.149  1.00  0.00           C\n"
    "END\n"
)
FASTA = ">s1 first\nACGTACGT\n>s2 second\nTTTTGGGG\n"


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_structure_accepts_a_form_and_writes_a_pdb(tmp_path: Path) -> None:
    source = _write(tmp_path / "input.pdb", PDB)
    form = read_source(source, ["atom", "field"], {})
    path = Path(_port_inputs.structure(form, "", "unit"))
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "ATOM" in text and "ALA" in text


def test_structure_accepts_a_file_artifact(tmp_path: Path) -> None:
    source = _write(tmp_path / "model.pdb", PDB)
    artifact = FileArtifact("pdb", {"structure": str(source)}, {})
    assert Path(_port_inputs.structure(artifact, "", "unit")) == source


def test_structure_falls_back_to_the_legacy_path(tmp_path: Path) -> None:
    source = _write(tmp_path / "legacy.pdb", PDB)
    assert _port_inputs.structure(None, str(source), "unit") == str(source)


def test_structure_rejects_a_bare_string_or_object(tmp_path: Path) -> None:
    source = _write(tmp_path / "legacy.pdb", PDB)
    with pytest.raises(StepError, match="structure port expects"):
        _port_inputs.structure(str(source), str(source), "unit")
    with pytest.raises(StepError, match="structure port expects"):
        _port_inputs.structure(object(), str(source), "unit")
    with pytest.raises(StepError, match="a structure port is required"):
        _port_inputs.structure(None, "", "unit")


def test_fasta_accepts_a_form_and_writes_records(tmp_path: Path) -> None:
    source = _write(tmp_path / "input.fasta", FASTA)
    form = read_source(source, ["sequence", "position"], {})
    path = Path(_port_inputs.fasta(form, "", "unit"))
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert text.startswith(">") and "ACGTACGT" in text


def test_fasta_accepts_a_file_artifact(tmp_path: Path) -> None:
    source = _write(tmp_path / "query.fa", FASTA)
    artifact = FileArtifact("fasta", {"query": str(source)}, {})
    assert Path(_port_inputs.fasta(artifact, "", "unit")) == source


def test_fasta_rejects_a_bare_string(tmp_path: Path) -> None:
    source = _write(tmp_path / "query.fa", FASTA)
    with pytest.raises(StepError, match="sequence port expects"):
        _port_inputs.fasta(str(source), str(source), "unit")


def test_file_prefers_the_named_role(tmp_path: Path) -> None:
    trajectory = _write(tmp_path / "run.xtc", "trajectory")
    topology = _write(tmp_path / "system.pdb", PDB)
    artifact = FileArtifact(
        "xtc",
        {"trajectory": str(trajectory), "topology": str(topology)},
        {},
    )
    assert _port_inputs.file(artifact, "", "unit", roles=("topology",)) == str(topology)
    with pytest.raises(StepError, match="carries several files"):
        _port_inputs.file(artifact, "", "unit")


def test_file_rejects_a_bare_string_and_requires_a_port(tmp_path: Path) -> None:
    source = _write(tmp_path / "run.xtc", "trajectory")
    with pytest.raises(StepError, match="file port expects"):
        _port_inputs.file(str(source), str(source), "unit")
    with pytest.raises(StepError, match="a file port is required"):
        _port_inputs.file(None, "", "unit")
