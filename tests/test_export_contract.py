"""Export-contract regression tests for native file registration."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

import pytest

from src.core import FileArtifact, Form
from src.task.step.steps.export_results import ExportResultsStep
from src.task.step.steps.msa_trim import MsaTrimStep
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps import esmfold_predict
from src.task.step.steps._sequence_common import encode_sequences

PDB = (
    "ATOM      1  N   MET A   1      11.104  13.207   2.100  1.00 70.00           N\n"
    "ATOM      2  CA  MET A   1      12.560  13.207   2.100  1.00 70.00           C\n"
    "ATOM      3  C   MET A   1      13.000  14.500   2.100  1.00 70.00           C\n"
    "END\n"
)


class FakeModel:
    def infer_pdb(self, sequence: str) -> str:
        return PDB


def test_esmfold_registers_native_and_export_results(tmp_path, monkeypatch):
    monkeypatch.setattr(esmfold_predict, "_load_model", lambda *args, **kwargs: FakeModel())
    form = encode_sequences(["MKV"], "sequence", "position", "protein")
    ctx = Context(tmp_path / "task", {})
    ctx["sequence"] = form
    try:
        run(
            ctx,
            [
                {
                    "name": "esmfold_predict",
                    "inputs": ["sequence"],
                    "params": {"output": "structure", "num_recycles": 1},
                },
                {
                    "name": "export_results",
                    "inputs": ["structure"],
                    "params": {"format": "pdb", "output": "saved"},
                },
            ],
        )
        out = ctx["saved"]
        assert isinstance(out, FileArtifact)
        assert out.format == "exported_files"
        assert out.info["formats"]["file_1"] == "pdb"
        path = Path(out.files["file_1"])
        assert path.is_file()
        assert path.read_text() == PDB
        assert path.is_relative_to(ctx.out_dir)
        report = json.loads((ctx.out_dir / "steps/01_esmfold_predict.json").read_text())
        assert report["result_files"][0]["format"] == "pdb"
        assert Path(report["result_files"][0]["path"]) == path
        # Native text writers use the platform newline convention; the receipt
        # must describe the actual saved artifact, including CRLF on Windows.
        assert report["result_files"][0]["bytes"] == path.stat().st_size
    finally:
        ctx.finalize()

FAKE_BOLTZ = """#!/usr/bin/env python
import json
import os
import shutil
import sys
from pathlib import Path

args = sys.argv[1:]
out = Path(args[args.index("--out_dir") + 1]) / "pred"
out.mkdir(parents=True, exist_ok=True)
shutil.copy(os.environ["OPERON_TEST_PDB"], out / "prediction.pdb")
(out / "confidence_model_0.json").write_text(json.dumps({
    "confidence_score": 0.8, "ptm": 0.5, "iptm": 0.4, "complex_plddt": 0.7,
    "complex_iplddt": 0.6, "complex_pde": 1.0, "chain_pair_iptm": 0.3,
}))
"""


def test_boltz_registers_native_pdb(tmp_path, monkeypatch):
    model = tmp_path / "model.pdb"
    model.write_text(PDB)
    script = tmp_path / "boltz.py"
    script.write_text(FAKE_BOLTZ)
    monkeypatch.setenv("OPERON_TEST_PDB", str(model))
    ctx = Context(tmp_path / "task", {})
    ctx["sequence"] = encode_sequences(["MKV"], "sequence", "position", "protein")
    try:
        run(
            ctx,
            [
                {
                    "name": "boltz_predict",
                    "inputs": ["sequence"],
                    "params": {
                        "output": "structure",
                        "boltz_path": str(script),
                        "msa_mode": "empty",
                        "use_msa_server": False,
                        "device": "cpu",
                        "sampling_steps": 1,
                        "diffusion_samples": 1,
                        "num_workers": 0,
                        "output_format": "pdb",
                    },
                },
                {
                    "name": "export_results",
                    "inputs": ["structure"],
                    "params": {"format": "pdb", "output": "saved"},
                },
            ],
        )
        out = ctx["saved"]
        assert out.info["formats"]["file_1"] == "pdb"
        assert Path(out.files["file_1"]).read_text() == PDB
    finally:
        ctx.finalize()


def test_ligand_pdbqt_registers_native(tmp_path):
    pytest.importorskip("rdkit")
    ctx = Context(tmp_path / "task", {})
    try:
        run(
            ctx,
            [
                {
                    "name": "ligand_pdbqt_prepare",
                    "inputs": [],
                    "params": {"smiles": "CCO", "output": "ligand"},
                },
                {
                    "name": "export_results",
                    "inputs": ["ligand"],
                    "params": {"format": "native", "output": "saved"},
                },
            ],
        )
        out = ctx["saved"]
        assert out.info["formats"]["file_1"] == "pdbqt"
        assert "ROOT" in Path(out.files["file_1"]).read_text()
    finally:
        ctx.finalize()


def test_export_results_fasta_from_sequence_form(tmp_path):
    ctx = Context(tmp_path / "task", {})
    ctx["seq"] = encode_sequences(["MKV", "AC"], "sequence", "position", "protein")
    try:
        run(
            ctx,
            [
                {
                    "name": "export_results",
                    "inputs": ["seq"],
                    "params": {"format": "fasta", "output": "saved"},
                }
            ],
        )
        out = ctx["saved"]
        assert out.info["formats"]["data"] == "fasta"
        content = Path(out.files["data"]).read_text()
        assert "MKV" in content and "AC" in content
    finally:
        ctx.finalize()

class _ExportCtx(dict):
    """Minimal mapping-style task context for direct step invocation."""

    def __init__(self, params, root):
        super().__init__()
        self.step_params = dict(params)
        self.out_dir = Path(root)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts = {}

    def log(self, *args, **kwargs):
        return None


def test_export_results_fasta_from_trimmed_alignment(tmp_path):
    codes = {"A": 0, "C": 1, "G": 2, "T": 3, "-": 5}
    rows = ["A-GT", "ATGT", "ACGT"]
    data = np.asarray([[codes[character] for character in row] for row in rows], dtype=np.float32)
    alignment = Form(
        data,
        dims=["sequence", "position"],
        labels={
            "sequence": {f"s{index}": index for index in range(len(rows))},
            "position": {str(index): index for index in range(len(rows[0]))},
        },
        info={
            "representation": "fasta",
            "sequences": rows,
            "alphabet": "dna",
            "alphabet_map": codes,
        },
    )
    ctx = _ExportCtx({"output": "trimmed", "max_gap_fraction": 0.2}, tmp_path / "task")
    MsaTrimStep().run(ctx, [alignment])
    trimmed = ctx["trimmed"]
    assert trimmed.data.shape == (3, 3)
    assert trimmed.info["sequences"] == ["AGT", "AGT", "AGT"]
    assert trimmed.info["alphabet"] == "dna"

    ctx.step_params = {"format": "fasta", "output": "saved"}
    ExportResultsStep().run(ctx, [trimmed])
    out = ctx["saved"]
    assert out.info["formats"]["data"] == "fasta"
    content = Path(out.files["data"]).read_text()
    assert content.count(">") == 3
    assert ">s0\nAGT" in content
