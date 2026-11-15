"""Stable storage identities and immutable metadata, without credentials."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath, PureWindowsPath
from typing import Literal

from operon.contracts.base import ContractError
from operon.contracts.storage import StorageRef


class StorageError(ContractError):
    """Machine-readable storage failure shared by all application adapters."""


def relative_path(value: str) -> str:
    """Normalize portable root-relative paths; never normalize away traversal."""
    if not isinstance(value, str) or len(value) > 2048:
        raise ValueError('Storage paths must be strings of at most 2048 characters')
    value = value.replace('\\', '/')
    if (PureWindowsPath(value).drive or value.startswith('/') or '\x00' in value
            or '..' in value.split('/') or ':' in value):
        raise ValueError('Storage paths must remain inside their configured root')
    return str(PurePosixPath(value or '.'))


def reference(storage_id: str, path: str = '.', *, version: str | None = None,
              digest: str | None = None) -> StorageRef:
    return StorageRef(storage_id=storage_id, relative_path=relative_path(path),
                      version=version, digest=digest)


@dataclass(frozen=True)
class StorageEntry:
    ref: StorageRef
    name: str
    kind: Literal['file', 'directory', 'symlink', 'other']
    size_bytes: int
    modified_ns: int | None
    is_symlink: bool = False
    accessible: bool = True


def restart(code: str, message: str) -> StorageError:
    return StorageError(message, code=code, next_actions=(
        {'action': 'restart_browse', 'cursor': None},))
