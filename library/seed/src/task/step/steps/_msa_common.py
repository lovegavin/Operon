"""Assemble a protein MSA from the locally installed ColabFold databases.

The ColabFold sequence databases (UniRef30 and the ColabFold environmental
database) are declared as the ``colabfold_msa`` resource, so a deployment can
download them once and every structure operator that needs an MSA runs without
network access.  The search runs through MMseqs2, which the ``colabfold``
environment provides; when neither the binary nor the databases are present the
caller gets an actionable error instead of a silent empty MSA.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from src.core.errors import StepError
from src.task.step.steps._resources_common import Resource, check_resource, load_resources

RESOURCE_ID = "colabfold_msa"
UNIREF_DB = "uniref30_2302_db"
ENVDB_DB = "colabfold_envdb_202108_db"
_REQUIRED_SUFFIXES = (".dbtype", ".index")


def _resource_roots() -> list[Path]:
    roots: list[Path] = []
    configured = os.environ.get("OPERON_COLABFOLD_MSA", "").strip()
    if configured:
        roots.append(Path(configured).expanduser())
    resource: Resource | None = None
    try:
        resource = load_resources().get(RESOURCE_ID)
    except (StepError, OSError):
        resource = None
    if resource is not None:
        try:
            check = check_resource(resource)
        except (StepError, OSError):
            check = {}
        root = str(check.get("root") or "").strip()
        if root:
            roots.append(Path(root))
        for candidate in resource.roots:
            roots.append(Path(candidate).expanduser())
    roots.append(Path.home() / ".local/share/operon/resources" / RESOURCE_ID)
    seen: set[Path] = set()
    unique: list[Path] = []
    for root in roots:
        resolved = root.expanduser()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(resolved)
    return unique


def _has_database(root: Path, name: str) -> bool:
    base = root / name
    return base.is_file() and all((root / (name + suffix)).is_file() for suffix in _REQUIRED_SUFFIXES)


def database_root() -> tuple[Path, str, str]:
    """Return ``(root, uniref prefix, envdb prefix or '')`` for installed databases."""

    for root in _resource_roots():
        if not _has_database(root, UNIREF_DB):
            continue
        envdb = ENVDB_DB if _has_database(root, ENVDB_DB) else ""
        return root, UNIREF_DB, envdb
    raise StepError(
        "no local MSA database: download the 'colabfold_msa' resource "
        "(UniRef30 + ColabFold environmental database) or link an existing copy"
    )


def _managed_roots() -> list[Path]:
    roots: list[Path] = []
    configured = os.environ.get("OPERON_MANAGED_ROOT", "").strip()
    if configured:
        roots.append(Path(configured).expanduser())
    home = Path.home()
    roots.append(home / "Operon" / "managed-v1")
    roots.append(home / ".operon" / "managed-v1")
    return roots


def mmseqs_binary() -> Path:
    """Locate the MMseqs2 binary (the colabfold environment ships one)."""

    explicit = os.environ.get("OPERON_MMSEQS", "").strip()
    candidates: list[Path] = [Path(explicit)] if explicit else []
    located = shutil.which("mmseqs")
    if located:
        candidates.append(Path(located))
    for managed in _managed_roots():
        candidates.extend(sorted(managed.glob("environments/*/bin/mmseqs")))
        candidates.extend(
            sorted(managed.glob("environments/*/lib/python*/site-packages/colabfold/mmseqs/bin/mmseqs"))
        )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise StepError(
        "mmseqs was not found; add mmseqs2 to the colabfold environment "
        "(conda install -c bioconda mmseqs2) or set OPERON_MMSEQS"
    )


def _run(binary: Path, arguments: list[str], *, timeout: int) -> None:
    try:
        completed = subprocess.run(
            [str(binary)] + arguments,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise StepError(f"mmseqs {arguments[0]} timed out after {timeout} s") from None
    if completed.returncode != 0:
        tail = (completed.stderr or completed.stdout or "").strip().splitlines()[-6:]
        detail = " | ".join(tail) or f"exit {completed.returncode}"
        raise StepError(f"mmseqs {arguments[0]} failed: {detail}")


def build_msa(
    sequence: str,
    workdir: Path,
    *,
    name: str = "query",
    threads: int = 8,
    max_accept: int = 5000,
    timeout: int = 3600,
) -> Path:
    """Search the local UniRef30 database and return the resulting ``.a3m`` file."""

    clean = "".join(residue for residue in str(sequence).upper() if residue.isalpha())
    if not clean:
        raise StepError("MSA assembly needs a non-empty protein sequence")
    root, uniref, _envdb = database_root()
    binary = mmseqs_binary()
    base = Path(workdir) / "msa"
    base.mkdir(parents=True, exist_ok=True)
    query = base / f"{name}.fasta"
    query.write_text(f">{name}\n{clean}\n", encoding="utf-8")
    database = str(root / uniref)
    threads = max(1, int(threads))
    _run(binary, ["createdb", str(query), str(base / "qdb")], timeout=timeout)
    _run(
        binary,
        [
            "search",
            str(base / "qdb"),
            database,
            str(base / "res"),
            str(base / "tmp"),
            "-s",
            "8",
            "--threads",
            str(threads),
            "--max-accept",
            str(max(1, int(max_accept))),
        ],
        timeout=timeout,
    )
    _run(
        binary,
        [
            "result2msa",
            str(base / "qdb"),
            database,
            str(base / "res"),
            str(base / "profile"),
            "--msa-format-mode",
            "6",
        ],
        timeout=timeout,
    )
    _run(
        binary,
        [
            "unpackdb",
            str(base / "profile"),
            str(base),
            "--unpack-name-mode",
            "0",
            "--unpack-suffix",
            ".a3m",
        ],
        timeout=timeout,
    )
    produced = base / f"{name}.a3m"
    if not produced.is_file():
        raise StepError(f"MSA search produced no alignment for {name}")
    lines = produced.read_text(encoding="utf-8", errors="replace").splitlines()
    if not lines or not lines[0].startswith(">"):
        raise StepError(f"MSA search produced an unreadable alignment for {name}")
    return produced


def temporary_msa(sequence: str, *, threads: int = 8) -> tuple[Path, Path]:
    """Build an MSA in a fresh temporary directory; return ``(a3m, directory)``."""

    directory = Path(tempfile.mkdtemp(prefix="msa_"))
    return build_msa(sequence, directory, threads=threads), directory
