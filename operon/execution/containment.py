"""Linux subreaper monitor for generation-bound invocation trees.

Runs in the management Python, not in the scientific environment. A child that
double-forks or creates a new session is adopted here rather than disappearing
from ownership. Only ECHILD after root completion produces tree-exit evidence.
If this monitor dies, no proof is synthesized and the environment stays pinned.
"""
from __future__ import annotations

import ctypes
import errno
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def write(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.' + str(os.getpid()) + '.tmp')
    with temporary.open('w', encoding='utf-8') as stream:
        json.dump(value, stream)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def main():
    import psutil
    request = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    if not sys.platform.startswith('linux'):
        raise RuntimeError('Subreaper containment requires Linux')
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
        raise OSError(ctypes.get_errno(), 'Cannot establish process containment')
    cancelled = False
    def stop(signum, frame):
        nonlocal cancelled
        cancelled = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    identity = {'pid': os.getpid(), 'created': psutil.Process().create_time(), 'boot_id': request['boot_id'], 'host': None}
    write(request['ready'], {'schema_version': 1, 'attempt_id': request['attempt_id'],
          'fence': request['fence'], 'ready': True, 'identity': identity})
    deadline = time.monotonic() + 60
    while not Path(request['start_gate']).exists():
        if cancelled:
            # Handlers and subreaper ownership are active, but no worker has
            # been spawned. ECHILD is still required for terminal tree proof.
            try:
                os.waitpid(-1, os.WNOHANG)
            except ChildProcessError:
                write(request['proof'], {'attempt_id': request['attempt_id'], 'fence': request['fence'],
                      'tree_exited': True, 'method': 'linux-subreaper', 'identity': identity,
                      'exit_code': 130, 'cancelled': True})
                return 130
            raise RuntimeError('Unexpected child before invocation start')
        if time.monotonic() > deadline:
            return 125
        time.sleep(.01)
    process = subprocess.Popen(request['argv'], cwd=request['cwd'], env=request['environment'],
                               stdin=subprocess.DEVNULL)
    root_code = None
    while True:
        if cancelled:
            # Repeated passes handle fork races; termination is proven by waitpid,
            # not by assuming an enumerated snapshot was complete.
            for child in reversed(psutil.Process().children(recursive=True)):
                try:
                    child.kill()
                except psutil.NoSuchProcess:
                    pass
        try:
            pid, status = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            if root_code is None:
                raise RuntimeError('Root exit status missing')
            break
        if pid == process.pid:
            root_code = os.waitstatus_to_exitcode(status)
            process.returncode = root_code
        elif pid == 0:
            time.sleep(.02)
    write(request['proof'], {'attempt_id': request['attempt_id'], 'fence': request['fence'],
          'tree_exited': True, 'method': 'linux-subreaper', 'identity': identity,
          'exit_code': root_code, 'cancelled': cancelled})
    return 130 if cancelled else (root_code if root_code >= 0 else 128 - root_code)


if __name__ == '__main__':
    raise SystemExit(main())
