"""Content identities for library code.

The identity covers only Python sources so that sidecars and documentation can
be corrected without changing executable identity.
"""

from __future__ import annotations

from hashlib import sha256


def file_sha256(data: bytes) -> str:
    return sha256(data).hexdigest()


def normalize_newlines(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def code_identity(files: dict[str, bytes]) -> str:
    """Hash sorted ``.py`` entries as ``name + NUL + LF-normalized content``."""
    digest = sha256()
    for name in sorted(name for name in files if name.endswith(".py")):
        digest.update(name.encode("utf-8") + b"\0")
        digest.update(normalize_newlines(files[name]))
    return digest.hexdigest()
