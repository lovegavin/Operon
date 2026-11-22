"""Workspace task scaffolding and bounded UTF-8 writes for agents.

Agents do not need host filesystem permissions inside the Operon workspace:
the backend validates a workspace-relative path and performs the write. Every
operation is confined to the profile workspace; Operon's internal state
directories are never writable through this service.
"""
from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path, PurePosixPath

from .documents import CommandError

DEFAULT_FOLDERS = ('input', 'results', 'reports', 'figures')
PROTECTED_ROOTS = frozenset({'.studio', '.operon', '.admission'})
MAX_TEXT_BYTES = 10 * 1024 * 1024
MAX_BINARY_BYTES = 50 * 1024 * 1024


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


def _write_data(root, relative, data, overwrite=True):
    root = _workspace(root)
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
        with os.fdopen(handle, 'wb') as stream:
            stream.write(data)
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


def write_text(root, relative, content, overwrite=True):
    """Write UTF-8 text to a workspace-relative path, creating parent folders."""
    if not isinstance(content, str):
        raise CommandError('invalid_content', 'content must be a string')
    data = content.encode('utf-8')
    if len(data) > MAX_TEXT_BYTES:
        raise CommandError(
            'content_too_large',
            f'content exceeds {MAX_TEXT_BYTES // (1024 * 1024)} MiB',
            413,
        )
    return _write_data(root, relative, data, overwrite)


def write_binary(root, relative, content, overwrite=True):
    """Write bytes (PNG, PDF, ZIP, ...) to a workspace-relative path."""
    if not isinstance(content, (bytes, bytearray, memoryview)):
        raise CommandError('invalid_content', 'content must be bytes')
    data = bytes(content)
    if len(data) > MAX_BINARY_BYTES:
        raise CommandError(
            'content_too_large',
            f'content exceeds {MAX_BINARY_BYTES // (1024 * 1024)} MiB',
            413,
        )
    return _write_data(root, relative, data, overwrite)


class StreamSink:
    """Copy a streamed request body into one workspace file.

    The bytes never pass through JSON or base64: each chunk is written straight to a
    temporary file that is renamed into place only when the whole body arrived, so a
    dropped connection cannot leave a truncated file behind.
    """

    def __init__(self, root, relative, overwrite=True):
        self._root = _workspace(root)
        _, self._target = _target(self._root, relative, 'path')
        self._overwrite = overwrite
        self._existed = False
        self._handle = None
        self._temporary = None
        self._stream = None
        self._size = 0
        self._digest = hashlib.sha256()
        self.result = None

    def __enter__(self):
        target = self._target
        self._existed = target.exists()
        if self._existed:
            if target.is_dir():
                raise CommandError('invalid_path', 'path already exists as a directory')
            if not self._overwrite:
                raise CommandError(
                    'file_exists',
                    f'{target.relative_to(self._root).as_posix()} already exists; pass overwrite=true to replace it',
                    409,
                )
        target.parent.mkdir(parents=True, exist_ok=True)
        final = target.resolve()
        if final != self._root and not final.is_relative_to(self._root):
            raise CommandError('invalid_path', 'path escapes the workspace')
        self._handle, self._temporary = tempfile.mkstemp(prefix='.' + target.name + '.', dir=target.parent)
        self._stream = os.fdopen(self._handle, 'wb')
        return self

    def write(self, chunk):
        if not chunk:
            return 0
        data = bytes(chunk)
        self._stream.write(data)
        self._size += len(data)
        self._digest.update(data)
        return len(data)

    def __exit__(self, exc_type, exc, trace):
        try:
            if self._stream is not None:
                self._stream.close()
            if exc_type is None:
                os.replace(self._temporary, self._target)
                self.result = {
                    'workspace': str(self._root),
                    'path': self._target.relative_to(self._root).as_posix(),
                    'bytes': self._size,
                    'sha256': self._digest.hexdigest(),
                    'created': not self._existed,
                }
        finally:
            if exc_type is not None and self._temporary:
                try:
                    os.unlink(self._temporary)
                except OSError:
                    pass
            self._stream = None
        return False


def open_stream(root, relative, overwrite=True):
    """Open a bounded writer for a streamed upload; use it as a context manager."""
    return StreamSink(root, relative, overwrite)


def write_stream(root, relative, chunks, overwrite=True):
    """Write an iterable of byte chunks to a workspace-relative path."""
    with open_stream(root, relative, overwrite) as sink:
        for chunk in chunks:
            sink.write(chunk)
    return sink.result


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

    def write_binary(self, path, content, overwrite=True):
        return write_binary(self.root, path, content, overwrite)

    def open_stream(self, path, overwrite=True):
        return open_stream(self.root, path, overwrite)

    def write_stream(self, path, chunks, overwrite=True):
        return write_stream(self.root, path, chunks, overwrite)
