"""AlphaFold-2 operators: stub runner, model ranking, MSA tooling, declarations.

The suite never touches a real AlphaFold-2 installation. A stub ``run_alphafold.py``
records the arguments it receives, so the tests can assert the command the operator
builds; a stub ``jackhmmer`` covers the alignment conversion; the ranking operator is
pure Python.
"""

from __future__ import annotations

import csv
import json
import sys
from io import StringIO
from pathlib import Path

import pytest

from src.core import FileArtifact, StepError
from src.task.step.steps.alphafold2_batch_predict import Alphafold2BatchPredictStep
from src.task.step.steps.alphafold2_msa_search import Alphafold2MsaSearchStep
from src.task.step.steps.alphafold2_predict import Alphafold2PredictStep
from src.task.step.steps.alphafold2_rank_models import Alphafold2RankModelsStep
from src.task.step.steps import _resources_common as common

ROOT = Path(__file__).resolve().parents[1]
OPERATOR_ROOT = ROOT / "library" / "seed"
OPERATOR_DIR = OPERATOR_ROOT / "src" / "task" / "step" / "steps"
OPERATORS = {
    "alphafold2_predict": "Alphafold2PredictStep",
    "alphafold2_batch_predict": "Alphafold2BatchPredictStep",
    "alphafold2_msa_search": "Alphafold2MsaSearchStep",
    "alphafold2_rank_models": "Alphafold2RankModelsStep",
}

PREDICTION_PDB = (
    "ATOM      1  CA  ALA A   1      11.104   6.134  -6.504  1.00 86.25           C\n"
    "END\n"
)

STUB_RUNNER = '''\
import json
import sys
from pathlib import Path

arguments = {}
for value in sys.argv[1:]:
    key, _, item = value.partition("=")
    arguments[key.lstrip("-")] = item

output = Path(arguments["output_dir"])
folder = output / Path(arguments["fasta_paths"]).stem
folder.mkdir(parents=True, exist_ok=True)
(folder / "ranked_0.pdb").write_text(
    "ATOM      1  CA  ALA A   1      11.104   6.134  -6.504  1.00 86.25           C\\nEND\\n",
    encoding="utf-8",
)
(folder / "ranking_debug.json").write_text(
    json.dumps(
        {
            "order": ["model_1_ptm_pred_0"],
            "plddts": {"model_1_ptm_pred_0": 86.25},
            "ptm": 0.79,
            "iptm": 0.0,
        }
    ),
    encoding="utf-8",
)
(output / "arguments.json").write_text(json.dumps(arguments, indent=2), encoding="utf-8")
'''

STUB_JACKHMMER = '''\
import sys
from pathlib import Path

target = Path(sys.argv[sys.argv.index("-A") + 1])
target.write_text(
    "# STOCKHOLM 1.0\\n"
    "query             MKTAY-\\n"
    "hit1              MKTAWY\\n"
    "#=GC RF           xxxxx.\\n"
    "//\\n",
    encoding="utf-8",
)
'''


class Ctx:
    """Minimal step context with one parameter dict and one artifact directory."""

    def __init__(self, directory: Path, params: dict) -> None:
        self.step_params = {"output": "out", **params}
        self.task_dir = directory
        self.artifacts: dict = {}
        self.outputs: dict = {}

    def __setitem__(self, key, value) -> None:
        self.outputs[key] = value

    def __getitem__(self, key):
        return self.outputs[key]


def _execute(step, directory: Path, **params):
    ctx = Ctx(directory, params)
    step.run(ctx, [])
    return ctx, ctx[ctx.step_params["output"]]


def _pdb(plddt: float) -> str:
    head = "ATOM      1  CA  ALA A   1      11.104   6.134  -6.504  1.00"
    assert len(head) == 60
    return head + f"{plddt:6.2f}" + "           C\nEND\n"


@pytest.fixture()
def checkout(tmp_path):
    """A fake AlphaFold-2 checkout plus the uniref90 database the MSA step needs."""

    home = tmp_path / "checkout"
    home.mkdir()
    (home / "run_alphafold.py").write_text(STUB_RUNNER, encoding="utf-8")
    data = tmp_path / "data"
    (data / "uniref90").mkdir(parents=True)
    (data / "uniref90" / "uniref90.fasta").write_text(">query\nMKTAY\n", encoding="utf-8")
    return {"home": home, "data": data}


def test_alphafold2_predict_returns_the_ranked_model(tmp_path, monkeypatch, checkout):
    fasta = tmp_path / "query.fasta"
    fasta.write_text(">query\nMKTAYIAKQR\n", encoding="utf-8")
    output = tmp_path / "af2"
    monkeypatch.setenv("OPERON_ALPHAFOLD2_HOME", str(checkout["home"]))

    ctx, artifact = _execute(
        Alphafold2PredictStep(),
        tmp_path,
        fasta_path=str(fasta),
        output_dir=str(output),
        data_dir=str(checkout["data"]),
        python_executable=sys.executable,
        timeout_seconds=120,
    )

    assert isinstance(artifact, FileArtifact)
    assert artifact.format == "pdb"
    structure = Path(artifact.files["structure"])
    assert structure.name == "ranked_0.pdb"
    assert structure.is_file()
    assert artifact.info["mean_plddt"] == pytest.approx(86.25)
    assert artifact.info["ptm"] == pytest.approx(0.79)
    assert artifact.info["best_model"] == "model_1_ptm_pred_0"

    arguments = json.loads((output / "arguments.json").read_text(encoding="utf-8"))
    assert arguments["fasta_paths"] == str(fasta)
    assert arguments["output_dir"] == str(output)
    assert arguments["data_dir"] == str(checkout["data"])
    assert arguments["model_preset"] == "monomer_ptm"
    assert arguments["max_template_date"] == "2022-01-01"
    assert arguments["use_gpu"] == "false"

    report = json.loads(Path(artifact.info["result_file"]).read_text(encoding="utf-8"))
    assert report["model_preset"] == "monomer_ptm"
    assert report["use_gpu"] is False
    assert report["mean_plddt"] == pytest.approx(86.25)
    assert [item["id"] for item in ctx.artifacts["native_results"]["out"]["files"]] == [
        "structure",
        "report",
    ]


def test_alphafold2_predict_forwards_non_default_models(tmp_path, monkeypatch, checkout):
    fasta = tmp_path / "query.fasta"
    fasta.write_text(">query\nMKTAYIAKQR\n", encoding="utf-8")
    output = tmp_path / "af2"
    monkeypatch.setenv("OPERON_ALPHAFOLD2_HOME", str(checkout["home"]))

    _, artifact = _execute(
        Alphafold2PredictStep(),
        tmp_path,
        fasta_path=str(fasta),
        output_dir=str(output),
        data_dir=str(checkout["data"]),
        runner="run_alphafold.py",
        model_preset="multimer",
        max_template_date="2020-05-14",
        use_gpu=True,
        python_executable=sys.executable,
        timeout_seconds=120,
    )

    arguments = json.loads((output / "arguments.json").read_text(encoding="utf-8"))
    assert arguments["model_preset"] == "multimer"
    assert arguments["max_template_date"] == "2020-05-14"
    assert arguments["use_gpu"] == "true"
    report = json.loads(Path(artifact.info["result_file"]).read_text(encoding="utf-8"))
    assert report["max_template_date"] == "2020-05-14"
    assert report["use_gpu"] is True


def test_alphafold2_predict_without_data_dir_names_the_variable(
    tmp_path, monkeypatch, checkout
):
    fasta = tmp_path / "query.fasta"
    fasta.write_text(">query\nMKTAYIAKQR\n", encoding="utf-8")
    monkeypatch.setenv("OPERON_ALPHAFOLD2_HOME", str(checkout["home"]))
    monkeypatch.delenv("OPERON_ALPHAFOLD2_DATA", raising=False)
    monkeypatch.delenv("OPERON_ALPHAFOLD_DATA", raising=False)

    with pytest.raises(StepError, match="OPERON_ALPHAFOLD2_DATA"):
        _execute(
            Alphafold2PredictStep(),
            tmp_path,
            fasta_path=str(fasta),
            output_dir=str(tmp_path / "af2"),
            python_executable=sys.executable,
        )


def test_alphafold2_batch_predict_writes_a_summary(tmp_path, monkeypatch, checkout):
    fasta_dir = tmp_path / "fastas"
    fasta_dir.mkdir()
    (fasta_dir / "alpha.fasta").write_text(">alpha\nMKTAY\n", encoding="utf-8")
    (fasta_dir / "beta.fasta").write_text(">beta\nMKTAY\n", encoding="utf-8")
    extra = tmp_path / "gamma.fa"
    extra.write_text(">gamma\nMKTAY\n", encoding="utf-8")
    output = tmp_path / "batch"
    monkeypatch.setenv("OPERON_ALPHAFOLD2_HOME", str(checkout["home"]))

    _, artifact = _execute(
        Alphafold2BatchPredictStep(),
        tmp_path,
        fasta_dir=str(fasta_dir),
        fasta_paths=[str(extra)],
        output_dir=str(output),
        data_dir=str(checkout["data"]),
        python_executable=sys.executable,
        timeout_seconds=120,
    )

    assert artifact.format == "csv"
    summary = output / "summary.csv"
    assert Path(artifact.files["summary"]) == summary
    rows = list(csv.DictReader(StringIO(summary.read_text(encoding="utf-8"))))
    # explicit fasta_paths come first, then the directory in sorted order
    assert [row["name"] for row in rows] == ["gamma", "alpha", "beta"]
    assert {row["status"] for row in rows} == {"ok"}
    assert all(Path(row["pdb"]).is_file() for row in rows)
    assert artifact.info["succeeded"] == 3
    assert artifact.info["failed"] == 0


def test_alphafold2_rank_models_selects_the_best_plddt(tmp_path):
    models = tmp_path / "models"
    models.mkdir()
    for name, plddt in (("model_a", 41.5), ("model_b", 88.25), ("model_c", 62.0)):
        (models / f"{name}.pdb").write_text(_pdb(plddt), encoding="utf-8")

    _, artifact = _execute(Alphafold2RankModelsStep(), tmp_path, models_dir=str(models))

    assert artifact.format == "pdb"
    best = Path(artifact.files["structure"])
    assert best.name == "best.pdb"
    assert best.parent != models
    assert best.read_text(encoding="utf-8") == _pdb(88.25)
    assert not (models / "best.pdb").exists()
    assert artifact.info["model"] == "model_b"
    assert artifact.info["mean_plddt"] == pytest.approx(88.25)
    assert artifact.info["candidates"] == 3

    ranking = best.parent / "ranking.csv"
    rows = list(csv.DictReader(StringIO(ranking.read_text(encoding="utf-8"))))
    assert [row["name"] for row in rows] == ["model_b", "model_c", "model_a"]
    assert [row["rank"] for row in rows] == ["1", "2", "3"]
    assert [row["selected"] for row in rows] == ["yes", "no", "no"]
    assert artifact.info["ranking_file"] == str(ranking)


def test_alphafold2_rank_models_prefers_the_scores_json(tmp_path):
    models = tmp_path / "models"
    models.mkdir()
    for name, plddt in (("model_a", 41.5), ("model_b", 88.25), ("model_c", 62.0)):
        (models / f"{name}.pdb").write_text(_pdb(plddt), encoding="utf-8")
    scores = tmp_path / "ranking_debug.json"
    scores.write_text(
        json.dumps(
            {
                "order": ["model_a_pred"],
                "plddts": {"model_a_pred": 99.0, "model_b_pred": 80.0},
            }
        ),
        encoding="utf-8",
    )

    _, artifact = _execute(
        Alphafold2RankModelsStep(),
        tmp_path,
        models_dir=str(models),
        scores_json=str(scores),
    )

    assert artifact.info["model"] == "model_a"
    rows = list(
        csv.DictReader(
            StringIO(Path(artifact.info["ranking_file"]).read_text(encoding="utf-8"))
        )
    )
    assert [row["name"] for row in rows] == ["model_a", "model_b", "model_c"]


def test_alphafold2_msa_search_requires_a_search_tool(tmp_path, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda *args, **kwargs: None)

    with pytest.raises(StepError, match="requires jackhmmer or hhblits"):
        _execute(
            Alphafold2MsaSearchStep(),
            tmp_path,
            sequence="MKTAY",
            output_dir=str(tmp_path / "msa"),
            data_dir=str(tmp_path / "data"),
        )


def test_alphafold2_msa_search_converts_stockholm_to_a3m(tmp_path, checkout):
    binary = tmp_path / "bin" / "jackhmmer"
    binary.parent.mkdir()
    binary.write_text(f"#!{sys.executable}\n" + STUB_JACKHMMER, encoding="utf-8")
    binary.chmod(0o755)

    _, artifact = _execute(
        Alphafold2MsaSearchStep(),
        tmp_path,
        sequence="MKTAY",
        output_dir=str(tmp_path / "msa"),
        data_dir=str(checkout["data"]),
        binary=str(binary),
        threads=2,
        timeout_seconds=60,
    )

    assert artifact.format == "a3m"
    alignment = Path(artifact.files["alignment"])
    assert alignment.name == "msa.a3m"
    text = alignment.read_text(encoding="utf-8")
    assert ">query\nMKTAY\n" in text
    assert ">hit1\nMKTAWy\n" in text
    assert artifact.info["tool"] == "jackhmmer"
    assert artifact.info["sequences"] == 2


def test_the_four_operators_declare_the_alphafold2_environment():
    from operon_sdk.declarations import compile_declaration, source_declarations

    for operator_id, class_name in OPERATORS.items():
        path = OPERATOR_DIR / f"{operator_id}.py"
        module = f"src.task.step.steps.{operator_id}"
        declarations = source_declarations(path, module)
        assert [value["id"] for value in declarations] == [operator_id]
        assert declarations[0]["entry_point"].endswith(f":{class_name}")

        descriptor = compile_declaration(declarations[0], OPERATOR_ROOT)
        assert descriptor["kind"] == "operator"
        assert descriptor["resources"]["environment"] == "alphafold2"
        assert descriptor["output_parameter"] == "output"
        assert descriptor["inputs_arity"] == 0
        assert descriptor["parameters_schema"]["type"] == "object"


def test_environment_metadata_lists_the_alphafold2_family():
    assignments = json.loads(
        (ROOT / "library/seed/operon/environment_assignments.json").read_text(
            encoding="utf-8"
        )
    )
    for operator_id in OPERATORS:
        assert assignments["operators"][operator_id] == "alphafold2"

    environments = json.loads(
        (ROOT / "library/seed/operon/environments.json").read_text(encoding="utf-8")
    )
    card = environments["environments"]["alphafold2"]
    assert card["planned"] is False
    assert card["requirements"] == ["numpy"]
    assert card["imports"] == []
    assert "afdb" in card["notes"]

    resources = json.loads(
        (OPERATOR_DIR / "resources.json").read_text(encoding="utf-8")
    )
    record = next(item for item in resources["resources"] if item["id"] == "alphafold2")
    assert record["env"] == "OPERON_ALPHAFOLD_DATA"
    assert len(record["units"]) == 1
    assert len(record["units"][0]["files"]) == 18
    resource = common.load_resources(OPERATOR_DIR / "resources.json")["alphafold2"]
    assert len(common.expected_files(resource)) == 18
