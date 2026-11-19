"""Batch AlphaFold-2 structure prediction over a directory of FASTA files."""

from __future__ import annotations

import csv
import os
from pathlib import Path

from src.core import FileArtifact, StepError
from src.task.step.base import Step
from src.task.step.steps._native_results import output_directory, remember_native, result_file
from src.task.step.steps.alphafold2_predict import (
    DEFAULT_PRESET,
    DEFAULT_TEMPLATE_DATE,
    DEFAULT_TIMEOUT,
    PRESETS,
    data_directory,
    interpreter,
    runner_path,
    run_prediction,
)

FASTA_SUFFIXES = (".fasta", ".fa", ".faa", ".fas")

CSV_COLUMNS = ("name", "status", "pdb", "plddt", "error")


def fasta_files(params, where: str = "alphafold2_batch_predict") -> list[Path]:
    """Explicit ``fasta_paths`` plus every FASTA file of ``fasta_dir``."""

    candidates: list[Path] = []
    values = params.get("fasta_paths") or []
    if isinstance(values, str):
        values = [values]
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        path = Path(text).expanduser()
        if not path.is_file():
            raise StepError(f"{where}: fasta_paths entry {path} is not a file")
        if path not in candidates:
            candidates.append(path)

    directory_value = str(params.get("fasta_dir") or "").strip()
    if directory_value:
        directory = Path(directory_value).expanduser()
        if not directory.is_dir():
            raise StepError(f"{where}: fasta_dir {directory} is not a directory")
        for path in sorted(directory.iterdir()):
            if path.is_file() and path.suffix.lower() in FASTA_SUFFIXES and path not in candidates:
                candidates.append(path)

    if not candidates:
        raise StepError(f"{where}: provide fasta_dir or fasta_paths with at least one FASTA file")
    return candidates


def write_summary(path: Path, rows: list[dict]) -> None:
    """Write the per-input report; the header is always present."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in CSV_COLUMNS})


class Alphafold2BatchPredictStep(Step):
    """Predict many structures with one local AlphaFold-2 installation."""

    provider = "operon-core"

    parameters_file = "alphafold2_batch_predict.Alphafold2BatchPredictStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
                         'outputs': [{'logical_type': 'file_artifact',
                                      'representations': ['file_artifact'],
                                      'metadata': {}}]},
        "protocol_version": 3,
        "id": "alphafold2_batch_predict",
        "version": "1.0.0",
        "kind": "operator",
        "title": "AlphaFold-2 batch structure prediction",
        "description": (
            "Run the local AlphaFold-2 run_alphafold.py once per FASTA file of a directory or "
            "list, keep every raw output tree in one output directory and report name, status, "
            "model path, mean pLDDT and error text in summary.csv."
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
                    "info": {"representation": {"type": "string", "const": "csv"}},
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
        out_name = str(params.get("output") or "summary")
        where = "alphafold2_batch_predict"

        fasta_paths = fasta_files(params, where)
        output_value = str(params.get("output_dir") or "").strip()
        if not output_value:
            raise StepError(f"{where}: output_dir is required")
        output_dir = Path(output_value).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)
        preset = str(params.get("model_preset") or DEFAULT_PRESET)
        if preset not in PRESETS:
            raise StepError(f"{where}: model_preset must be one of {', '.join(PRESETS)}, got '{preset}'")
        template_date = str(params.get("max_template_date") or DEFAULT_TEMPLATE_DATE)
        use_gpu = bool(params.get("use_gpu"))
        timeout = int(params.get("timeout_seconds") or DEFAULT_TIMEOUT)
        data_dir = data_directory(params, where)
        runner = runner_path(params, where)
        python_executable = interpreter(params, where)

        rows: list[dict] = []
        for fasta in fasta_paths:
            try:
                result = run_prediction(
                    fasta,
                    output_dir=output_dir,
                    data_dir=data_dir,
                    runner=runner,
                    python_executable=python_executable,
                    preset=preset,
                    max_template_date=template_date,
                    use_gpu=use_gpu,
                    timeout=timeout,
                    where=where,
                )
            except StepError as error:
                rows.append(
                    {
                        "name": fasta.stem,
                        "status": "failed",
                        "pdb": "",
                        "plddt": "",
                        "error": str(error),
                    }
                )
                print(f"[{where}] {fasta.stem}: failed")
                continue
            rows.append(
                {
                    "name": fasta.stem,
                    "status": "ok",
                    "pdb": str(result["pdb"]),
                    "plddt": result["mean_plddt"],
                    "error": "",
                }
            )
            print(f"[{where}] {fasta.stem}: rank 1 mean pLDDT {result['mean_plddt']}")

        summary_path = output_dir / "summary.csv"
        write_summary(summary_path, rows)
        succeeded = sum(1 for row in rows if row["status"] == "ok")
        failed = len(rows) - succeeded
        if not succeeded:
            first_error = rows[0]["error"] if rows else ""
            raise StepError(
                f"{where}: all {len(rows)} predictions failed; see {summary_path}: {first_error}"
            )

        result_files = [
            result_file("summary", summary_path, "csv", "AlphaFold-2 batch summary"),
        ]
        remember_native(ctx, out_name, result_files)
        ctx[out_name] = FileArtifact(
            "csv",
            {"summary": str(summary_path)},
            info={
                "source": where,
                "output_dir": str(output_dir),
                "rows": len(rows),
                "succeeded": succeeded,
                "failed": failed,
                "model_preset": preset,
            },
        )
        self._export_data = {
            "files": result_files,
            "code": {
                "status": 0,
                "summary": str(summary_path),
                "rows": len(rows),
                "succeeded": succeeded,
                "failed": failed,
                "output_dir": str(output_dir),
                "model_preset": preset,
            },
        }

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
