"""Command assembly for the ColabFold MSA server parameter.

``msa_host`` must reach ``colabfold_batch`` as ``--host-url`` and must be absent
from the command when unset, so the public ColabFold default keeps working.
"""

from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest

from src.core.errors import StepError
from src.task.step.steps.colabfold_predict import msa_databases, msa_host_url, predict

STUB_RUNNER = '''#!/usr/bin/env python
import json
import os
import sys
from pathlib import Path

arguments = sys.argv[1:]
outdir = Path(arguments[1])
outdir.mkdir(parents=True, exist_ok=True)
structure = outdir / "query_unrelaxed_rank_001_alphafold2_ptm_model_1_seed_000.pdb"
structure.write_text(
    "ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 50.00           C\\n",
    encoding="utf-8",
)
scores = outdir / "query_scores_rank_001_alphafold2_ptm_model_1_seed_000.json"
scores.write_text(
    json.dumps({"plddt": [50.0], "ptm": 0.5, "pae": [[0.0]], "max_pae": 0.0}),
    encoding="utf-8",
)
Path(os.environ["OPERON_TEST_CAPTURE"]).write_text(json.dumps(arguments), encoding="utf-8")
'''


def _runner(tmp_path: Path) -> Path:
    path = tmp_path / "fake_colabfold.py"
    path.write_text(STUB_RUNNER, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def _predict(tmp_path: Path, monkeypatch, **kwargs):
    capture = tmp_path / "argv.json"
    monkeypatch.setenv("OPERON_TEST_CAPTURE", str(capture))
    workdir = tmp_path / "work"
    workdir.mkdir()
    structure, scores = predict(
        "ACDEFGHIK",
        binary=str(_runner(tmp_path)),
        workdir=workdir,
        device="cpu",
        **kwargs,
    )
    return json.loads(capture.read_text(encoding="utf-8")), structure, scores


def test_non_empty_msa_host_appends_host_url(tmp_path, monkeypatch) -> None:
    argv, structure, scores = _predict(tmp_path, monkeypatch, msa_host="https://msa.example.org")

    assert structure.is_file()
    assert scores is not None and scores.is_file()
    assert argv[0].endswith("query.fasta")
    assert argv[-2:] == ["--host-url", "https://msa.example.org"]


def test_empty_msa_host_keeps_the_colabfold_default(tmp_path, monkeypatch) -> None:
    argv, _, _ = _predict(tmp_path, monkeypatch)

    assert "--host-url" not in argv


def test_blank_msa_host_is_treated_as_unset() -> None:
    assert msa_host_url("") == ""
    assert msa_host_url("   ") == ""
    assert msa_host_url(None) == ""


def test_msa_host_url_is_returned_unchanged() -> None:
    assert msa_host_url("https://msa.example.org:8443/api") == "https://msa.example.org:8443/api"


@pytest.mark.parametrize(
    "value",
    ["msa.example.org", "ftp://msa.example.org", "https://", "localhost:8080"],
)
def test_non_http_msa_host_is_rejected(value: str) -> None:
    with pytest.raises(StepError, match="msa_host"):
        msa_host_url(value)


def test_invalid_msa_host_never_runs_the_runner(tmp_path, monkeypatch) -> None:
    capture = tmp_path / "argv.json"
    monkeypatch.setenv("OPERON_TEST_CAPTURE", str(capture))
    workdir = tmp_path / "work"
    workdir.mkdir()

    with pytest.raises(StepError, match="msa_host"):
        predict(
            "ACDEFGHIK",
            binary=str(_runner(tmp_path)),
            workdir=workdir,
            device="cpu",
            msa_host="not-a-url",
        )

    assert not capture.exists()


def test_local_databases_are_refused_for_the_batch_runner(tmp_path, monkeypatch) -> None:
    capture = tmp_path / "argv.json"
    monkeypatch.setenv("OPERON_TEST_CAPTURE", str(capture))
    workdir = tmp_path / "work"
    workdir.mkdir()

    with pytest.raises(StepError, match="colabfold_search"):
        predict(
            "ACDEFGHIK",
            binary=str(_runner(tmp_path)),
            workdir=workdir,
            device="cpu",
            db1="/data/msa/uniref30_2302/uniref30_2302_db",
        )

    assert not capture.exists()


def test_single_sequence_runs_ignore_local_databases(tmp_path) -> None:
    root = tmp_path / "msa"
    (root / "uniref30_2302").mkdir(parents=True)
    (root / "uniref30_2302" / "uniref30_2302_db.dbtype").write_text("0", encoding="utf-8")

    assert msa_databases(root, "", "", "single_sequence") == ("", "")


def test_msa_databases_resolves_the_resource_layout(tmp_path) -> None:
    root = tmp_path / "msa"
    uniref = root / "uniref30_2302"
    envdb = root / "colabfold_envdb_202108"
    uniref.mkdir(parents=True)
    envdb.mkdir(parents=True)
    (uniref / "uniref30_2302_db.dbtype").write_text("0", encoding="utf-8")
    (envdb / "colabfold_envdb_202108_db.index").write_text("0", encoding="utf-8")

    first, second = msa_databases(root, "", "", "mmseqs2_uniref_env")

    assert first == str(uniref / "uniref30_2302_db")
    assert second == str(envdb / "colabfold_envdb_202108_db")


def test_msa_databases_explains_a_missing_index(tmp_path) -> None:
    root = tmp_path / "msa"
    (root / "uniref30_2302").mkdir(parents=True)

    with pytest.raises(StepError) as caught:
        msa_databases(root, "", "", "mmseqs2_uniref_env")

    assert "has no .dbtype or .index file" in str(caught.value)
