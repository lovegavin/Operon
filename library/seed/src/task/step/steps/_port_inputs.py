"""Resolve declared data ports into the temporary files that tool wrappers need.

Operators that wrap external programs (ProteinMPNN, RFdiffusion, Vina, MDAnalysis,
...) need a file on disk.  The workflow contract no longer hands them a bare path
parameter: the run data arrives as a ``form`` (a structure or sequence table) or a
``file_artifact`` port, and this module materialises that port into a temporary
file while keeping the legacy path parameter as an empty-by-default override for
direct API calls.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from src.core import FileArtifact, Form
from src.core.errors import StepError

from . import _genome_align_utils, _protein_common

_STRUCTURE_FORMATS = {"pdb", "ent", "cif", "mmcif"}


def _artifact_path(artifact: FileArtifact, operator: str, roles: tuple[str, ...], formats: frozenset[str]) -> str:
    artifact.validate()
    if formats and artifact.format.lower() not in formats:
        raise StepError(
            f"{operator}: expected one of {', '.join(sorted(formats))}, got {artifact.format!r}"
        )
    files = artifact.files or {}
    for role in roles:
        if role in files:
            return str(files[role])
    if len(files) == 1:
        return str(next(iter(files.values())))
    if files:
        raise StepError(
            f"{operator}: the file artifact carries several files "
            f"({', '.join(sorted(files))}); name one of them explicitly"
        )
    raise StepError(f"{operator}: the file artifact carries no files")


def structure(
    value,
    fallback: str = "",
    operator: str = "step",
    atom_dim: str = "atom",
    field_dim: str = "field",
    design_index: int = 0,
) -> str:
    """Return a PDB path for a structure port, or the legacy override path."""
    if isinstance(value, FileArtifact):
        return _artifact_path(value, operator, ("structure", "model", "pdb"), frozenset(_STRUCTURE_FORMATS))
    if isinstance(value, Form):
        path = _protein_common.structure_file(value, fallback, operator, atom_dim, field_dim,
                                              design_index=design_index)
        return Path(path).as_posix()
    if value is not None:
        raise StepError(
            f"{operator}: the structure port expects a form or file_artifact, got {type(value).__name__}"
        )
    text = str(fallback or "").strip()
    if text:
        return text
    raise StepError(f"{operator}: a structure port is required")


def fasta(
    value,
    fallback: str = "",
    operator: str = "step",
    sequence_dim: str = "sequence",
    position_dim: str = "position",
) -> str:
    """Return a FASTA path for a sequence port, or the legacy override path."""
    if isinstance(value, FileArtifact):
        return _artifact_path(value, operator, ("query", "fasta", "sequences"), frozenset({"fasta", "fa", "faa", "fna"}))
    if isinstance(value, Form):
        workdir = Path(tempfile.mkdtemp(prefix=f"{operator}-fasta-"))
        path = workdir / "query.fasta"
        _genome_align_utils.write_fasta(value, sequence_dim, position_dim, path, operator)
        return path.as_posix()
    if value is not None:
        raise StepError(
            f"{operator}: the sequence port expects a form or file_artifact, got {type(value).__name__}"
        )
    text = str(fallback or "").strip()
    if text:
        return text
    raise StepError(f"{operator}: a sequence port is required")


def file(
    value,
    fallback: str = "",
    operator: str = "step",
    roles: tuple[str, ...] = (),
    formats: frozenset[str] | None = None,
) -> str:
    """Return the path carried by a file artifact port, or the legacy override."""
    if isinstance(value, FileArtifact):
        return _artifact_path(value, operator, roles, frozenset(formats or ()))
    if value is not None:
        raise StepError(
            f"{operator}: the file port expects a file_artifact, got {type(value).__name__}"
        )
    text = str(fallback or "").strip()
    if text:
        return text
    raise StepError(f"{operator}: a file port is required")
