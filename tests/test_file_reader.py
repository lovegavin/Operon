"""FileReader: the generic file source used by file-port operators."""
from __future__ import annotations

import gzip
from pathlib import Path

import pytest

from src.core import FileArtifact, ReaderError
from src.reader import read_source
from src.reader.readers.file_reader import FileReader


def _write(path: Path, payload: bytes = b"payload") -> Path:
    path.write_bytes(payload)
    return path


def test_infers_format_and_default_role(tmp_path: Path) -> None:
    path = _write(tmp_path / "coords.npy", b"\x93NUMPY")
    artifact = FileReader().read(path, ["file"], {})
    assert isinstance(artifact, FileArtifact)
    assert artifact.format == "npy"
    assert artifact.files == {"data": str(path.resolve())}
    assert artifact.info["compressed"] is False
    artifact.validate()


def test_records_explicit_role_and_format(tmp_path: Path) -> None:
    path = _write(tmp_path / "run.pdbqt")
    artifact = FileReader().read(path, ["file"], {}, role="ligand", format="pdbqt")
    assert artifact.files["ligand"] == str(path.resolve())
    assert artifact.format == "pdbqt"


def test_alias_normalisation(tmp_path: Path) -> None:
    path = _write(tmp_path / "query.faa")
    assert FileReader().read(path, ["file"], {}).format == "fasta"
    other = _write(tmp_path / "weird.bin", b"\x00\x01")
    assert FileReader().read(other, ["file"], {}, format="mmcif").format == "cif"


def test_compressed_suffix_is_ignored_for_format(tmp_path: Path) -> None:
    path = tmp_path / "traj.npy.gz"
    with gzip.open(path, "wb") as handle:
        handle.write(b"\x93NUMPY")
    artifact = FileReader().read(path, ["file"], {})
    assert artifact.format == "npy"
    assert artifact.info["compressed"] is True
    artifact.validate()


def test_missing_file_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ReaderError):
        FileReader().read(tmp_path / "absent.npy", ["file"], {})


def test_registered_reader_can_be_selected_by_id(tmp_path: Path) -> None:
    path = _write(tmp_path / "topology.pdb", b"ATOM\n")
    artifact = read_source(path, ["file"], {}, reader_id="FileReader")
    assert artifact.format == "pdb"
    assert artifact.files["data"] == str(path.resolve())
    artifact.validate()
