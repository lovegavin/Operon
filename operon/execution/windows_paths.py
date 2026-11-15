"""Verified Windows current-directory aliases for owned invocation attempts.

CreateProcess cannot use every extended-length path as its current directory.
Only the launch spelling changes: prepared files, logs and artifact ownership
remain at the exact original attempt root. Aliases are retained metadata; cleanup
may remove a matching alias after the ordinary process-tree/lease checks, never
the target directory or its contents.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import re
import stat

from operon.bytecode import io_path
from operon.contracts.base import ContractError
from operon.engine.fs import FileLock
from operon.environment_store.windows_paths import _NativeJunctions, _entry, _logical_path, _plain_directory


_WINDOWS = os.name == 'nt'
_REPARSE_ATTRIBUTE = 0x400


def _error(message, code='attempt_launch_conflict', **details):
    return ContractError(message, code=code, details=details)


def _layout(executor_root, attempt_root, run_id, attempt_id):
    if any(not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,200}', value)
           or value in ('.', '..') for value in (run_id, attempt_id)):
        raise _error('Attempt launch requires exact bounded run and attempt identifiers')
    root, target = (Path(value).absolute() for value in (executor_root, attempt_root))
    if _WINDOWS:
        root, target = _logical_path(root), _logical_path(target)
        if any(part in ('.', '..') or part.endswith(('.', ' ')) or ':' in part for part in root.parts[1:]):
            raise _error('Executor root contains a nonportable Win32 name')
    try:
        parts = target.relative_to(root).parts
    except ValueError as exc:
        raise _error('Attempt current directory escapes the executor root') from exc
    compact = len(parts) == 4 and parts[:2] == ('runs', run_id) and parts[2:] == ('attempts', attempt_id)
    legacy = (len(parts) == 6 and parts[:3] == ('runs', run_id, 'nodes')
              and parts[-2:] == ('attempts', attempt_id) and parts[3] not in ('.', '..'))
    if not (compact or legacy):
        raise _error('Current directory does not identify this exact invocation attempt')
    if _WINDOWS and any(part.endswith(('.', ' ')) or ':' in part for part in parts):
        raise _error('Attempt directory contains a nonportable Win32 name')
    # A shortened digest keeps the alias useful for deeply nested workspaces.
    # Any collision fails exact reparse-target verification; nothing is replaced.
    identity = '\0'.join((os.path.normcase(str(root)), *parts))
    name = hashlib.sha256(identity.encode('utf-8')).hexdigest()[:24]
    alias = root / '.work' / name
    return root, target, alias


@contextmanager
def _alias_lock(root, alias):
    _plain_directory(root)
    locks = root / '.work-locks'
    _plain_directory(locks, create=True)
    lock = locks / (alias.name + '.lock')
    entry = _entry(lock)
    if entry is not None and (not stat.S_ISREG(entry.st_mode)
            or getattr(entry, 'st_file_attributes', 0) & _REPARSE_ATTRIBUTE):
        raise _error('Attempt launch lock must be an ordinary file')
    with FileLock(lock):
        yield


def _target_directories(root, target):
    current = root
    _plain_directory(current)
    for part in target.relative_to(root).parts:
        current = current / part
        _plain_directory(current)
    if _logical_path(io_path(target).resolve(strict=True)) != _logical_path(io_path(root).resolve(strict=True)) / target.relative_to(root):
        raise _error('Attempt current directory changed its executor confinement')


def _translate(exc, *, removing=False):
    if isinstance(exc, ContractError):
        if exc.code.startswith('attempt_launch_'):
            return exc
        code = 'attempt_launch_conflict' if exc.code == 'environment_launch_conflict' else 'attempt_launch_unavailable'
    else:
        code = 'attempt_launch_unavailable'
    return _error('Attempt launch alias removal failed' if removing else 'Attempt launch alias is unavailable',
                  code, winerror=getattr(exc, 'winerror', None))


def attempt_launch_cwd(executor_root, attempt_root, *, run_id, attempt_id):
    """Return the exact attempt cwd, using a verified short junction on Windows.

    The caller has already prepared the attempt under its host lease. No parent
    cwd, alternate data directory, shell command or extended-cwd fallback is used.
    """
    root, target, alias = _layout(executor_root, attempt_root, run_id, attempt_id)
    if not _WINDOWS:
        return target
    if len(str(alias).encode('utf-16-le')) // 2 >= 248:
        raise _error('Executor root is too long for a normal Windows attempt current directory',
                     'attempt_launch_path_too_long')
    try:
        api = _NativeJunctions()
        api.local_root(root)
        with _alias_lock(root, alias):
            _target_directories(root, target)
            _plain_directory(alias.parent, create=True)
            if _entry(alias) is None:
                api.create(alias, target)
            api.verify(alias, target)
            _target_directories(root, target)
        return alias
    except (ContractError, OSError, AttributeError) as exc:
        error = _translate(exc)
        raise error from (None if error is exc else exc)


def remove_attempt_alias(executor_root, attempt_root, *, run_id, attempt_id):
    """Remove matching alias metadata only, after caller-confirmed attempt exit.

    This does not establish process/lease exit or release anything itself. It
    also supports a dangling alias after interrupted cleanup, without traversing
    the target. Foreign directories, links or other targets are never removed.
    """
    root, target, alias = _layout(executor_root, attempt_root, run_id, attempt_id)
    if not _WINDOWS:
        return False
    try:
        api = _NativeJunctions()
        api.local_root(root)
        with _alias_lock(root, alias):
            if _entry(alias.parent) is None:
                return False
            _plain_directory(alias.parent)
            if _entry(alias) is None:
                return False
            api.verify(alias, target)
            api.remove(alias)
        return True
    except (ContractError, OSError, AttributeError) as exc:
        error = _translate(exc, removing=True)
        raise error from (None if error is exc else exc)


__all__ = ['attempt_launch_cwd', 'remove_attempt_alias']
