"""Small filesystem primitives kept inside the engine boundary.

The engine must be usable by a scientific operator without importing a UI
server.  These are process-safe reentrant file locks and atomic JSON writes for
engine-owned directories only.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import threading
import time
import uuid

_STATES: dict[str, dict] = {}
_STATES_LOCK = threading.Lock()


class FileLock:
    """Reentrant per thread; the OS lock is released even after a crash."""

    def __init__(self, path, timeout=30.0):
        self.path, self.timeout = Path(path), timeout
        key = os.path.normcase(str(self.path.resolve()))
        with _STATES_LOCK:
            self.state = _STATES.setdefault(key, {'mutex': threading.RLock(), 'depth': 0,
                                                  'handle': None})

    def __enter__(self):
        state = self.state
        state['mutex'].acquire()
        try:
            if not state['depth']:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                handle = open(self.path, 'a+b')
                handle.seek(0, os.SEEK_END)
                if not handle.tell():
                    handle.write(b'\0'); handle.flush()
                deadline = time.monotonic() + self.timeout
                while True:
                    try:
                        handle.seek(0)
                        if os.name == 'nt':
                            import msvcrt
                            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                        else:
                            import fcntl
                            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except OSError:
                        if time.monotonic() >= deadline:
                            handle.close()
                            raise TimeoutError(f'Engine file is busy: {self.path}')
                        time.sleep(0.05)
                state['handle'] = handle
            state['depth'] += 1
            return self
        except BaseException:
            state['mutex'].release()
            raise

    def __exit__(self, *exc):
        state = self.state
        try:
            state['depth'] -= 1
            if not state['depth'] and state['handle'] is not None:
                state['handle'].close()
                state['handle'] = None
        finally:
            state['mutex'].release()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(16):
        temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
        try:
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                                 getattr(os, 'O_BINARY', 0), 0o600)
            break
        except FileExistsError:
            continue
    else:
        raise FileExistsError(f'Unable to allocate a temporary JSON file beside {path}')
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
