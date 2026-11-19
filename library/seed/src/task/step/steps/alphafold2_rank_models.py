"""Rank AlphaFold-2 models by pLDDT and select the best one."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from src.core import FileArtifact, StepError
from src.task.step.base import Step
from src.task.step.steps._native_results import output_directory, remember_native, result_file

CSV_COLUMNS = ("rank", "name", "plddt", "path", "selected")
SCORE_FIELDS = ("plddt", "mean_plddt", "score")
IGNORED_KEYS = ("plddts", "order", "ptm", "iptm", "max_pae")


def model_files(models_dir, where: str = "alphafold2_rank_models") -> list[Path]:
    """Every PDB model of a file or directory input, excluding a previous ``best.pdb``."""

    path = Path(models_dir).expanduser()
    if path.is_file():
        if path.suffix.lower() != ".pdb":
            raise StepError(f"{where}: models_dir file {path} is not a PDB file")
        return [path]
    if not path.is_dir():
        raise StepError(f"{where}: models_dir {path} is neither a directory nor a PDB file")
    models = [
        candidate
        for candidate in sorted(path.rglob("*.pdb"))
        if candidate.is_file() and candidate.name != "best.pdb"
    ]
    if not models:
        raise StepError(f"{where}: no PDB model found under {path}")
    return models


def score_table(scores_json) -> dict[str, float]:
    """Model name to pLDDT mapping from the shapes ``ranking_debug.json`` and friends use."""

    path = Path(scores_json).expanduser()
    if not path.is_file():
        raise StepError(f"alphafold2_rank_models: scores_json {path} is not a file")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise StepError(f"alphafold2_rank_models: scores_json {path} is not valid JSON: {error}") from error

    table: dict[str, float] = {}

    def add(name, value) -> None:
        if name is None:
            return
        try:
            table[str(name)] = float(value)
        except (TypeError, ValueError):
            return

    if isinstance(payload, dict):
        ranked = payload.get("plddts")
        if isinstance(ranked, dict):
            for name, value in ranked.items():
                add(name, value)
        elif isinstance(ranked, list) and isinstance(payload.get("order"), list):
            for name, value in zip(payload["order"], ranked):
                add(name, value)
        for name, value in payload.items():
            if name in IGNORED_KEYS:
                continue
            if isinstance(value, dict):
                for field in SCORE_FIELDS:
                    if field in value:
                        add(name, value[field])
                        break
            else:
                add(name, value)
    elif isinstance(payload, list):
        for row in payload:
            if not isinstance(row, dict):
                continue
            name = row.get("name") or row.get("model") or row.get("file")
            for field in SCORE_FIELDS:
                if field in row:
                    add(name, row[field])
                    break
    if not table:
        raise StepError(f"alphafold2_rank_models: scores_json {path} holds no pLDDT value")
    return table


def score_for(model: Path, table: dict[str, float]) -> float | str:
    """pLDDT of a model file, matched by name because scores and files rarely share a stem."""

    stem = model.stem
    for key in (stem, model.name, str(model)):
        if key in table:
            return table[key]
    for key, value in table.items():
        if key and (key in stem or stem in key):
            return value
    return ""


def mean_plddt(model: Path) -> float:
    """Mean B-factor of the C-alpha atoms, falling back to every atom."""

    try:
        lines = model.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return 0.0
    alpha: list[float] = []
    every: list[float] = []
    for line in lines:
        if not line.startswith(("ATOM  ", "HETATM")):
            continue
        try:
            value = float(line[60:66])
        except (ValueError, IndexError):
            continue
        every.append(value)
        if line[12:16].strip() == "CA":
            alpha.append(value)
    values = alpha or every
    if not values:
        return 0.0
    return sum(values) / len(values)


def write_ranking(path: Path, rows: list[dict]) -> None:
    """Write the ranking table; the header is always present."""

    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [",".join(CSV_COLUMNS)]
    for row in rows:
        values = []
        for column in CSV_COLUMNS:
            text = str(row.get(column, ""))
            if "," in text or '"' in text:
                text = '"' + text.replace('"', '""') + '"'
            values.append(text)
        lines.append(",".join(values))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class Alphafold2RankModelsStep(Step):
    """Rank AlphaFold-2 models by pLDDT and copy the best one."""

    provider = "operon-core"

    parameters_file = "alphafold2_rank_models.Alphafold2RankModelsStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
                         'outputs': [{'logical_type': 'file_artifact',
                                      'representations': ['file_artifact'],
                                      'metadata': {}}]},
        "protocol_version": 3,
        "id": "alphafold2_rank_models",
        "version": "1.0.0",
        "kind": "operator",
        "title": "AlphaFold-2 model ranking",
        "description": (
            "Rank the PDB models of one AlphaFold-2 output directory by pLDDT, copy the best "
            "model as best.pdb and report every candidate with rank, name, pLDDT and whether it "
            "was selected."
        ),
        "category": "Structure",
        "icon": "ArrowsDownUp",
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
            "supports_cuda": False,
            "estimate": "estimate_memory",
        },
        "inputs_arity": 0,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs) -> None:
        params = ctx.step_params
        out_name = str(params.get("output") or "best")
        where = "alphafold2_rank_models"

        value = str(params.get("models_dir") or "").strip()
        if not value:
            raise StepError(f"{where}: models_dir is required")
        models = model_files(value, where)

        scores_value = str(params.get("scores_json") or "").strip()
        table = score_table(scores_value) if scores_value else {}

        rows: list[dict] = []
        for model in models:
            score = score_for(model, table) if table else ""
            if score == "":
                score = mean_plddt(model)
            rows.append({"name": model.stem, "plddt": score, "path": str(model)})
        rows.sort(key=lambda row: (row["plddt"], row["name"]), reverse=True)
        for index, row in enumerate(rows, start=1):
            row["rank"] = index
            row["selected"] = "yes" if index == 1 else "no"

        best = Path(rows[0]["path"])
        directory = output_directory(ctx, "alphafold2")
        best_path = directory / "best.pdb"
        shutil.copyfile(best, best_path)
        ranking_path = directory / "ranking.csv"
        write_ranking(ranking_path, rows)

        result_files = [
            result_file("structure", best_path, "pdb", "Best AlphaFold-2 model"),
            result_file("ranking", ranking_path, "csv", "AlphaFold-2 model ranking"),
        ]
        remember_native(ctx, out_name, result_files)
        ctx[out_name] = FileArtifact(
            "pdb",
            {"structure": str(best_path)},
            info={
                "source": where,
                "model": rows[0]["name"],
                "raw_model": str(best),
                "mean_plddt": rows[0]["plddt"],
                "candidates": len(rows),
                "ranking_file": str(ranking_path),
                "scores_json": scores_value,
            },
        )
        self._export_data = {
            "files": result_files,
            "code": {
                "status": 0,
                "best": str(best_path),
                "ranking": str(ranking_path),
                "model": rows[0]["name"],
                "mean_plddt": rows[0]["plddt"],
                "candidates": len(rows),
            },
        }
        print(
            f"[{where}] {rows[0]['name']}: rank 1 of {len(rows)} with mean pLDDT "
            f"{rows[0]['plddt']}"
        )

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
