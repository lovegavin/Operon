"""Process ownership: identity-checked launch, adoption and confirmed stop.

A launch receipt is written before the process is spawned.  A lost launch reply
is reconciled from that receipt; the attempt is never blindly launched again.
Resources are released only after the owned process tree is confirmed gone.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

import psutil

from .contracts import EngineError, ProcessIdentity
from .telemetry import METRICS


class SupervisorError(EngineError):
    code = 'supervisor_error'


class StopUnconfirmedError(SupervisorError):
    code = 'stop_unconfirmed'


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def boot_identity() -> str:
    """Stable per-boot identity so a reused PID after reboot is detectable."""
    try:
        value = Path('/proc/sys/kernel/random/boot_id').read_text(encoding='utf-8').strip()
        if value:
            return value
    except OSError:
        pass
    try:
        return f'boot:{int(psutil.boot_time())}'
    except (OSError, psutil.Error):
        return 'boot:unknown'


_BOOT = boot_identity()


def identity_for_pid(pid: int) -> ProcessIdentity | None:
    try:
        process = psutil.Process(pid)
        return ProcessIdentity(pid=process.pid, created=process.create_time(), boot_id=_BOOT)
    except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError):
        return None


def identity_alive(identity: ProcessIdentity | dict | None) -> bool:
    identity = ProcessIdentity.from_json(identity) if isinstance(identity, dict) else identity
    if identity is None:
        return False
    if identity.boot_id and identity.boot_id != _BOOT:
        return False
    try:
        process = psutil.Process(identity.pid)
        return (process.create_time() == identity.created and
                process.status() not in (psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD))
    except psutil.NoSuchProcess:
        return False
    except psutil.AccessDenied:
        # Insufficient permission is not proof of death.
        return True
    except (ValueError, TypeError):
        return False


@dataclass(frozen=True)
class LaunchSpec:
    argv: tuple[str, ...]
    cwd: str
    environment: dict
    stdout_path: str
    executable: str | None = None
    stdin_devnull: bool = True


@dataclass(frozen=True)
class LaunchReceipt:
    attempt_id: str
    fence: int
    state: str
    identity: ProcessIdentity | None
    stdout_path: str
    started_at: str
    error: str | None = None
    adopted: bool = False

    def to_json(self) -> dict:
        return {'attempt_id': self.attempt_id, 'fence': self.fence, 'state': self.state,
                'pid': self.identity.pid if self.identity else None,
                'created': self.identity.created if self.identity else None,
                'boot_id': self.identity.boot_id if self.identity else _BOOT,
                'stdout_path': self.stdout_path, 'started_at': self.started_at,
                'error': self.error, 'adopted': self.adopted}


@dataclass(frozen=True)
class StopReceipt:
    attempt_id: str
    confirmed: bool
    identity: ProcessIdentity | None
    exited: bool
    stop_method: str
    tree: tuple[int, ...] = ()
    detail: str = ''


class ProcessSupervisor:
    """Owns launch/stop receipts beneath one attempt directory."""

    def __init__(self, directory, *, adopt_verified=True, boot_id=None):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.adopt_verified = adopt_verified
        self.boot_id = boot_id or _BOOT
        self.lock = threading.RLock()
        self._processes: dict[str, subprocess.Popen] = {}

    def receipt_path(self, attempt_id: str) -> Path:
        return self.directory / f'{attempt_id}.launch.json'

    def read_receipt(self, attempt_id: str) -> LaunchReceipt | None:
        path = self.receipt_path(attempt_id)
        try:
            value = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return None
        identity = None
        if value.get('pid'):
            identity = ProcessIdentity(pid=int(value['pid']), created=float(value['created']),
                                       boot_id=value.get('boot_id'), host=value.get('host'))
        return LaunchReceipt(attempt_id=value.get('attempt_id', attempt_id), fence=int(value.get('fence', 0)),
                             state=value.get('state', 'unknown'), identity=identity,
                             stdout_path=value.get('stdout_path', ''),
                             started_at=value.get('started_at', ''), error=value.get('error'),
                             adopted=bool(value.get('adopted')))

    def _write(self, attempt_id: str, value: dict) -> None:
        path = self.receipt_path(attempt_id)
        temporary = path.with_name(path.name + '.tmp-' + str(os.getpid()) + '-' + threading.current_thread().name)
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(temporary, path)

    def reconcile(self, attempt_id: str, *, fence: int) -> LaunchReceipt | None:
        receipt = self.read_receipt(attempt_id)
        if receipt is None:
            return None
        if receipt.fence != int(fence):
            raise SupervisorError('The launch receipt belongs to a different attempt fence',
                                  code='stale_attempt')
        if receipt.identity is None:
            return receipt
        alive = identity_alive(receipt.identity)
        return LaunchReceipt(**{**receipt.__dict__, 'adopted': alive and receipt.state != 'started'})

    def launch(self, attempt_id: str, *, fence: int, spec: LaunchSpec) -> LaunchReceipt:
        """Idempotent launch.  An existing live receipt is adopted, not duplicated."""
        with self.lock:
            existing = self.read_receipt(attempt_id)
            if existing is not None:
                if existing.fence != int(fence):
                    raise SupervisorError('A launch receipt exists for another fence; refusing to launch',
                                          code='stale_attempt')
                if existing.identity and identity_alive(existing.identity):
                    METRICS.increment('supervisor.launch_adopted')
                    return LaunchReceipt(**{**existing.__dict__, 'state': 'started', 'adopted': True})
                if existing.state in ('launching', 'spawned'):
                    # The receipt proves a spawn may have happened but the
                    # process identity is not verifiable.  Quarantine rather
                    # than risk an execution tree the engine does not own.
                    raise SupervisorError(
                        'A previous launch may have started but its process identity is no longer verifiable; '
                        'the attempt is quarantined for explicit reconciliation', code='recovery_required')
                raise SupervisorError('A terminal launch receipt exists; create a new attempt',
                                      code='stale_attempt')
            stdout = Path(spec.stdout_path)
            stdout.parent.mkdir(parents=True, exist_ok=True)
            stamp = utc_now()
            self._write(attempt_id, {'attempt_id': attempt_id, 'fence': int(fence), 'state': 'launching',
                                     'pid': None, 'created': None, 'boot_id': self.boot_id,
                                     'stdout_path': str(stdout), 'started_at': stamp})
            environment = dict(spec.environment)
            environment.setdefault('PYTHONUNBUFFERED', '1')
            kwargs = {'cwd': spec.cwd, 'env': environment, 'stdin': subprocess.DEVNULL,
                      'stdout': open(stdout, 'ab'), 'stderr': subprocess.STDOUT}
            if os.name == 'nt':
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
            else:
                kwargs['start_new_session'] = True
            try:
                with kwargs['stdout'] as stream:
                    process = subprocess.Popen(list(spec.argv), executable=spec.executable, **kwargs)
            except (OSError, ValueError) as exc:
                self._write(attempt_id, {'attempt_id': attempt_id, 'fence': int(fence), 'state': 'failed',
                                         'pid': None, 'created': None, 'boot_id': self.boot_id,
                                         'stdout_path': str(stdout), 'started_at': stamp,
                                         'error': f'{type(exc).__name__}: {exc}'})
                raise SupervisorError(f'Cannot launch the attempt: {exc}', code='launch_failed') from exc
            identity = identity_for_pid(process.pid)
            if identity is None:
                try:
                    process.kill()
                except OSError:
                    pass
                self._write(attempt_id, {'attempt_id': attempt_id, 'fence': int(fence), 'state': 'failed',
                                         'stdout_path': str(stdout), 'started_at': stamp,
                                         'error': 'The spawned process disappeared before its identity was recorded'})
                raise SupervisorError('The spawned process disappeared before its identity was recorded',
                                      code='launch_failed')
            self._write(attempt_id, {'attempt_id': attempt_id, 'fence': int(fence), 'state': 'started',
                                     'pid': identity.pid, 'created': identity.created,
                                     'boot_id': identity.boot_id, 'stdout_path': str(stdout),
                                     'started_at': stamp})
            self._processes[attempt_id] = process
            METRICS.increment('supervisor.launches')
            return LaunchReceipt(attempt_id=attempt_id, fence=int(fence), state='started',
                                 identity=identity, stdout_path=str(stdout), started_at=stamp)

    def poll_status(self, attempt_id: str) -> tuple[str, int | None]:
        """Non-blocking process status for the current supervisor process.

        Across a supervisor restart the exit code is unavailable unless the
        receipt recorded it; callers must treat that as recovery-required
        rather than assuming success.
        """
        with self.lock:
            process = self._processes.get(attempt_id)
            if process is not None:
                code = process.poll()
                if code is None:
                    return 'running', None
                receipt = self.read_receipt(attempt_id)
                if receipt is not None and receipt.state not in ('exited', 'stopped', 'failed'):
                    value = receipt.to_json()
                    value.update(state='exited', exit_code=int(code), exited_at=utc_now())
                    value.pop('adopted', None)
                    self._write(attempt_id, value)
                self._processes.pop(attempt_id, None)
                return 'exited', int(code)
            receipt = self.read_receipt(attempt_id)
            if receipt is None:
                return 'missing', None
            if receipt.state in ('exited', 'stopped'):
                path = self.receipt_path(attempt_id)
                try:
                    value = json.loads(path.read_text(encoding='utf-8'))
                except (OSError, ValueError):
                    value = {}
                return receipt.state, (int(value['exit_code']) if value.get('exit_code') is not None else None)
            if receipt.state == 'failed':
                return 'failed', None
            if receipt.identity is not None and identity_alive(receipt.identity):
                return 'running', None
            return 'lost', None

    def wait(self, receipt: LaunchReceipt, timeout: float | None = None) -> int | None:
        if receipt.identity is None:
            return None
        try:
            process = psutil.Process(receipt.identity.pid)
            if process.create_time() != receipt.identity.created:
                return None
            return process.wait(timeout=timeout)
        except psutil.TimeoutExpired:
            return None
        except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError):
            return None

    def stop(self, attempt_id: str, *, fence: int | None = None, timeout=10.0) -> StopReceipt:
        """Stop the recorded owned tree and confirm it is gone before returning."""
        receipt = self.read_receipt(attempt_id)
        if receipt is None:
            return StopReceipt(attempt_id=attempt_id, confirmed=True, identity=None, exited=True,
                               stop_method='no-process')
        if fence is not None and receipt.fence != int(fence):
            raise SupervisorError('The launch receipt belongs to a stale fence', code='stale_attempt')
        if receipt.identity is None:
            return StopReceipt(attempt_id=attempt_id, confirmed=True, identity=None, exited=True,
                               stop_method='no-identity')
        if receipt.identity.boot_id and receipt.identity.boot_id != self.boot_id:
            return StopReceipt(attempt_id=attempt_id, confirmed=True, identity=receipt.identity,
                               exited=True, stop_method='different-boot')
        if not identity_alive(receipt.identity):
            return StopReceipt(attempt_id=attempt_id, confirmed=True, identity=receipt.identity,
                               exited=True, stop_method='already-exited')
        tree: list[int] = []
        try:
            root = psutil.Process(receipt.identity.pid)
        except psutil.NoSuchProcess:
            return StopReceipt(attempt_id=attempt_id, confirmed=True, identity=receipt.identity,
                               exited=True, stop_method='race-exited')
        try:
            tree = [child.pid for child in root.children(recursive=True)]
        except psutil.Error:
            tree = []
        # Bind the live Popen handle to the verified identity; never stop a PID
        # selected by name or a reused PID.  Suspension requires additional
        # process rights that are not guaranteed under an AppContainer sandbox,
        # so the owned tree is terminated directly and confirmed below.
        children = []
        try:
            handle = psutil.Process(receipt.identity.pid)
            children = handle.children(recursive=True)
        except psutil.NoSuchProcess:
            handle = None
        except psutil.AccessDenied as exc:
            raise StopUnconfirmedError(f'Insufficient permission to enumerate the owned process tree: {exc}',
                                       details={'attempt_id': attempt_id, 'tree': tree}) from exc
        for child in reversed(children):
            try:
                child.kill()
            except psutil.NoSuchProcess:
                continue
            except psutil.AccessDenied:
                continue
        if handle is not None:
            try:
                handle.kill()
            except psutil.NoSuchProcess:
                pass
            except psutil.AccessDenied:
                process = self._processes.get(attempt_id)
                if process is not None:
                    try:
                        process.kill()
                    except OSError as exc:
                        raise StopUnconfirmedError(
                            'Insufficient permission to stop the owned process tree',
                            details={'attempt_id': attempt_id, 'tree': tree}) from exc
                else:
                    self._taskkill(receipt.identity.pid, attempt_id)
        try:
            psutil.wait_procs([item for item in [handle, *children] if item is not None],
                              timeout=timeout)
        except psutil.Error:
            pass
        deadline = time.monotonic() + max(0.0, timeout)
        while time.monotonic() < deadline:
            if not identity_alive(receipt.identity):
                remaining = []
                for pid in tree:
                    try:
                        child = psutil.Process(pid)
                        if child.is_running() and child.status() != psutil.STATUS_ZOMBIE:
                            remaining.append(pid)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                if not remaining:
                    self._mark_stopped(attempt_id)
                    METRICS.increment('supervisor.stops')
                    return StopReceipt(attempt_id=attempt_id, confirmed=True, identity=receipt.identity,
                                       exited=True, stop_method='owned-tree', tree=tuple(tree))
            time.sleep(0.02)
        raise StopUnconfirmedError(
            'The owned process tree did not confirm termination; the resource lease remains charged',
            details={'attempt_id': attempt_id, 'tree': tree, 'pid': receipt.identity.pid})

    @staticmethod
    def _taskkill(pid: int, attempt_id: str):
        """Last-resort Windows-owned termination; failure stays visible."""
        if os.name != 'nt':
            raise StopUnconfirmedError('Insufficient permission to stop the owned process tree',
                                       details={'attempt_id': attempt_id, 'pid': pid})
        try:
            result = subprocess.run(['taskkill', '/F', '/T', '/PID', str(pid)],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise StopUnconfirmedError('The owned process tree could not be terminated',
                                       details={'attempt_id': attempt_id, 'pid': pid}) from exc
        if result.returncode not in (0, 128):
            raise StopUnconfirmedError('The owned process tree could not be terminated',
                                       details={'attempt_id': attempt_id, 'pid': pid,
                                                'taskkill_exit': result.returncode})

    def _mark_stopped(self, attempt_id: str):
        receipt = self.read_receipt(attempt_id)
        if receipt is None:
            return
        value = receipt.to_json()
        value.update(state='stopped', stopped_at=utc_now())
        value.pop('adopted', None)
        process = self._processes.pop(attempt_id, None)
        if process is not None:
            try:
                process.wait(timeout=1)
            except (subprocess.TimeoutExpired, OSError):
                pass
            if process.returncode is not None:
                value['exit_code'] = int(process.returncode)
        self._write(attempt_id, value)
