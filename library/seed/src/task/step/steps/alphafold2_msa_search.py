"""Multiple sequence alignment search with jackhmmer or hhblits."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from src.core import FileArtifact, StepError
from src.task.step.base import Step
from src.task.step.steps._native_results import output_directory, remember_native, result_file
from src.task.step.steps.alphafold2_predict import data_directory

TOOLS = ("jackhmmer", "hhblits")
JACKHMMER_DATABASE = ("uniref90", "uniref90.fasta")
HHBLITS_DATABASE = ("uniref30", "UniRef30_2021_03", "UniRef30_2021_03_a3m")
DEFAULT_THREADS = 4
DEFAULT_TIMEOUT = 3600


def tool_kind(binary: str) -> str:
    """Which search tool a binary name or path refers to."""

    name = Path(str(binary)).name.lower()
    if "hhblits" in name:
        return "hhblits"
    if "jackhmmer" in name or "hmmer" in name:
        return "jackhmmer"
    return ""


def resolve_tools(requested: str, where: str = "alphafold2_msa_search") -> tuple[str, str]:
    """Absolute path and kind of the search tool, falling back to the other one."""

    name = str(requested or "").strip() or "jackhmmer"
    kind = tool_kind(name)
    if not kind:
        raise StepError(f"{where}: binary must be jackhmmer or hhblits, got '{name}'")
    found = shutil.which(name)
    if found:
        return found, kind
    for alternative in TOOLS:
        if alternative == kind:
            continue
        found = shutil.which(alternative)
        if found:
            return found, alternative
    raise StepError("alphafold2 MSA search requires jackhmmer or hhblits on PATH")


def query_path(
    params, output_dir: Path, where: str = "alphafold2_msa_search"
) -> tuple[Path, str]:
    """FASTA file of the query and its sequence, writing it when only a string was given."""

    fasta_value = str(params.get("fasta_path") or "").strip()
    if fasta_value:
        path = Path(fasta_value).expanduser()
        if not path.is_file():
            raise StepError(f"{where}: fasta_path {path} is not a file")
        return path, read_sequence(path)

    sequence = "".join(str(params.get("sequence") or "").split())
    if not sequence:
        raise StepError(f"{where}: provide sequence or fasta_path")
    path = output_dir / "query.fasta"
    path.write_text(f">query\n{sequence}\n", encoding="utf-8")
    return path, sequence


def read_sequence(path: Path) -> str:
    """Residues of the first FASTA record, empty when the file has no record."""

    residues: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith(">"):
            if residues:
                break
            continue
        residues.append("".join(line.split()))
    return "".join(residues)


def database_path(
    data_dir: Path, kind: str, where: str = "alphafold2_msa_search"
) -> str:
    """Database argument of the search tool."""

    if kind == "hhblits":
        folder = data_dir / HHBLITS_DATABASE[0]
        for prefix in HHBLITS_DATABASE[1:]:
            candidate = folder / prefix
            if Path(f"{candidate}.ffdata").is_file():
                return str(candidate)
        expected = folder / HHBLITS_DATABASE[1]
        raise StepError(
            f"{where}: hhblits needs {expected}.ffdata and {expected}.ffindex under data_dir "
            f"{data_dir}; run operon resources link alphafold2 first"
        )
    database = data_dir / JACKHMMER_DATABASE[0] / JACKHMMER_DATABASE[1]
    if not database.is_file():
        raise StepError(
            f"{where}: jackhmmer needs {database}; run operon resources link alphafold2 first"
        )
    return str(database)


def search_command(
    binary: str,
    kind: str,
    *,
    query: Path,
    database: str,
    alignment: Path,
    threads: int,
) -> list[str]:
    """The non-interactive search invocation for the selected tool."""

    if kind == "hhblits":
        return [
            str(binary),
            "-i",
            str(query),
            "-d",
            str(database),
            "-oa3m",
            str(alignment),
            "-o",
            os.devnull,
            "-cpu",
            str(threads),
            "-n",
            "2",
            "-e",
            "1e-3",
            "-mact",
            "0.35",
            "-maxfilt",
            "100000000",
            "-neffmax",
            "20",
            "-nodiff",
            "-realign_max",
            "100000000",
            "-maxseq",
            "1000000",
        ]
    return [
        str(binary),
        "--cpu",
        str(threads),
        "-N",
        "1",
        "-E",
        "1e-3",
        "--incE",
        "1e-3",
        "-A",
        str(alignment),
        "--noali",
        "-o",
        os.devnull,
        str(query),
        str(database),
    ]


def stockholm_to_a3m(text: str) -> str:
    """Convert a Stockholm alignment to a3m using its ``#=GC RF`` match columns.

    Match columns keep their residue in upper case, insert columns are lower
    cased and gaps in insert columns are dropped. Without an RF annotation every
    column is treated as a match column.
    """

    records: dict[str, list[str]] = {}
    order: list[str] = []
    reference: list[str] = []
    for line in text.splitlines():
        if not line or line.startswith("#"):
            if line.startswith("#=GC RF"):
                parts = line.split(None, 2)
                if len(parts) == 3:
                    reference.extend(parts[2].strip())
            continue
        if line.startswith("//"):
            break
        parts = line.split()
        if len(parts) < 2:
            continue
        name, column = parts[0], parts[1]
        if name not in records:
            records[name] = []
            order.append(name)
        records[name].extend(column)

    width = max((len(value) for value in records.values()), default=0)
    reference.extend("x" * (width - len(reference)))
    rows: list[str] = []
    for name in order:
        column = "".join(records[name])
        column = column + "-" * (width - len(column))
        residues: list[str] = []
        for index, residue in enumerate(column):
            match = reference[index] not in (".", "-") if reference else True
            if match:
                residues.append(residue.upper() if residue != "-" else "-")
            elif residue != "-":
                residues.append(residue.lower())
        rows.append(f">{name}\n{''.join(residues)}\n")
    return "".join(rows)


def a3m_stats(path: Path) -> dict:
    """Sequence count and alignment width of an a3m/FASTA file."""

    sequences: list[int] = []
    current = 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith(">"):
            if current:
                sequences.append(current)
            current = 0
            continue
        current += len("".join(line.split()))
    if current:
        sequences.append(current)
    return {
        "sequences": len(sequences),
        "columns": max(sequences, default=0),
    }


class Alphafold2MsaSearchStep(Step):
    """Build a multiple sequence alignment with jackhmmer or hhblits."""

    provider = "operon-core"

    parameters_file = "alphafold2_msa_search.Alphafold2MsaSearchStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
                         'outputs': [{'logical_type': 'file_artifact',
                                      'representations': ['file_artifact'],
                                      'metadata': {}}]},
        "protocol_version": 3,
        "id": "alphafold2_msa_search",
        "version": "1.0.0",
        "kind": "operator",
        "title": "AlphaFold-2 MSA search",
        "description": (
            "Search the reference databases of an AlphaFold-2 data directory with jackhmmer or "
            "hhblits and return the resulting alignment as an a3m file that a local "
            "AlphaFold-2 run can reuse."
        ),
        "category": "Sequence",
        "icon": "Filter",
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
                    "info": {"representation": {"type": "string", "const": "a3m"}},
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
        out_name = str(params.get("output") or "msa")
        where = "alphafold2_msa_search"

        output_value = str(params.get("output_dir") or "").strip()
        if not output_value:
            raise StepError(f"{where}: output_dir is required")
        output_dir = Path(output_value).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)

        binary, kind = resolve_tools(str(params.get("binary") or "jackhmmer"), where)
        data_dir = data_directory(params, where)
        database = database_path(data_dir, kind, where)
        query, sequence = query_path(params, output_dir, where)
        threads = int(params.get("threads") or DEFAULT_THREADS)
        if threads < 1:
            raise StepError(f"{where}: threads must be at least 1")
        timeout = int(params.get("timeout_seconds") or DEFAULT_TIMEOUT)

        alignment = output_dir / "msa.a3m"
        raw_alignment = output_dir / "msa.sto" if kind == "jackhmmer" else alignment
        command = search_command(
            binary,
            kind,
            query=query,
            database=database,
            alignment=raw_alignment,
            threads=threads,
        )
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=dict(os.environ),
            )
        except FileNotFoundError as exc:
            raise StepError(f"{where}: '{binary}' could not be started: {exc}") from exc
        except subprocess.TimeoutExpired as exc:
            raise StepError(f"{where}: {kind} timed out after {timeout} s") from exc
        if completed.returncode != 0:
            tail = (completed.stderr or completed.stdout or "").strip()[-1500:]
            raise StepError(f"{where}: {kind} failed with exit code {completed.returncode}: {tail}")
        if not raw_alignment.is_file():
            raise StepError(f"{where}: {kind} wrote no alignment to {raw_alignment}")
        if kind == "jackhmmer":
            alignment.write_text(
                stockholm_to_a3m(raw_alignment.read_text(encoding="utf-8", errors="replace")),
                encoding="utf-8",
            )

        statistics = a3m_stats(alignment)
        if not statistics["sequences"]:
            raise StepError(f"{where}: {kind} produced an empty alignment in {alignment}")
        result_files = [
            result_file("alignment", alignment, "a3m", "AlphaFold-2 multiple sequence alignment"),
        ]
        remember_native(ctx, out_name, result_files)
        ctx[out_name] = FileArtifact(
            "a3m",
            {"alignment": str(alignment)},
            info={
                "source": where,
                "tool": kind,
                "database": database,
                "query": str(query),
                "query_length": len(sequence),
                "sequences": statistics["sequences"],
                "columns": statistics["columns"],
            },
        )
        self._export_data = {
            "files": result_files,
            "code": {
                "status": 0,
                "alignment": str(alignment),
                "tool": kind,
                "sequences": statistics["sequences"],
                "columns": statistics["columns"],
                "query_length": len(sequence),
            },
        }
        print(
            f"[{where}] {kind}: {statistics['sequences']} sequences, "
            f"{statistics['columns']} columns for a {len(sequence)} residue query"
        )

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
