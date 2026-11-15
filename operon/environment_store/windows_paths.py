"""Local launch locations for immutable generations with long Windows paths.

These junctions are metadata, not environment identities or readiness receipts.
The caller must validate the generation and hold its ordinary environment lease
before launch; GC must establish that it is unreferenced before removing an
alias. Executables are validated against the canonical payload first, then
joined lexically to the returned root. Resolving that join defeats the alias.
"""
from __future__ import annotations

from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import hashlib
import os
from pathlib import Path
import re
import stat
import struct
import uuid

from operon.bytecode import filesystem_path, io_path
from operon.contracts.base import ContractError
from operon.engine.fs import FileLock


_WINDOWS = os.name == 'nt'
_MOUNT_POINT = 0xA0000003
_REPARSE_ATTRIBUTE = 0x400
_MAX_REPARSE_BYTES = 16384


def _conflict(message):
    return ContractError(message, code='environment_launch_conflict')


def _logical_path(path):
    value = str(path)
    if value.startswith('\\\\?\\UNC\\'):
        value = '\\\\' + value[8:]
    elif value.startswith('\\\\?\\'):
        value = value[4:]
    return Path(value)


def _layout(store_root, generation_id):
    if not isinstance(generation_id, str) or not re.fullmatch('[a-f0-9]{64}', generation_id):
        raise ContractError('Launch aliases require a full generation SHA256', code='invalid_environment')
    root = _logical_path(Path(store_root).resolve()) if _WINDOWS else Path(store_root).resolve()
    target = root / 'generations' / generation_id / 'payload'
    name = hashlib.sha256(generation_id.encode('ascii')).hexdigest()[:24]
    return root, target, root / '.launch' / name


def _entry(path):
    try:
        return io_path(path).lstat()
    except FileNotFoundError:
        return None


def _plain_directory(path, *, create=False):
    if create:
        io_path(path).mkdir(exist_ok=True)
    entry = _entry(path)
    if (entry is None or not stat.S_ISDIR(entry.st_mode) or stat.S_ISLNK(entry.st_mode)
            or getattr(entry, 'st_file_attributes', 0) & _REPARSE_ATTRIBUTE):
        raise _conflict(f'Launch metadata requires a real directory: {path}')


@contextmanager
def _generation_lock(root, generation_id):
    _plain_directory(root)
    _plain_directory(root / 'locks', create=True)
    path = root / 'locks' / (generation_id + '.launch.lock')
    entry = _entry(path)
    if entry is not None and (not stat.S_ISREG(entry.st_mode)
            or getattr(entry, 'st_file_attributes', 0) & _REPARSE_ATTRIBUTE):
        raise _conflict('Generation launch lock is not a regular file')
    with FileLock(path):
        yield


def _mount_buffer(target):
    """Encode the documented MountPointReparseBuffer, lengths in UTF-16 bytes."""
    printable = str(target)
    substitute = '\\??\\' + printable
    if '\0' in printable:
        raise _conflict('Invalid junction target')
    short = substitute.encode('utf-16-le')
    long = printable.encode('utf-16-le')
    if len(short) + len(long) + 20 > _MAX_REPARSE_BYTES:
        raise ContractError('Generation junction target is too long', code='environment_launch_unavailable')
    body = struct.pack('<HHHH', 0, len(short), len(short) + 2, len(long))
    body += short + b'\0\0' + long + b'\0\0'
    return struct.pack('<IHH', _MOUNT_POINT, len(body), 0) + body


def _mount_names(data):
    """Reject symlinks, other reparse tags and malformed/truncated records."""
    if len(data) < 16:
        raise _conflict('Truncated launch junction record')
    tag, size, _ = struct.unpack_from('<IHH', data)
    if tag != _MOUNT_POINT or size < 8 or size + 8 != len(data) or len(data) > _MAX_REPARSE_BYTES:
        raise _conflict('Launch alias is not a valid directory junction')
    offsets = struct.unpack_from('<HHHH', data, 8)
    paths = data[16:]
    names = []
    for offset, length in (offsets[:2], offsets[2:]):
        if (offset % 2 or length % 2 or not length or offset + length + 2 > len(paths)
                or paths[offset + length:offset + length + 2] != b'\0\0'):
            raise _conflict('Invalid launch junction name bounds')
        try:
            name = paths[offset:offset + length].decode('utf-16-le')
        except UnicodeDecodeError as exc:
            raise _conflict('Invalid launch junction name encoding') from exc
        if '\0' in name:
            raise _conflict('Invalid launch junction name')
        names.append(name)
    return tuple(names)


class _NativeJunctions:
    """Win32 junction operations; no shell, privileges or drive mappings."""

    def __init__(self):
        self.api = ctypes.WinDLL('kernel32', use_last_error=True)
        signatures = {
            'CreateFileW': ([wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                             wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE], wintypes.HANDLE),
            'CloseHandle': ([wintypes.HANDLE], wintypes.BOOL),
            'CreateDirectoryW': ([wintypes.LPCWSTR, ctypes.c_void_p], wintypes.BOOL),
            'RemoveDirectoryW': ([wintypes.LPCWSTR], wintypes.BOOL),
            'MoveFileExW': ([wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD], wintypes.BOOL),
            'GetDriveTypeW': ([wintypes.LPCWSTR], wintypes.UINT),
            'DeviceIoControl': ([wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
                                 ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
                                 ctypes.c_void_p], wintypes.BOOL),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(self.api, name)
            function.argtypes, function.restype = arguments, result

    @staticmethod
    def _check(result):
        if not result:
            raise ctypes.WinError(ctypes.get_last_error())
        return result

    def local_root(self, root):
        if (len(root.drive) != 2 or root.drive[1] != ':' or not root.is_absolute()
                or self.api.GetDriveTypeW(root.anchor) not in (2, 3, 6)):
            raise ContractError('Launch junctions require a local Windows volume',
                                code='environment_launch_unavailable')

    @contextmanager
    def _open(self, path, *, write=False):
        # Open the junction itself. Deny concurrent write/delete while checking
        # its reparse record; never open through to the generation payload.
        access = 0x80000000 | (0x40000000 if write else 0)
        handle = self.api.CreateFileW(filesystem_path(path, resolve=False), access, 1,
                                     None, 3, 0x02000000 | 0x00200000, None)
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            yield handle
        finally:
            self.api.CloseHandle(handle)

    def _get(self, handle):
        output = ctypes.create_string_buffer(_MAX_REPARSE_BYTES)
        count = wintypes.DWORD()
        self._check(self.api.DeviceIoControl(handle, 0x000900A8, None, 0, output,
                                             len(output), ctypes.byref(count), None))
        return _mount_names(output.raw[:count.value])

    def verify(self, alias, target):
        entry = _entry(alias)
        if (entry is None or not stat.S_ISDIR(entry.st_mode) or stat.S_ISLNK(entry.st_mode)
                or not getattr(entry, 'st_file_attributes', 0) & _REPARSE_ATTRIBUTE):
            raise _conflict('Existing launch alias is not a directory junction')
        with self._open(alias) as handle:
            actual = self._get(handle)
        expected = ('\\??\\' + str(target), str(target))
        # Compare every path component, including the full generation digest.
        # Do not resolve/normalize '..', symlinks or a misleading print name.
        if tuple(value.casefold() for value in actual) != tuple(value.casefold() for value in expected):
            raise _conflict('Launch junction points to a different generation')

    def create(self, alias, target):
        # Publish a verified junction without replacement. A crash can leave a
        # temporary metadata entry, but never an ordinary directory at the alias.
        temporary = alias.with_name(alias.name + '.' + uuid.uuid4().hex + '.tmp')
        native = filesystem_path(temporary, resolve=False)
        self._check(self.api.CreateDirectoryW(native, None))
        try:
            with self._open(temporary, write=True) as handle:
                data = _mount_buffer(target)
                buffer = ctypes.create_string_buffer(data)
                count = wintypes.DWORD()
                self._check(self.api.DeviceIoControl(handle, 0x000900A4, buffer, len(data),
                                                     None, 0, ctypes.byref(count), None))
                if self._get(handle) != ('\\??\\' + str(target), str(target)):
                    raise _conflict('New launch junction target verification failed')
            # Flags=0 deliberately excludes MOVEFILE_REPLACE_EXISTING.
            self._check(self.api.MoveFileExW(native, filesystem_path(alias, resolve=False), 0))
        finally:
            # RemoveDirectory deletes only this metadata entry, even when it is
            # a junction; it never enumerates or removes target contents.
            if _entry(temporary) is not None:
                self._check(self.api.RemoveDirectoryW(native))

    def remove(self, alias):
        self._check(self.api.RemoveDirectoryW(filesystem_path(alias, resolve=False)))


def launch_root(store_root, generation_id):
    """Return a normal logical launch Path; fail closed on unavailable junctions.

    On non-Windows systems this is simply the canonical payload path. Windows
    callers must preserve the lexical alias when appending a validated relative
    executable or runtime-data path. This function never grants a generation
    lease, verifies runtime content, or falls back to an extended executable.
    """
    root, target, alias = _layout(store_root, generation_id)
    if not _WINDOWS:
        return target.resolve()
    if len(str(alias).encode('utf-16-le')) // 2 >= 248:
        raise ContractError('Store root is too long for a normal Windows launch directory',
                            code='environment_launch_path_too_long')
    try:
        api = _NativeJunctions()
        api.local_root(root)
        with _generation_lock(root, generation_id):
            for directory in (root / 'generations', target.parent, target):
                _plain_directory(directory)
            _plain_directory(alias.parent, create=True)
            if _entry(alias) is None:
                api.create(alias, target)
            api.verify(alias, target)
        return alias
    except (OSError, AttributeError) as exc:
        raise ContractError('Windows generation launch junction is unavailable',
                            code='environment_launch_unavailable',
                            details={'winerror': getattr(exc, 'winerror', None)}) from exc


def remove_launch_alias(store_root, generation_id):
    """Remove only the matching junction; return False when no alias exists.

    GC owns the reference/lease check. A dangling junction may be removed after
    an interrupted GC, so the payload need not exist. Foreign entries are never
    replaced or removed, and the generation target is never traversed.
    """
    root, target, alias = _layout(store_root, generation_id)
    if not _WINDOWS:
        return False
    try:
        api = _NativeJunctions()
        api.local_root(root)
        with _generation_lock(root, generation_id):
            if _entry(alias.parent) is None:
                return False
            _plain_directory(alias.parent)
            if _entry(alias) is None:
                return False
            api.verify(alias, target)
            api.remove(alias)
        return True
    except (OSError, AttributeError) as exc:
        raise ContractError('Windows generation launch junction removal is unavailable',
                            code='environment_launch_unavailable',
                            details={'winerror': getattr(exc, 'winerror', None)}) from exc
