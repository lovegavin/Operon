"""Process-bound Windows cwd aliases, independent of operator or language.

CreateProcess does not support an extended-length current directory. A junction
changes only its spelling: relative I/O still reaches the caller's exact working
directory. This is not a workaround for third-party tools' own path limitations.
"""
from contextlib import ExitStack
import json
import os
from pathlib import Path
import tempfile


def _windows_local_app_data():
    """Ask Windows, not a worker's redirected TEMP/LOCALAPPDATA environment."""
    import ctypes
    import uuid
    shell = ctypes.WinDLL('shell32', use_last_error=True)
    ole = ctypes.WinDLL('ole32', use_last_error=True)
    ole.CoInitializeEx.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    ole.CoInitializeEx.restype = ctypes.c_long
    ole.CoUninitialize.argtypes = []
    ole.CoUninitialize.restype = None
    ole.CoTaskMemFree.argtypes = [ctypes.c_void_p]
    ole.CoTaskMemFree.restype = None
    shell.SHGetKnownFolderPath.argtypes = [ctypes.c_void_p, ctypes.c_uint32,
                                         ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
    shell.SHGetKnownFolderPath.restype = ctypes.c_long
    initialized = ole.CoInitializeEx(None, 0)
    # An existing STA is equally usable; only balance our successful COM init.
    if initialized < 0 and initialized != -2147417850:  # RPC_E_CHANGED_MODE
        raise OSError(f'Cannot initialize Windows folder lookup: {initialized:#x}')
    pointer = ctypes.c_void_p()
    folder = (ctypes.c_ubyte * 16).from_buffer_copy(
        uuid.UUID('F1B32785-6FBA-4FCF-9D55-7B8E7F157091').bytes_le)
    try:
        result = shell.SHGetKnownFolderPath(ctypes.byref(folder), 0, None,
                                            ctypes.byref(pointer))
        if result < 0 or not pointer.value:
            raise OSError(f'Cannot locate Windows local application data: {result:#x}')
        return Path(ctypes.wstring_at(pointer))
    finally:
        if pointer.value:
            ole.CoTaskMemFree(pointer)
        if initialized >= 0:
            ole.CoUninitialize()


def _alias_root(temp_root, api):
    from operon.environment_store.windows_paths import _logical_path, _plain_directory
    # Worker TEMP is deliberately task-scoped and may be hundreds of characters
    # long. Metadata aliases must not inherit that path or change where task
    # temporary data is stored. Only the small alias/journal live outside the run.
    explicit = temp_root is not None
    root = _logical_path(Path(temp_root if explicit else _windows_local_app_data()).resolve(strict=True))
    _plain_directory(root)
    api.local_root(root)
    proposed = root if explicit else root / 'Operon' / 'ProcessCwd'
    if len(str(proposed).encode('utf-16-le')) // 2 > 180:
        raise OSError('Windows process alias directory is too long; configure a shorter local metadata root.')
    if not explicit:
        for part in ('Operon', 'ProcessCwd'):
            root /= part
            _plain_directory(root, create=True)
    return root


class ProcessDirectory:
    """Keep an alias until its owner confirms the entire process tree stopped.

    A crash leaves a tiny journal/alias, never a copied data directory. Uncertain
    shutdown retains these for diagnosis; no automatic recursive deletion is
    attempted. Separate launches, including the same cwd, have separate aliases.
    """

    def __init__(self, cwd, *, temp_root=None):
        self.path = cwd
        self.directory = self.alias = self.target = None
        self.scope = None
        self.handles = ExitStack()
        if os.name != 'nt' or cwd is None:
            return
        from operon.bytecode import io_path
        from operon.environment_store.windows_paths import (
            _NativeJunctions, _logical_path,
        )
        target = _logical_path(io_path(Path(cwd).absolute()).resolve(strict=True))
        if not io_path(target).is_dir():
            raise NotADirectoryError(str(target))
        # Always strip the extended spelling from short cwd values as well.
        if len(str(target).encode('utf-16-le')) // 2 < 240:
            self.path = str(target)
            return
        self.api = _NativeJunctions()
        root = _alias_root(temp_root, self.api)
        from .process_path_scopes import worker_scope
        scoped = worker_scope(target)
        if scoped is not None:
            self.scope, root = scoped
        self.directory = Path(tempfile.mkdtemp(prefix='operon-cwd-', dir=root))
        self.target, self.alias = target, self.directory / 'cwd'
        try:
            self._journal('preparing')
            if len(str(self.alias).encode('utf-16-le')) // 2 >= 260:
                raise OSError('Process cwd metadata alias exceeds Windows launch limits')
            self.api.create(self.alias, target)
            self.api.verify(self.alias, target)
            # Pin the reparse entry against replacement for the process lifetime.
            self.handles.enter_context(self.api._open(self.alias))
            self._journal('prepared')
            self.path = str(self.alias)
        except BaseException as error:
            try:
                self.finish(confirmed=True)
            except OSError as cleanup:
                error.add_note(f'Alias metadata cleanup requires attention: {cleanup}')
            raise

    def _journal(self, state):
        from operon.engine.fs import atomic_json
        atomic_json(self.directory / 'owner.json', {
            'format': 'operon.process-cwd', 'version': 2 if self.scope else 1, 'owner_pid': os.getpid(),
            'target': str(self.target), 'alias': str(self.alias), 'state': state,
            **({'scope': self.scope} if self.scope else {}),
        })

    def finish(self, *, confirmed):
        self.handles.close()
        if self.directory is None:
            return
        if not confirmed:
            self._journal('recovery_required')
            return
        from operon.environment_store.windows_paths import _entry
        if _entry(self.alias) is not None:
            self.api.verify(self.alias, self.target)
            self.api.remove(self.alias)  # RemoveDirectory: metadata only.
        (self.directory / 'owner.json').unlink(missing_ok=True)
        self.directory.rmdir()  # Refuse unknown extra contents; never recurse.
        self.directory = None
