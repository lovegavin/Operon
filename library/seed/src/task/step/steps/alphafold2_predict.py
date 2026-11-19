"""Run a local AlphaFold-2 installation to predict one structure."""

from __future__ import annotations

import json
import os
import pickle
import shutil
import subprocess
from pathlib import Path

from src.core import FileArtifact, StepError
from src.task.step.base import Step
from src.task.step.steps._envpython import environment_python
from src.task.step.steps._native_results import output_directory, remember_native, result_file

PRESETS = ("monomer", "monomer_casp14", "monomer_ptm", "multimer")
DEFAULT_PRESET = "monomer_ptm"
DEFAULT_TEMPLATE_DATE = "2022-01-01"
DEFAULT_TIMEOUT = 3600


def data_directory(params, where: str = "alphafold2_predict") -> Path:
    """Parameter, then ``OPERON_ALPHAFOLD2_DATA``, then the declared resource env."""

    value = str(
        params.get("data_dir")
        or os.environ.get("OPERON_ALPHAFOLD2_DATA")
        or os.environ.get("OPERON_ALPHAFOLD_DATA")
        or ""
    ).strip()
    if not value:
        raise StepError(
            f"{where}: data_dir is required; pass data_dir or export "
            "OPERON_ALPHAFOLD2_DATA with the AlphaFold-2 parameter and MSA database directory"
        )
    path = Path(value).expanduser()
    if not path.is_dir():
        raise StepError(f"{where}: data_dir {path} is not a directory")
    return path


def runner_path(params, where: str = "alphafold2_predict") -> Path:
    """Resolve the ``run_alphafold.py`` entry point of an AlphaFold-2 checkout."""

    value = str(params.get("runner") or "run_alphafold.py").strip()
    candidate = Path(value).expanduser()
    if candidate.is_absolute() or os.sep in value or "/" in value:
        if candidate.is_file():
            return candidate
        raise StepError(f"{where}: runner {candidate} does not exist")
    home = os.environ.get("OPERON_ALPHAFOLD2_HOME") or os.environ.get("OPERON_ALPHAFOLD_HOME") or ""
    if home:
        candidate = Path(home).expanduser() / value
        if candidate.is_file():
            return candidate
    found = shutil.which(value)
    if found:
        return Path(found)
    raise StepError(
        f"{where}: runner '{value}' was not found; point OPERON_ALPHAFOLD2_HOME at an "
        "AlphaFold-2 checkout containing run_alphafold.py or pass an explicit runner path"
    )


def interpreter(params, where: str = "alphafold2_predict") -> str:
    """The Python that runs the checkout: the parameter, else the ``alphafold2`` environment."""

    value = str(params.get("python_executable") or "").strip()
    if value:
        found = shutil.which(value) or (value if Path(value).expanduser().is_file() else "")
        if not found:
            raise StepError(f"{where}: python_executable {value} was not found")
        return found
    resolved = environment_python("alphafold2")
    if resolved:
        return resolved
    raise StepError(
        f"{where}: the 'alphafold2' environment has no interpreter; prepare it (see "
        "docs/large_resources.md) or pass python_executable"
    )


def alphafold_command(
    python_executable,
    runner,
    *,
    fasta,
    output_dir,
    data_dir,
    preset: str = DEFAULT_PRESET,
    max_template_date: str = DEFAULT_TEMPLATE_DATE,
    use_gpu: bool = False,
) -> list[str]:
    """The official non-interactive ``run_alphafold.py`` invocation."""

    return [
        str(python_executable),
        str(runner),
        f"--fasta_paths={fasta}",
        f"--output_dir={output_dir}",
        f"--data_dir={data_dir}",
        f"--model_preset={preset}",
        f"--max_template_date={max_template_date}",
        "--use_gpu=" + ("true" if use_gpu else "false"),
    ]


def ranking_payload(folder) -> dict:
    """Parsed ``ranking_debug.json`` of one prediction, empty when unreadable."""

    path = Path(folder) / "ranking_debug.json"
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def ranked_value(payload: dict, key: str):
    """One scalar of the top-ranked model; the value itself when already a scalar."""

    values = payload.get(key)
    if isinstance(values, dict):
        if not values:
            return ""
        for model in payload.get("order") or []:
            if model in values:
                return values[model]
        return next(iter(values.values()))
    if isinstance(values, (int, float)) and not isinstance(values, bool):
        return values
    return ""


def pickled_plddt(folder):
    """Mean per-residue pLDDT of the first readable ``result_model_*.pkl``."""

    for path in sorted(Path(folder).glob("result_model_*.pkl")):
        try:
            payload = pickle.loads(path.read_bytes())
        except (OSError, EOFError, ImportError, AttributeError, ValueError, TypeError):
            continue
        values = payload.get("plddt") if isinstance(payload, dict) else None
        try:
            numbers = [float(value) for value in values]
        except (TypeError, ValueError):
            continue
        if numbers:
            return sum(numbers) / len(numbers)
    return ""


def read_metrics(folder) -> dict:
    """Mean pLDDT and pTM of the top-ranked model; empty strings when unavailable."""

    payload = ranking_payload(folder)
    plddt = ranked_value(payload, "plddts")
    if plddt == "":
        plddt = pickled_plddt(folder)
    ptm = ranked_value(payload, "ptm")
    if ptm == "":
        ptm = ranked_value(payload, "iptm")
    order = payload.get("order") or []
    return {
        "mean_plddt": plddt,
        "ptm": ptm,
        "best_model": str(order[0]) if order else "",
    }


def locate_prediction(output_dir, fasta, where: str = "alphafold2_predict") -> Path:
    """``ranked_0.pdb`` inside ``<output_dir>/<fasta name>/``."""

    folder = Path(output_dir) / Path(fasta).stem
    ranked = folder / "ranked_0.pdb"
    if ranked.is_file():
        return ranked
    for matches in (sorted(folder.glob("ranked_*.pdb")), sorted(Path(output_dir).rglob("ranked_0.pdb"))):
        if matches:
            return matches[0]
    raise StepError(f"{where}: AlphaFold-2 produced no ranked PDB under {folder}")


def run_prediction(
    fasta,
    *,
    output_dir,
    data_dir,
    runner,
    python_executable,
    preset: str = DEFAULT_PRESET,
    max_template_date: str = DEFAULT_TEMPLATE_DATE,
    use_gpu: bool = False,
    timeout: int = DEFAULT_TIMEOUT,
    where: str = "alphafold2_predict",
) -> dict:
    """Run one prediction and report the ranked model together with its metrics."""

    command = alphafold_command(
        python_executable,
        runner,
        fasta=fasta,
        output_dir=output_dir,
        data_dir=data_dir,
        preset=preset,
        max_template_date=max_template_date,
        use_gpu=use_gpu,
    )
    environment = dict(os.environ)
    if not use_gpu:
        environment["CUDA_VISIBLE_DEVICES"] = ""
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=environment,
        )
    except FileNotFoundError as exc:
        raise StepError(f"{where}: '{python_executable}' could not start the AlphaFold-2 runner: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise StepError(f"{where}: AlphaFold-2 timed out after {timeout} s") from exc
    if completed.returncode != 0:
        tail = (completed.stderr or completed.stdout or "").strip()[-1500:]
        raise StepError(
            f"{where}: AlphaFold-2 failed with exit code {completed.returncode}: {tail}"
        )
    pdb = locate_prediction(output_dir, fasta, where)
    folder = pdb.parent
    ranking = folder / "ranking_debug.json"
    return {
        "pdb": pdb,
        "folder": folder,
        "ranking": ranking if ranking.is_file() else None,
        "command": command,
        **read_metrics(folder),
    }


class Alphafold2PredictStep(Step):
    """Predict one structure with a local AlphaFold-2 checkout."""

    provider = "operon-core"

    parameters_file = "alphafold2_predict.Alphafold2PredictStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
                         'outputs': [{'logical_type': 'file_artifact',
                                      'representations': ['file_artifact'],
                                      'metadata': {}}]},
        "protocol_version": 3,
        "id": "alphafold2_predict",
        "version": "1.0.0",
        "kind": "operator",
        "title": "AlphaFold-2 structure prediction",
        "description": (
            "Predict a protein structure from one FASTA file with a local AlphaFold-2 "
            "installation by calling its run_alphafold.py entry point, then return the "
            "ranked_0 model as a PDB artifact together with the mean pLDDT and pTM that "
            "AlphaFold-2 recorded in ranking_debug.json."
        ),
        "category": "Machine Learning",
        "icon": "Brain",
        "contracts": {
            "version": 1,
            "inputs": [],
            "output": {
                "mode": "declare",
                "schema": {
                    "kind": "file",
                    "numeric": False,
                    "ndim": 0,
                    "dims": [],
                    "info": {"representation": {"type": "string", "const": "pdb"}},
                    "info_open": True,
                },
            },
        },
        "resources": {
            "environment": "alphafold2",
            "memory_modes": ["full"],
            "supports_cuda": True,
            "estimate": "estimate_memory",
        },
        "inputs_arity": 0,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs) -> None:
        params = ctx.step_params
        out_name = str(params.get("output") or "structure")

        fasta_value = str(params.get("fasta_path") or "").strip()
        if not fasta_value:
            raise StepError("alphafold2_predict: fasta_path is required")
        fasta = Path(fasta_value).expanduser()
        if not fasta.is_file():
            raise StepError(f"alphafold2_predict: fasta_path {fasta} is not a file")
        output_value = str(params.get("output_dir") or "").strip()
        if not output_value:
            raise StepError("alphafold2_predict: output_dir is required")
        output_dir = Path(output_value).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)
        preset = str(params.get("model_preset") or DEFAULT_PRESET)
        if preset not in PRESETS:
            raise StepError(
                f"alphafold2_predict: model_preset must be one of {', '.join(PRESETS)}, got '{preset}'"
            )
        template_date = str(params.get("max_template_date") or DEFAULT_TEMPLATE_DATE)
        use_gpu = bool(params.get("use_gpu"))
        timeout = int(params.get("timeout_seconds") or DEFAULT_TIMEOUT)

        result = run_prediction(
            fasta,
            output_dir=output_dir,
            data_dir=data_directory(params),
            runner=runner_path(params),
            python_executable=interpreter(params),
            preset=preset,
            max_template_date=template_date,
            use_gpu=use_gpu,
            timeout=timeout,
        )

        directory = output_directory(ctx, "alphafold2")
        pdb_path = directory / "ranked_0.pdb"
        shutil.copyfile(result["pdb"], pdb_path)
        report = {
            "fasta_path": str(fasta),
            "output_dir": str(output_dir),
            "raw_model": str(result["pdb"]),
            "model_preset": preset,
            "max_template_date": template_date,
            "use_gpu": use_gpu,
            "best_model": result["best_model"],
            "mean_plddt": result["mean_plddt"],
            "ptm": result["ptm"],
        }
        report_path = directory / "result.json"
        report_path.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        result_files = [
            result_file("structure", pdb_path, "pdb", "AlphaFold-2 model"),
            result_file("report", report_path, "json", "AlphaFold-2 prediction report"),
        ]
        remember_native(ctx, out_name, result_files)
        ctx[out_name] = FileArtifact(
            "pdb",
            {"structure": str(pdb_path)},
            info={
                "source": "alphafold2_predict",
                "result_file": str(report_path),
                "model_preset": preset,
                "best_model": result["best_model"],
                "mean_plddt": result["mean_plddt"],
                "ptm": result["ptm"],
            },
        )
        self._export_data = {
            "files": result_files,
            "code": {
                "status": 0,
                "fasta_path": str(fasta),
                "pdb": str(pdb_path),
                "mean_plddt": result["mean_plddt"],
                "ptm": result["ptm"],
                "best_model": result["best_model"],
                "model_preset": preset,
            },
        }
        print(
            f"[alphafold2_predict] {fasta.stem}: rank 1 model {result['best_model'] or 'unknown'}, "
            f"mean pLDDT {result['mean_plddt']}"
        )

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
