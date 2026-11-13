"""Workspace task scaffolding and bounded UTF-8 writes for agents.

Agents do not need host filesystem permissions inside the Operon workspace:
the backend validates a workspace-relative path and performs the write. Every
operation is confined to the profile workspace; Operon's internal state
directories are never writable through this service.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path, PurePosixPath

from .documents import CommandError

DEFAULT_FOLDERS = ('input', 'results', 'reports', 'figures')
PROTECTED_ROOTS = frozenset({'.studio', '.operon', '.admission'})
MAX_TEXT_BYTES = 10 * 1024 * 1024


def _normalize(value, label):
    if not isinstance(value, str):
        raise CommandError('invalid_path', f'{label} must be a string')
    text = value.strip()
    if not text:
        raise CommandError('invalid_path', f'{label} must not be empty')
    normalized = text.replace('\\', '/')
    if normalized.startswith('/'):
        raise CommandError('invalid_path', f'{label} must be relative to the workspace')
    if len(normalized) > 1 and normalized[1] == ':':
        raise CommandError('invalid_path', f'{label} must be relative to the workspace')
    pure = PurePosixPath(normalized)
    if any(part in ('', '.', '..') for part in pure.parts):
        raise CommandError('invalid_path', f'{label} must not contain empty, "." or ".." segments')
    if pure.parts[0] in PROTECTED_ROOTS or pure.parts[0].startswith('.'):
        raise CommandError('protected_path', f'{label} may not target Operon internal state')
    return pure


def _workspace(root):
    root = Path(root).resolve()
    if not root.is_dir():
        raise CommandError('workspace_missing', 'The Operon workspace is not available', 500)
    return root


def _target(root, relative, label='path'):
    pure = _normalize(relative, label)
    target = root.joinpath(*pure.parts)
    if target.is_symlink():
        raise CommandError('invalid_path', f'{label} must not be a symbolic link')
    resolved = target.resolve()
    if resolved != root and not resolved.is_relative_to(root):
        raise CommandError('invalid_path', f'{label} escapes the workspace')
    return pure, target


def scaffold(root, base_dir, folders=None):
    """Create the standard task skeleton below ``base_dir``.

    ``base_dir`` is relative to the workspace (``task1`` or ``project/task1``).
    Default folders are ``input``, ``results``, ``reports`` and ``figures``.
    """
    root = _workspace(root)
    _, base = _target(root, base_dir, 'base_dir')
    names = list(DEFAULT_FOLDERS if folders is None else folders)
    if not names:
        raise CommandError('invalid_folder', 'At least one folder is required')
    if len(names) > 20:
        raise CommandError('invalid_folder', 'At most 20 folders may be created')
    created = []
    if not base.exists():
        base.mkdir(parents=True, exist_ok=True)
        created.append(base.relative_to(root).as_posix())
    result = []
    for name in names:
        pure = _normalize(name, 'folder')
        if len(pure.parts) != 1:
            raise CommandError('invalid_folder', f'Folder {name!r} must be a single path component')
        path = base / pure.parts[0]
        if path.exists() and not path.is_dir():
            raise CommandError(
                'invalid_folder',
                f'{path.relative_to(root).as_posix()} already exists and is not a directory',
            )
        if not path.exists():
            path.mkdir(parents=True)
            created.append(path.relative_to(root).as_posix())
        result.append(path.relative_to(root).as_posix())
    return {
        'workspace': str(root),
        'base_dir': base.relative_to(root).as_posix(),
        'folders': result,
        'created': created,
    }


def write_text(root, relative, content, overwrite=True):
    """Write UTF-8 text to a workspace-relative path, creating parent folders."""
    root = _workspace(root)
    if not isinstance(content, str):
        raise CommandError('invalid_content', 'content must be a string')
    data = content.encode('utf-8')
    if len(data) > MAX_TEXT_BYTES:
        raise CommandError(
            'content_too_large',
            f'content exceeds {MAX_TEXT_BYTES // (1024 * 1024)} MiB',
            413,
        )
    _, target = _target(root, relative, 'path')
    existed = target.exists()
    if existed:
        if target.is_dir():
            raise CommandError('invalid_path', 'path already exists as a directory')
        if not overwrite:
            raise CommandError(
                'file_exists',
                f'{target.relative_to(root).as_posix()} already exists; pass overwrite=true to replace it',
                409,
            )
    target.parent.mkdir(parents=True, exist_ok=True)
    # Re-check after creating parents: a concurrent symlink may change the target.
    final = target.resolve()
    if final != root and not final.is_relative_to(root):
        raise CommandError('invalid_path', 'path escapes the workspace')
    handle, temporary = tempfile.mkstemp(prefix='.' + target.name + '.', dir=target.parent)
    try:
        with os.fdopen(handle, 'w', encoding='utf-8', newline='') as stream:
            stream.write(content)
        os.replace(temporary, target)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise
    return {
        'workspace': str(root),
        'path': target.relative_to(root).as_posix(),
        'bytes': len(data),
        'created': not existed,
    }


class TaskFiles:
    """Workspace file operations owned by the profile application service."""

    def __init__(self, application):
        self.app = application

    @property
    def root(self):
        return Path(self.app.service.root)

    def scaffold(self, base_dir, folders=None):
        return scaffold(self.root, base_dir, folders)

    def write_text(self, path, content, overwrite=True):
        return write_text(self.root, path, content, overwrite)
