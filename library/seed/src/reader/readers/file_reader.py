"""FileReader: reference any declared file format as a file artifact.

Readers that hand an operator a file (BAM, VCF, A3M, ...) each claim one
format. Trajectories, docking poses and model inputs have no such typed
reader, so a workflow had no way to feed them to an operator that declares a
``file_artifact`` port. This reader closes that gap without decoding the
payload: it validates one existing file and reports its representation.
"""
from __future__ import annotations

from pathlib import Path

from src.reader.base import Reader

_COMPRESSION_SUFFIXES = {".gz", ".bz2", ".xz", ".zst", ".zip"}
_ALIASES = {"fa": "fasta", "faa": "fasta", "fna": "fasta", "fas": "fasta", "mmcif": "cif"}


class FileReader(Reader):
    provider = "operon-readers"
    parameters_file = "file.parameters.json"
    definition = {
        "protocol_revision": "3.7",
        "protocol_version": 3,
        "id": "FileReader",
        "version": "1.0.0",
        "kind": "reader",
        "title": "FileReader",
        "description": (
            "Reference any supported file as a file artifact without decoding it, "
            "for operators that declare a file port."
        ),
        "category": "Data",
        "icon": "File",
        "data_formats": {
            "inputs": [],
            "outputs": [
                {
                    "logical_type": "file_artifact",
                    "representations": ["file_artifact"],
                    "metadata": {},
                }
            ],
        },
        "contracts": {
            "version": 1,
            "inputs": [],
            "output": {
                "kind": "file",
                "numeric": False,
                "ndim": 0,
                "info": {"representation": {"type": "string"}},
                "info_open": True,
            },
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False},
        "extensions": [
            ".npy",
            ".xtc",
            ".trr",
            ".dcd",
            ".nc",
            ".mdcrd",
            ".crd",
            ".edr",
            ".gro",
            ".psf",
            ".top",
            ".tpr",
            ".prmtop",
            ".parm7",
            ".pdbqt",
            ".sdf",
            ".mol2",
            ".mol",
            ".json",
            ".h5",
            ".hdf5",
            ".pdb",
            ".ent",
        ],
        "handles_compression": True,
        "file_input": {"dims": ["file"], "labels": {}, "compression": [".gz", ".bz2", ".xz"]},
    }

    def read(self, path, dims, labels, **args):
        from src.core import ReaderError
        from src.core.files import FileArtifact

        source = Path(path)
        if not source.is_file():
            raise ReaderError(f"FileReader: {source} is not a file")
        suffixes = [suffix.lower() for suffix in source.suffixes]
        compressed = bool(suffixes) and suffixes[-1] in _COMPRESSION_SUFFIXES
        if compressed:
            suffixes = suffixes[:-1]
        inferred = suffixes[-1].lstrip(".") if suffixes else "data"
        inferred = _ALIASES.get(inferred, inferred) or "data"
        requested = str(args.get("format") or "").strip().lower()
        representation = _ALIASES.get(requested, requested) or inferred
        role = str(args.get("role") or "data").strip() or "data"
        artifact = FileArtifact(
            representation,
            {role: str(source.resolve())},
            {
                "source": "FileReader",
                "suffix": suffixes[-1] if suffixes else "",
                "compressed": compressed,
            },
        )
        artifact.validate()
        return artifact
