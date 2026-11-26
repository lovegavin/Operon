"""Single-design reads and bridge artifact relocation for the design chain."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from operon import environments
from operon.env_worker import Context as WorkerContext
from src.core import StepError
from src.core.forms import Form
from src.reader import read_source
from src.task.step.steps import _port_inputs
from src.task.step.steps._protein_common import design_frame

FIELDS = {"x": 0, "y": 1, "z": 2, "residue_number": 3}


def _design_form() -> Form:
    data = np.zeros((2, 3, 4), dtype=np.float32)
    data[0, :, 0] = [0.0, 1.0, 2.0]
    data[1, :, 0] = [9.0, 10.0, 11.0]
    data[0, :, 1] = [0.0, 1.0, 2.0]
    data[1, :, 1] = [9.0, 10.0, 11.0]
    data[:, :, 3] = 17
    labels = {
        "design": {"design1": 0, "design2": 1},
        "atom": {"atom1": 0, "atom2": 1, "atom3": 2},
        "field": dict(FIELDS),
    }
    return Form(data=data, dims=["design", "atom", "field"], labels=labels, info={"n_designs": 2})


def test_design_frame_selects_one_design() -> None:
    form = _design_form()

    chosen = design_frame(form, design_index=2)

    assert chosen.dims == ["atom", "field"]
    assert np.allclose(chosen.data, form.data[1])
    assert set(chosen.labels) == {"atom", "field"}
    assert chosen.info["n_designs"] == 2


def test_design_frame_requires_an_explicit_design() -> None:
    form = _design_form()

    with pytest.raises(StepError, match="carries 2 designs"):
        design_frame(form)
    with pytest.raises(StepError, match="outside the 2 design"):
        design_frame(form, design_index=3)


def test_design_frame_leaves_a_single_structure_alone() -> None:
    form = Form(data=np.zeros((3, 4), dtype=np.float32), dims=["atom", "field"],
                labels={"atom": {"atom1": 0, "atom2": 1, "atom3": 2}, "field": dict(FIELDS)})

    assert design_frame(form) is form


_PDB = (
    "ATOM      1  N   ALA A   1      11.104   6.134  -6.504  1.00  0.00           N\n"
    "ATOM      2  CA  ALA A   1      11.639   6.071  -5.147  1.00  0.00           C\n"
    "END\n"
)


def _stacked_form(tmp_path: Path) -> Form:
    source = tmp_path / "design.pdb"
    source.write_text(_PDB, encoding="utf-8")
    one = read_source(source, ["atom", "field"], {})
    second = np.array(one.data, dtype=float)
    second[:, one.labels["field"]["x"]] += 50.0
    labels = {"design": {"design1": 0, "design2": 1},
              "atom": dict(one.labels["atom"]), "field": dict(one.labels["field"])}
    return Form(data=np.stack([one.data, second], axis=0),
                dims=["design", "atom", "field"], labels=labels, info=dict(one.info))


def test_structure_port_writes_the_chosen_design(tmp_path: Path) -> None:
    form = _stacked_form(tmp_path)

    path = Path(_port_inputs.structure(form, "", "unit", design_index=2))

    text = path.read_text(encoding="utf-8")
    assert text.count("ATOM") == 2
    assert "  61.104" in text and "  61.639" in text
    assert "  11.104" not in text


def test_bridge_export_relocates_native_files(tmp_path: Path) -> None:
    bridge = tmp_path / "envbridge-abc"
    native = bridge / "rfdiffusion" / "run" / "design_0.pdb"
    native.parent.mkdir(parents=True)
    native.write_text("END\n", encoding="utf-8")
    outside = tmp_path / "elsewhere.pdb"
    outside.write_text("END\n", encoding="utf-8")
    export = {"result_files": [{"id": "design-0", "path": str(native),
                                "filename": "design_0.pdb", "format": "pdb"},
                               {"id": "keep", "path": str(outside), "format": "pdb"}]}

    moved = environments._relocate_export(export, bridge, artifacts_root=tmp_path / "artifacts")

    entry = moved["result_files"][0]
    destination = Path(entry["path"])
    assert destination.is_file()
    assert (tmp_path / "artifacts") in destination.parents
    assert entry["filename"] == destination.name
    assert moved["result_files"][1]["path"] == str(outside)


def test_worker_artifact_path_targets_the_task_artifact_root(tmp_path: Path) -> None:
    context = WorkerContext({"output": "designs"}, str(tmp_path / "bridge"),
                            str(tmp_path / "artifacts"))

    target = context.artifact_path("rfdiffusion/run-1/design_0.pdb")

    assert target.parent.is_dir()
    assert (tmp_path / "artifacts") in target.parents
    with pytest.raises(ValueError, match="escapes"):
        context.artifact_path("../outside.txt")


def test_structure_writer_keeps_blank_pdb_markers(tmp_path):
    """PDB markers such as altloc and insertion code must stay blank."""

    from src.task.step.steps import _protein_common

    source = tmp_path / "markers.pdb"
    source.write_text(
        "ATOM      1  N   ALA A   1      11.104   6.134  -6.504  1.00  0.00           N\n"
        "ATOM      2  CA  ALA A   1      11.639   6.071  -5.147  1.00  0.00           C\n"
        "END\n"
    )
    form = read_source(source, ["atom", "field"], {"atom": "auto", "field": "builtin"})
    target = tmp_path / "rewritten.pdb"
    _protein_common.write_structure_pdb(form, "atom", "field", target, "unit")
    lines = [line for line in target.read_text().splitlines() if line.startswith("ATOM")]
    assert lines, "the writer produced no ATOM lines"
    for line in lines:
        assert line[16] != "_", line
        assert line[26] != "_", line
        assert line[21] == "A", line
        assert line[22:26].strip().isdigit(), line


def test_stacked_designs_keep_the_reader_encoders(tmp_path: Path) -> None:
    from src.task.step.steps import rfdiffusion_design as designer
    from src.task.step.steps._protein_common import write_structure_pdb

    pdb = tmp_path / "design_0.pdb"
    pdb.write_text(
        "ATOM      1  N   ALA A   1      11.104   6.134  -6.504  1.00  0.00           N\n"
        "ATOM      2  CA  ALA A   1      11.639   6.071  -5.147  1.00  0.00           C\n"
        "END\n"
    )
    second = tmp_path / "design_1.pdb"
    second.write_text(pdb.read_text().replace("  11.104", "  61.104").replace("  11.639", "  61.639"))
    data, labels, extra = designer.stack_designs([pdb, second])
    assert data.shape == (2, 2, 12)
    assert extra["encoders"], "the stacked table dropped the reader encoders"
    stack = Form(data=data, dims=["design", "atom", "field"], labels=labels,
                 info={"designs": extra["designs"], "encoders": extra["encoders"]}, axis_info={})
    target = write_structure_pdb(stack, "atom", "field", tmp_path / "out.pdb", "probe", design_index=2)
    lines = [line for line in target.read_text().splitlines() if line.startswith("ATOM")]
    assert lines[0][17:20] == "ALA"
    assert lines[0][21] == "A"
    assert "  61.104" in lines[0]
