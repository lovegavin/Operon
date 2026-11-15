"""Explicit mount maps and confined local/SFTP filesystem adapters.

Backends return metadata only; each SFTP session has an exclusive connection.
They do not load operators, probe compute capability, or start remote services.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import posixpath
import stat
import threading

from operon.bytecode import filesystem_path
from .references import StorageEntry, StorageError, reference, relative_path


def _signature(attrs):
    values = [getattr(attrs, key, None) for key in (
        'st_mode', 'st_size', 'st_mtime', 'st_mtime_ns', 'st_ctime_ns', 'st_ino', 'st_dev')]
    return hashlib.sha256(json.dumps(values, separators=(',', ':')).encode()).hexdigest()


def _entry(storage_id, path, attrs, *, is_symlink=False, accessible=True):
    mode = attrs.st_mode or 0
    kind = ('directory' if stat.S_ISDIR(mode) else 'file' if stat.S_ISREG(mode)
            else 'symlink' if stat.S_ISLNK(mode) else 'other')
    modified_ns = getattr(attrs, 'st_mtime_ns', None)
    if modified_ns is None and getattr(attrs, 'st_mtime', None) is not None:
        modified_ns = int(attrs.st_mtime * 1_000_000_000)
    return StorageEntry(reference(storage_id, path, version=_signature(attrs)),
                        posixpath.basename(path) if path != '.' else '.', kind,
                        max(0, attrs.st_size or 0), modified_ns, is_symlink, accessible)


def _entry_name(name):
    if (not isinstance(name, str) or name in ('', '.', '..')
            or any(character in name for character in ('/', '\\', ':', '\x00'))):
        raise StorageError('Directory entry has no supported portable relative path',
                           code='storage_path_unsupported')
    return name


@dataclass(frozen=True)
class Mount:
    storage_id: str
    backend: object
    principals: frozenset[str]
    execution_profile_id: str | None = None
    endpoint: tuple[str, int, str] | None = None


class MountMap:
    """Administrator-owned IDs. Authorization is checked on every operation."""

    def __init__(self):
        self._mounts = {}
        self._lock = threading.RLock()

    def register(self, storage_id, backend, *, principals, execution_profile_id=None, endpoint=None):
        reference(storage_id)
        if isinstance(principals, str):
            raise ValueError('Authorized principals must be a collection, not one string')
        owners = frozenset(principals)
        if not owners or any(not isinstance(item, str) or not item for item in owners):
            raise ValueError('Every storage mount needs explicit authorized principals')
        with self._lock:
            self._mounts[storage_id] = Mount(storage_id, backend, owners, execution_profile_id, endpoint)

    def resolve(self, storage_id, principal):
        with self._lock:
            mount = self._mounts.get(storage_id)
        if mount is None or principal not in mount.principals:
            raise StorageError('Storage is unavailable to this principal', code='storage_forbidden')
        return mount

    def references(self, principal):
        """Discover authorized IDs without opening backends or exposing roots."""
        with self._lock:
            return tuple(reference(key) for key, mount in self._mounts.items()
                         if principal in mount.principals)


class LocalStorage:
    def __init__(self, root):
        self.root = Path(root).expanduser().resolve(strict=True)
        if not self.root.is_dir():
            raise ValueError('Storage root must be a directory')

    def open(self):
        return _LocalSession(self.root)

    def import_absolute(self, storage_id, value):
        """Explicit legacy migration; absolute paths never become identities."""
        path = Path(value)
        if not path.is_absolute():
            raise ValueError('Legacy import requires an absolute path')
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(self.root):
            raise StorageError('Legacy path is outside the storage root', code='storage_path_forbidden')
        return reference(storage_id, resolved.relative_to(self.root).as_posix())


class _LocalSession:
    def __init__(self, root):
        self.root = root

    def _native(self, path):
        return filesystem_path(path, resolve=False)

    def _resolve(self, value):
        path = (self.root / relative_path(value)).resolve(strict=True)
        if not path.is_relative_to(self.root):
            raise StorageError('Symlink target is outside the storage root', code='storage_path_forbidden')
        return path

    def _open_fd(self, path, *, directory=False):
        """Pin each resolved POSIX component; never follow a replacement link."""
        if os.open in os.supports_dir_fd and hasattr(os, 'O_NOFOLLOW'):
            descriptor = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                parts = path.relative_to(self.root).parts
                for index, part in enumerate(parts):
                    flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, 'O_NONBLOCK', 0)
                    if index < len(parts) - 1 or directory:
                        flags |= os.O_DIRECTORY
                    child = os.open(part, flags, dir_fd=descriptor)
                    os.close(descriptor)
                    descriptor = child
                result, descriptor = descriptor, None
                return result
            finally:
                if descriptor is not None:
                    os.close(descriptor)
        return os.open(self._native(path), os.O_RDONLY | getattr(os, 'O_BINARY', 0)
                       | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))

    def stat(self, storage_id, value, *, listing=False):
        value = relative_path(value)
        lexical = self.root / value
        attrs = os.lstat(self._native(lexical))
        linked = stat.S_ISLNK(attrs.st_mode)
        try:
            path = self._resolve(value)
            final = os.stat(self._native(path))
        except (StorageError, FileNotFoundError):
            if listing and linked:
                return _entry(storage_id, value, attrs, is_symlink=True, accessible=False)
            raise
        return _entry(storage_id, value, final, is_symlink=linked)

    def revision(self, value):
        path = self._resolve(value)
        attrs = os.stat(self._native(path))
        if not stat.S_ISDIR(attrs.st_mode):
            raise StorageError('Browse target is not a directory', code='storage_not_directory')
        return hashlib.sha256((str(path) + '\0' + _signature(attrs)).encode()).hexdigest()

    def listing_entry(self, storage_id, value, attrs):
        if stat.S_ISLNK(attrs.st_mode or 0):
            return self.stat(storage_id, value, listing=True)
        return _entry(storage_id, value, attrs)

    def names(self, value):
        path = self._resolve(value)
        if os.scandir in os.supports_fd:
            descriptor = self._open_fd(path, directory=True)
            try:
                with os.scandir(descriptor) as entries:
                    for entry in entries:
                        yield _entry_name(entry.name), entry.stat(follow_symlinks=False)
            finally:
                os.close(descriptor)
        else:
            # Windows has no scandir(dir_fd); resolve again around each page.
            with os.scandir(self._native(path)) as entries:
                for entry in entries:
                    yield _entry_name(entry.name), entry.stat(follow_symlinks=False)

    def read(self, value, limit):
        path = self._resolve(value)
        before = os.stat(self._native(path))
        if not stat.S_ISREG(before.st_mode):
            raise StorageError('Preview requires a regular file', code='storage_not_file')
        with os.fdopen(self._open_fd(path), 'rb') as handle:
            opened = os.fstat(handle.fileno())
            if (_signature(before) != _signature(opened) or self._resolve(value) != path):
                raise StorageError('File changed before preview', code='storage_changed')
            if os.name == 'nt':
                # Validate the path belonging to the opened handle, not merely
                # the pathname which another process could have replaced.
                import ctypes
                from ctypes import wintypes
                import msvcrt
                final_path = ctypes.WinDLL('kernel32', use_last_error=True).GetFinalPathNameByHandleW
                final_path.argtypes = [wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD]
                final_path.restype = wintypes.DWORD
                native_handle = msvcrt.get_osfhandle(handle.fileno())
                buffer = ctypes.create_unicode_buffer(32768)
                length = final_path(native_handle, buffer, len(buffer), 0)
                if not length or length >= len(buffer):
                    raise StorageError('Cannot verify the opened file location', code='storage_path_forbidden')
                actual = buffer.value
                if actual.startswith('\\\\?\\UNC\\'):
                    actual = '\\\\' + actual[8:]
                elif actual.startswith('\\\\?\\'):
                    actual = actual[4:]
                if not Path(actual).is_relative_to(self.root):
                    raise StorageError('Opened file is outside the storage root', code='storage_path_forbidden')
            data = handle.read(limit)
            if _signature(os.fstat(handle.fileno())) != _signature(opened):
                raise StorageError('File changed during preview', code='storage_changed')
            return data

    def abort(self):
        pass  # Local enumeration checks its cancellation event between entries.

    def close(self):
        pass


class SFTPStorage:
    """The connector returns an exclusively owned SFTPConnection-like object."""

    def __init__(self, root, connector):
        if not isinstance(root, str) or not root.startswith('/') or '\x00' in root:
            raise ValueError('SFTP storage root must be an absolute POSIX path')
        self.root, self.connector = posixpath.normpath(root), connector

    def open(self):
        connection = self.connector()
        try:
            return _SFTPSession(connection, self.root)
        except BaseException:
            connection.close()
            raise


class _SFTPSession:
    def __init__(self, connection, root):
        self.connection = connection
        self.sftp = connection.sftp
        self.root = posixpath.normpath(self.sftp.normalize(root))
        if not self.root.startswith('/'):
            raise StorageError('Server returned an invalid canonical root', code='storage_path_forbidden')

    def _resolve(self, value):
        value = relative_path(value)
        canonical = posixpath.normpath(self.sftp.normalize(posixpath.join(self.root, value)))
        if not canonical.startswith('/') or posixpath.commonpath((self.root, canonical)) != self.root:
            raise StorageError('Symlink target is outside the storage root', code='storage_path_forbidden')
        return canonical

    def stat(self, storage_id, value, *, listing=False):
        value = relative_path(value)
        attrs = self.sftp.lstat(posixpath.join(self.root, value))
        linked = stat.S_ISLNK(attrs.st_mode or 0)
        try:
            resolved = self._resolve(value)
            final = self.sftp.stat(resolved)
        except (StorageError, FileNotFoundError):
            if listing and linked:
                return _entry(storage_id, value, attrs, is_symlink=True, accessible=False)
            raise
        return _entry(storage_id, value, final, is_symlink=linked)

    def revision(self, value):
        path = self._resolve(value)
        attrs = self.sftp.stat(path)
        if not stat.S_ISDIR(attrs.st_mode or 0):
            raise StorageError('Browse target is not a directory', code='storage_not_directory')
        return hashlib.sha256((path + '\0' + _signature(attrs)).encode()).hexdigest()

    def listing_entry(self, storage_id, value, attrs):
        if stat.S_ISLNK(attrs.st_mode or 0):
            return self.stat(storage_id, value, listing=True)
        # READDIR already supplied these attributes. Do not perform three more
        # round trips for every ordinary entry on the first page.
        return _entry(storage_id, value, attrs)

    def names(self, value):
        # Paramiko's default read_aheads=50 is deliberately not used. Closing the
        # exclusive SFTP connection also closes a partially consumed directory.
        for attrs in self.sftp.listdir_iter(self._resolve(value), read_aheads=1):
            name = _entry_name(attrs.filename)
            yield name, attrs

    def read(self, value, limit):
        path = self._resolve(value)
        before = self.sftp.stat(path)
        if not stat.S_ISREG(before.st_mode or 0):
            raise StorageError('Preview requires a regular file', code='storage_not_file')
        with self.sftp.open(path, 'rb') as handle:
            if (_signature(handle.stat()) != _signature(before) or self._resolve(value) != path):
                raise StorageError('File changed before preview', code='storage_changed')
            data = handle.read(limit)
            if _signature(handle.stat()) != _signature(before):
                raise StorageError('File changed during preview', code='storage_changed')
            return data

    def abort(self):
        # Closing only this owned channel wakes a blocked READDIR/read. The
        # scientific control connection and other browse sessions are separate.
        self.sftp.get_channel().close()

    def close(self):
        self.connection.close()
