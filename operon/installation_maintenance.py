"""Windows Setup maintenance exclusion, independent of profile/runtime selection.

The mutex uses the immutable installation profile UUID shared with Setup. It is
released by Windows on a crash; a stale file cannot permanently disable startup.
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import uuid

from .engine.contracts import BusyError


class InstallationBusy(BusyError):
    code = 'installation_maintenance'


def mutex_name(root):
    marker = Path(root) / 'operon-install.json'
    if not marker.is_file():
        return None
    record = json.loads(marker.read_text(encoding='utf-8'))
    value = record['profile_id']
    if not isinstance(value, str) or uuid.UUID(value).hex != value:
        raise ValueError('Invalid installation profile identity')
    return 'Local\\OperonMaintenance-' + value


@contextmanager
def start_guard(root):
    if os.name != 'nt':
        yield
        return
    name = mutex_name(root)
    if name is None:
        yield
        return
    import ctypes
    from ctypes import wintypes
    api = ctypes.WinDLL('kernel32', use_last_error=True)
    api.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
    api.CreateMutexW.restype = wintypes.HANDLE
    api.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    api.WaitForSingleObject.restype = wintypes.DWORD
    api.ReleaseMutex.argtypes = (wintypes.HANDLE,)
    api.CloseHandle.argtypes = (wintypes.HANDLE,)
    handle = api.CreateMutexW(None, False, name)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    acquired = False
    try:
        status = api.WaitForSingleObject(handle, 0)
        acquired = status in (0, 0x80)  # acquired or abandoned
        if not acquired:
            if status == 0xFFFFFFFF:
                raise ctypes.WinError(ctypes.get_last_error())
            raise InstallationBusy('Operon is being updated or uninstalled; automatic restart is paused')
        yield
    finally:
        if acquired:
            api.ReleaseMutex(handle)
        api.CloseHandle(handle)


def installation_root():
    return Path(__file__).resolve().parents[1]


def require_idle(root=None):
    """Refuse agent work while Setup is replacing this installation."""
    target = Path(root) if root is not None else installation_root()
    if maintenance_active(target):
        raise SystemExit('Operon is being updated or uninstalled; start again after Setup finishes.')


def maintenance_active(root):
    if os.name != 'nt':
        return False
    name = mutex_name(root)
    if name is None:
        return False
    import ctypes
    from ctypes import wintypes
    api = ctypes.WinDLL('kernel32', use_last_error=True)
    api.OpenEventW.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR)
    api.OpenEventW.restype = wintypes.HANDLE
    api.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    api.WaitForSingleObject.restype = wintypes.DWORD
    api.CloseHandle.argtypes = (wintypes.HANDLE,)
    handle = api.OpenEventW(0x00100000, False, name + '-active')
    if not handle:
        error = ctypes.get_last_error()
        if error == 2:
            return False
        raise ctypes.WinError(error)
    try:
        result = api.WaitForSingleObject(handle, 0)
        if result == 0xFFFFFFFF:
            raise ctypes.WinError(ctypes.get_last_error())
        return result == 0
    finally:
        api.CloseHandle(handle)
