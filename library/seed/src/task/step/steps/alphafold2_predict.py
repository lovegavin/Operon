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


#: Database files of a stock AlphaFold-2 ``data_dir``.
#: The third item marks the hh-suite databases: AlphaFold receives a *prefix* and
#: the checkout appends ``_a3m``/``_cs219``/``_hhm`` itself, so those paths have
#: to be validated through their ``<prefix>_a3m.ffdata`` sidecar.
DATABASES = {
    "uniref90_database_path": ("uniref90", "uniref90.fasta", False),
    "mgnify_database_path": ("mgnify", "mgy_clusters_2022_05.fa", False),
    "pdb70_database_path": ("pdb70", "pdb70", True),
    "uniref30_database_path": ("uniref30", "UniRef30_2021_03", True),
    "bfd_database_path": (
        "bfd",
        "bfd_metaclust_clu_complete_id30_c90_final_seq.sorted_opt",
        True,
    ),
    "small_bfd_database_path": ("small_bfd", "bfd-first_non_consensus_sequences.fasta", False),
    "pdb_seqres_database_path": ("pdb_seqres", "pdb_seqres.txt", False),
    "uniprot_database_path": ("uniprot", "uniprot.fasta", False),
}

#: Names the same database is published under by different mirrors.  The EBI
#: archive unpacks as ``uniprot_sprot.fasta``/``mgy_clusters.fa`` while the
#: Google Cloud archive (and a stock AlphaFold-2 install) use the names above,
#: so both are accepted and the first one that exists wins.
DATABASE_ALIASES = {
    "uniprot_database_path": ("uniprot_sprot.fasta",),
    "mgnify_database_path": ("mgy_clusters.fa",),
}


def database_arguments(
    data_dir,
    preset: str = "full_dbs",
    where: str = "alphafold2_predict",
    model_preset: str = "monomer_ptm",
) -> dict:
    """The ``--*_database_path`` flags a stock checkout requires, derived from ``data_dir``."""

    root = Path(data_dir)
    names = ["uniref90_database_path", "mgnify_database_path"]
    if model_preset == "multimer":
        names.extend(["pdb_seqres_database_path", "uniprot_database_path"])
    if preset == "reduced_dbs":
        names.append("small_bfd_database_path")
    else:
        names.extend(["pdb70_database_path", "uniref30_database_path", "bfd_database_path"])
    arguments = {}
    missing = []
    for name in names:
        folder, filename, prefix = DATABASES[name]
        candidate = root / folder / filename
        if not prefix and not candidate.exists():
            for alias in DATABASE_ALIASES.get(name, ()):
                alternative = root / folder / alias
                if alternative.exists():
                    candidate = alternative
                    break
        if prefix:
            present = (root / folder / f"{filename}_a3m.ffdata").is_file()
        else:
            present = candidate.exists()
        if not present:
            missing.append(str(candidate))
            continue
        arguments[name] = candidate
    mmcif = root / "pdb_mmcif" / "mmcif_files"
    if mmcif.is_dir():
        arguments["template_mmcif_dir"] = mmcif
    obsolete = root / "pdb_mmcif" / "obsolete.dat"
    if obsolete.is_file():
        arguments["obsolete_pdbs_path"] = obsolete
    if missing:
        raise StepError(
            f"{where}: data_dir {root} is missing {len(missing)} database "
            f"item(s) for db_preset {preset}: " + ", ".join(missing[:4])
        )
    return arguments


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
    db_preset: str = "full_dbs",
    run_relax: bool = False,
    use_gpu_relax: bool = False,
) -> list[str]:
    """The ``run_alphafold.py`` invocation a stock checkout accepts.

    A stock checkout exposes no ``--use_gpu`` flag: GPU use is chosen per stage by
    ``--use_gpu_relax``, and every MSA database has to be named explicitly instead
    of being derived from ``--data_dir``.
    """

    databases = database_arguments(data_dir, db_preset, model_preset=preset)
    command = [
        str(python_executable),
        str(runner),
        f"--fasta_paths={fasta}",
        f"--output_dir={output_dir}",
        f"--data_dir={data_dir}",
        f"--model_preset={preset}",
        f"--db_preset={db_preset}",
        f"--max_template_date={max_template_date}",
        "--run_relax=" + ("true" if run_relax else "false"),
        "--use_gpu_relax=" + ("true" if use_gpu_relax else "false"),
    ]
    for name, value in databases.items():
        command.append(f"--{name}={value}")
    return command


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
    db_preset: str = "full_dbs",
    run_relax: bool = False,
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
        db_preset=db_preset,
        run_relax=run_relax,
        use_gpu_relax=use_gpu,
    )
    environment = dict(os.environ)
    binary_dir = str(Path(python_executable).parent)
    environment["PATH"] = binary_dir + os.pathsep + environment.get("PATH", "")
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
        db_preset = str(params.get("db_preset") or "full_dbs")
        if db_preset not in ("full_dbs", "reduced_dbs"):
            raise StepError(
                "alphafold2_predict: db_preset must be full_dbs or reduced_dbs, "
                f"got '{db_preset}'"
            )
        run_relax = bool(params.get("run_relax"))
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
            db_preset=db_preset,
            run_relax=run_relax,
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
