"""Streaming inventories and confined paths used by builders and collectors."""
from __future__ import annotations

import hashlib
import os
import stat
import sys
import time
from functools import lru_cache
from pathlib import Path

from operon.contracts.base import ContractError, sha256_hex
from operon.contracts.run_plan import validate_relative_path
from operon.bytecode import io_path


def confined(root, relative):
    root = Path(root).resolve()
    return _confined_resolved(root, relative)


def _confined_resolved(root, relative):
    """Internal helper: root was already resolved for this inventory operation."""
    validate_relative_path(relative)
    path = root / relative
    if not path.resolve().is_relative_to(root):
        raise ContractError('Path escapes its owned root', code='path_escape')
    return path


def file_digest(path):
    digest = hashlib.sha256()
    with io_path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


@lru_cache(maxsize=1)
def _final_path_api():
    import ctypes
    from ctypes import wintypes
    function = ctypes.WinDLL('kernel32', use_last_error=True).GetFinalPathNameByHandleW
    function.argtypes = [wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD]
    function.restype = wintypes.DWORD
    return function


def _opened_windows_path(stream):
    """Resolve the already opened object, not every ancestor of every filename."""
    import ctypes
    import msvcrt
    function = _final_path_api()
    handle = msvcrt.get_osfhandle(stream.fileno())
    capacity = 512
    while True:
        buffer = ctypes.create_unicode_buffer(capacity)
        length = function(handle, buffer, capacity, 0)
        if not length:
            raise ctypes.WinError(ctypes.get_last_error())
        if length < capacity:
            return Path(buffer.value)
        if length > 32768:
            raise ContractError('Opened path exceeds the Windows limit', code='path_escape')
        capacity = length + 1


def _windows_inventory_digest(path, root, attrs):
    # Check the actual open handle before reading any bytes. This also catches
    # an ancestor replaced with an external junction between enumeration/open.
    with path.open('rb') as stream:
        if not _opened_windows_path(stream).is_relative_to(root):
            raise ContractError('Path escapes its owned root', code='path_escape')
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size != attrs.st_size:
            raise ContractError('File changed during inventory', code='environment_corrupt')
        digest = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
        after = os.fstat(stream.fileno())
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ContractError('File changed during inventory', code='environment_corrupt')
        return digest.hexdigest()


def inventory(root, *, excluded_roots=()):
    """No dereferencing of external links, no in-memory file contents."""
    root = Path(root).resolve()
    scan_root = io_path(root)
    result = {}
    excluded = set(excluded_roots)
    for relative in excluded:
        _confined_resolved(root, relative)
    progress = os.environ.get('OPERON_EXPORT_PROBE') == '1'
    started = reported = time.monotonic()
    for directory, dirs, files in os.walk(scan_root, followlinks=False):
        dirs[:] = [name for name in dirs if (Path(directory) / name).relative_to(scan_root).as_posix() not in excluded]
        for name in sorted(dirs + files):
            path = Path(directory) / name
            relative = path.relative_to(scan_root).as_posix()
            validate_relative_path(relative)
            attrs = path.lstat()
            # Windows Path.resolve() repeatedly opens the complete ancestor
            # chain. Regular files instead use their open handle's final path.
            # Directories and links keep the existing full boundary check.
            if os.name != 'nt' or not stat.S_ISREG(attrs.st_mode):
                _confined_resolved(root, relative)
            if stat.S_ISLNK(attrs.st_mode):
                target = os.readlink(path)
                if Path(target).is_absolute():
                    raise ContractError('Absolute symlinks are not relocatable', code='invalid_environment')
                result[relative] = {'kind': 'symlink', 'target': target}
            elif stat.S_ISREG(attrs.st_mode):
                result[relative] = {'kind': 'file', 'size': attrs.st_size,
                                    'sha256': (_windows_inventory_digest(path, scan_root, attrs)
                                               if os.name == 'nt' else file_digest(path)),
                                    'executable': bool(attrs.st_mode & 0o111)}
            elif not stat.S_ISDIR(attrs.st_mode):
                raise ContractError('Special files cannot be packaged', code='invalid_environment')
            if progress and time.monotonic() - reported >= 5:
                reported = time.monotonic()
                print(f'[Operon portable probe] inventory entries={len(result)} elapsed={reported - started:.1f}s',
                      file=sys.stderr, flush=True)
    return result


def verify_inventory(root, expected, *, excluded_roots=()):
    actual = inventory(root, excluded_roots=excluded_roots)
    if actual != expected:
        changed = sorted(set(actual) ^ set(expected) | {
            key for key in actual.keys() & expected.keys() if actual[key] != expected[key]})
        raise ContractError('Environment contents changed: ' + ', '.join(changed[:12]),
                            code='environment_corrupt')
    return sha256_hex(actual)
