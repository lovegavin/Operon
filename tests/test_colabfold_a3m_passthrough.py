import json
from pathlib import Path

import pytest

from src.core.errors import StepError
from src.task.step.steps import colabfold_predict as mod


def _batch(tmp_path: Path) -> Path:
    binary = tmp_path / "colabfold_batch"
    binary.write_text(
        "#!/usr/bin/env python3\n"
        "import pathlib, sys, json\n"
        "out = pathlib.Path(sys.argv[2])\n"
        "out.mkdir(parents=True, exist_ok=True)\n"
        "(out / 'query_unrelaxed_rank_001_model.pdb').write_text('ATOM\\n')\n"
        "(out / 'query_scores_rank_001.json').write_text(json.dumps({'plddt': [90.0]}))\n"
        "pathlib.Path('argv.txt').write_text(' '.join(sys.argv[1:]))\n"
    )
    binary.chmod(0o755)
    return binary


def test_alignment_is_handed_to_the_runner_without_a_search(tmp_path):
    batch = _batch(tmp_path)
    a3m = tmp_path / "design.a3m"
    a3m.write_text(">query\nAAA\n>hit\nAAA\n")

    structure, scores = mod.predict(
        "AAA",
        binary=str(batch),
        workdir=tmp_path,
        msa_a3m=str(a3m),
    )

    argv = (tmp_path / "argv.txt").read_text()
    assert a3m.as_posix() in argv
    assert "--msa-mode" not in argv
    assert structure.is_file()
    assert scores is not None and scores.is_file()


def test_a_missing_alignment_fails_the_step(tmp_path):
    from types import SimpleNamespace

    step = mod.ColabfoldPredictStep.__new__(mod.ColabfoldPredictStep)
    ctx = SimpleNamespace(
        step_params={
            "colabfold_path": str(_batch(tmp_path)),
            "output": "structure",
            "msa_a3m": str(tmp_path / "missing.a3m"),
            "device": "cpu",
        },
        out_dir=tmp_path,
    )
    ctx.__getitem__ = lambda self, key: None
    form = SimpleNamespace(info={})
    inputs = [form]

    # the step reads the sequence from the Form before resolving the alignment
    form.info["sequences"] = ["AAA"]

    with pytest.raises(StepError) as excinfo:
        step.run(ctx, inputs)

    assert "does not exist" in str(excinfo.value)
