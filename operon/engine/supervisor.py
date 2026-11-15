"""Process ownership: identity-checked launch, adoption and confirmed stop.

A launch receipt is written before the process is spawned.  A lost launch reply
is reconciled from that receipt; the attempt is never blindly launched again.
Resources are released only after the owned process tree is confirmed gone.
"""
from __future__ import annotations

from dataclasses import dataclass
from contextlib import contextmanager, nullcontext
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

import psutil

from .contracts import EngineError, ProcessIdentity
from .fs import FileLock, atomic_json
from .telemetry import METRICS


class SupervisorError(EngineError):
    code = 'supervisor_error'


class StopUnconfirmedError(SupervisorError):
    code = 'stop_unconfirmed'


class PreparationRejectedError(EngineError):
    """Definite rejection before launch; the durable negative receipt exists."""

    code = 'preparation_rejected'


def preparation_rejection_proof(value, *, attempt_id, fence):
    """Validate the indivisible negative receipt, not absence of a process."""
    proof = value.get('no_spawn_proof') if isinstance(value, dict) else None
    return (isinstance(proof, dict) and value.get('outcome') == 'rejected_before_launch'
            and value.get('state') == 'failed' and value.get('attempt_id') == attempt_id
            and type(value.get('fence')) is int and value['fence'] == fence
            and 'pid' in value and value['pid'] is None
            and 'created' in value and value['created'] is None
            and proof == {'schema_version': 1, 'attempt_id': attempt_id, 'fence': fence,
                          'method': 'preparation-rejected', 'tree_exited': True,
                          'identity': None, 'environment_lease_acquired': False}
            and type(proof.get('schema_version')) is int and type(proof.get('fence')) is int
            and proof.get('tree_exited') is True and proof.get('environment_lease_acquired') is False)


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
    generation_id: str | None = None


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

    def __init__(self, directory, *, adopt_verified=True, boot_id=None, environment_store=None,
                 ready_timeout_seconds=10.0):
        if not 0 < ready_timeout_seconds <= 10:
            raise ValueError('Monitor readiness timeout must be in (0, 10] seconds')
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.adopt_verified = adopt_verified
        self.boot_id = boot_id or _BOOT
        self.lock = threading.RLock()
        self._processes: dict[str, subprocess.Popen] = {}
        self.environment_store = environment_store
        self._generation_jobs = {}
        self.ready_timeout_seconds = ready_timeout_seconds

    def receipt_path(self, attempt_id: str) -> Path:
        return self.directory / f'{attempt_id}.launch.json'

    def _launch_lock(self, attempt_id):
        key = hashlib.sha256(attempt_id.encode('utf-8')).hexdigest()
        return FileLock(self.directory / '.launch-locks' / (key + '.lock'))

    @contextmanager
    def _serialized_launch(self, attempt_id):
        with self.lock:
            try:
                guard = self._launch_lock(attempt_id)
                guard.__enter__()
            except Exception as exc:
                # Another supervisor can still own the attempt, including a
                # spawn whose receipt has not reached this process yet.
                raise SupervisorError('Launch ownership lock could not be acquired',
                                      code='recovery_required') from exc
            try:
                yield
            finally:
                try:
                    guard.__exit__(*sys.exc_info())
                except Exception as exc:
                    raise SupervisorError('Launch ownership lock release is uncertain',
                                          code='recovery_required') from exc

    def _execution_markers(self, attempt_id):
        return tuple(self.directory / (attempt_id + suffix) for suffix in
                     ('.launch.json', '.environment.json', '.containment.json', '.ready.json',
                      '.start', '.tree-exit.json'))

    def _monitor_ready(self, attempt_id, *, fence, identity):
        try:
            with (self.directory / (attempt_id + '.ready.json')).open('rb') as stream:
                raw = stream.read(4097)
            value = json.loads(raw) if len(raw) <= 4096 else None
            return (isinstance(value, dict) and type(value.get('schema_version')) is int
                    and value['schema_version'] == 1 and value.get('attempt_id') == attempt_id
                    and type(value.get('fence')) is int and value['fence'] == fence
                    and value.get('ready') is True and identity is not None
                    and value.get('identity') == identity.to_json())
        except (OSError, ValueError):
            return False

    def _wait_monitor_ready(self, attempt_id, *, fence, identity, process):
        deadline = time.monotonic() + self.ready_timeout_seconds
        path = self.directory / (attempt_id + '.ready.json')
        while True:
            if process.poll() is not None:
                raise SupervisorError('Containment monitor exited before readiness', code='recovery_required')
            if os.path.lexists(path):
                if self._monitor_ready(attempt_id, fence=fence, identity=identity):
                    return
                raise SupervisorError('Containment readiness identity differs', code='recovery_required')
            if time.monotonic() >= deadline:
                raise SupervisorError('Containment readiness was not confirmed within its timeout',
                                      code='recovery_required')
            time.sleep(.01)

    def _requires_monitor_ready(self, attempt_id):
        return os.name != 'nt' and os.path.lexists(self.directory / (attempt_id + '.environment.json'))

    def record_preparation_rejection(self, attempt_id, *, fence, error, stdout_path=''):
        """Commit a no-spawn outcome only while this attempt has no execution history.

        Any existing marker, including malformed or terminal records, is a
        reconciliation case. A missing receipt alone never authorizes release.
        The same lock covers launch, across threads and supervisor processes.
        """
        try:
            with self.lock, self._launch_lock(attempt_id):
                environment_lock = self.environment_store.lock if self.environment_store is not None else nullcontext()
                with environment_lock:
                    markers = self._execution_markers(attempt_id)
                    if self.environment_store is not None:
                        markers += (self.environment_store.root / 'leases' / (attempt_id + '.json'),)
                    if (type(fence) is not int or fence < 1 or attempt_id in self._processes
                            or attempt_id in self._generation_jobs
                            or any(os.path.lexists(path) for path in markers)):
                        raise SupervisorError('Attempt may have crossed its launch boundary; rejection is unproven',
                                              code='recovery_required')
                    value = {'attempt_id': attempt_id, 'fence': fence, 'state': 'failed',
                             'pid': None, 'created': None, 'boot_id': self.boot_id,
                             'stdout_path': str(stdout_path), 'started_at': utc_now(),
                             'error': str(error)[:4096], 'outcome': 'rejected_before_launch',
                             'no_spawn_proof': {'schema_version': 1, 'attempt_id': attempt_id,
                                 'fence': fence, 'method': 'preparation-rejected', 'tree_exited': True,
                                 'identity': None, 'environment_lease_acquired': False}}
                    atomic_json(self.receipt_path(attempt_id), value)
                    return self.read_receipt(attempt_id)
        except SupervisorError:
            raise
        except Exception as exc:
            # Failure to prove/write a negative outcome retains all grants.
            raise SupervisorError('Preparation rejection could not be durably proven',
                                  code='recovery_required') from exc

    def preparation_rejected(self, attempt_id, *, fence):
        try:
            value = json.loads(self.receipt_path(attempt_id).read_text(encoding='utf-8'))
            markers = self._execution_markers(attempt_id)[1:]
            if self.environment_store is not None:
                markers += (self.environment_store.root / 'leases' / (attempt_id + '.json'),)
            return (preparation_rejection_proof(value, attempt_id=attempt_id, fence=fence)
                    and not any(os.path.lexists(path) for path in markers))
        except (OSError, ValueError):
            return False

    def no_spawn_proven(self, attempt_id, *, fence):
        if self.preparation_rejected(attempt_id, fence=fence):
            return True
        try:
            launch = json.loads(self.receipt_path(attempt_id).read_text(encoding='utf-8'))
            proof = json.loads((self.directory / (attempt_id + '.tree-exit.json')).read_text(encoding='utf-8'))
            return (isinstance(launch, dict) and isinstance(proof, dict)
                    and launch.get('outcome') != 'rejected_before_launch'
                    and all(value.get('attempt_id') == attempt_id and type(value.get('fence')) is int
                            and value['fence'] == fence for value in (launch, proof))
                    and launch.get('state') == 'failed' and launch.get('pid') is None
                    and launch.get('created') is None and proof.get('identity') is None
                    and proof.get('method') == 'never-spawned' and proof.get('tree_exited') is True)
        except (OSError, ValueError):
            return False

    @staticmethod
    def _containment_helper():
        if not sys.platform.startswith('linux'):
            raise PreparationRejectedError('Generation containment is not available on this platform')
        helper = Path(__file__).resolve().parents[1] / 'execution' / 'containment.py'
        if not helper.is_file():
            raise PreparationRejectedError('Generation containment helper is unavailable')
        return helper

    def read_receipt(self, attempt_id: str) -> LaunchReceipt | None:
        path = self.receipt_path(attempt_id)
        try:
            value = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return None
        if (not isinstance(value, dict) or value.get('attempt_id') != attempt_id
                or type(value.get('fence')) is not int or value['fence'] < 1):
            return None
        identity = None
        if value.get('pid'):
            try:
                identity = ProcessIdentity(pid=int(value['pid']), created=float(value['created']),
                                           boot_id=value.get('boot_id'), host=value.get('host'))
            except (KeyError, TypeError, ValueError, OverflowError):
                return None
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
        if (alive and self._requires_monitor_ready(attempt_id)
                and (not self._monitor_ready(attempt_id, fence=fence, identity=receipt.identity)
                     or not os.path.lexists(self.directory / (attempt_id + '.start')))):
            raise SupervisorError('A live containment monitor has not completed its start handshake',
                                  code='recovery_required')
        return LaunchReceipt(**{**receipt.__dict__, 'adopted': alive and receipt.state != 'started'})

    def launch(self, attempt_id: str, *, fence: int, spec: LaunchSpec) -> LaunchReceipt:
        """Idempotent launch.  An existing live receipt is adopted, not duplicated."""
        with self._serialized_launch(attempt_id):
            try:
                existing = self.read_receipt(attempt_id)
            except (KeyError, TypeError, ValueError) as exc:
                raise SupervisorError('Existing launch receipt cannot be reconciled',
                                      code='recovery_required') from exc
            if existing is not None:
                if existing.fence != int(fence):
                    raise SupervisorError('A launch receipt exists for another fence; refusing to launch',
                                          code='recovery_required')
                if existing.identity and identity_alive(existing.identity):
                    if (self._requires_monitor_ready(attempt_id)
                            and (not self._monitor_ready(attempt_id, fence=fence, identity=existing.identity)
                                 or not os.path.lexists(self.directory / (attempt_id + '.start')))):
                        raise SupervisorError('Existing containment monitor start handshake is unproven',
                                              code='recovery_required')
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
                                      code='recovery_required')
            if any(os.path.lexists(path) for path in self._execution_markers(attempt_id)):
                raise SupervisorError('Execution marker exists without a verifiable launch receipt',
                                      code='recovery_required')
            containment_helper = None
            if spec.generation_id and os.name != 'nt':
                try:
                    containment_helper = self._containment_helper()
                except PreparationRejectedError as exc:
                    self.record_preparation_rejection(attempt_id, fence=fence, error=str(exc),
                                                       stdout_path=spec.stdout_path)
                    raise
            stdout = Path(spec.stdout_path)
            stdout.parent.mkdir(parents=True, exist_ok=True)
            stamp = utc_now()
            if spec.generation_id:
                if self.environment_store is None:
                    self.record_preparation_rejection(attempt_id, fence=fence,
                        error='Managed generation requires its environment store', stdout_path=spec.stdout_path)
                    raise PreparationRejectedError('Managed generation requires its environment store')
                try:
                    with self.environment_store.lock:
                        if os.path.lexists(self.environment_store.root / 'leases' / (attempt_id + '.json')):
                            raise SupervisorError('An environment lease exists without a launch receipt',
                                                  code='recovery_required')
                        self.environment_store.acquire(spec.generation_id, attempt_id=attempt_id, fence=fence)
                        self.environment_store.spawning(attempt_id, fence, self.directory)
                        atomic_json(self.directory / (attempt_id + '.environment.json'),
                                    {'generation_id': spec.generation_id, 'fence': fence})
                except Exception as exc:
                    # Acquisition may already be durable even if its reply or
                    # the companion marker failed. Never discard that pin.
                    raise SupervisorError('Generation launch preparation requires reconciliation',
                                          code='recovery_required') from exc
            self._write(attempt_id, {'attempt_id': attempt_id, 'fence': int(fence), 'state': 'launching',
                                     'pid': None, 'created': None, 'boot_id': self.boot_id,
                                     'stdout_path': str(stdout), 'started_at': stamp})
            environment = dict(spec.environment)
            environment.setdefault('PYTHONUNBUFFERED', '1')
            kwargs = {'cwd': spec.cwd, 'env': environment, 'stdin': subprocess.DEVNULL,
                      'stdout': open(stdout, 'ab'), 'stderr': subprocess.STDOUT}
            if os.name == 'nt':
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
                if spec.generation_id:
                    from operon.processes import _WindowsJob
                    self._generation_jobs[attempt_id] = _WindowsJob()
                    kwargs['creationflags'] |= 0x00000004  # attach before first instruction
            else:
                kwargs['start_new_session'] = True
            launch_argv = list(spec.argv)
            launch_executable = spec.executable
            if os.name == 'nt' and not launch_executable and os.path.isabs(launch_argv[0]):
                from operon.bytecode import executable_path
                launch_executable = executable_path(launch_argv[0])
            if spec.generation_id and os.name != 'nt':
                request_path = self.directory / (attempt_id + '.containment.json')
                atomic_json(request_path, {'argv': launch_argv, 'cwd': spec.cwd, 'environment': environment,
                    'attempt_id': attempt_id, 'fence': fence, 'boot_id': self.boot_id,
                    'proof': str(self.directory / (attempt_id + '.tree-exit.json')),
                    'ready': str(self.directory / (attempt_id + '.ready.json')),
                    'start_gate': str(self.directory / (attempt_id + '.start'))})
                # A standalone management Python keeps packages beside its
                # runtime, not in global site-packages. -I intentionally drops
                # inherited paths, so bind the already loaded management psutil
                # explicitly; scientific target paths must never enter here.
                monitor_bootstrap = ('import sys,runpy;sys.path.insert(0,sys.argv[1]);'
                                     'sys.argv=sys.argv[2:];runpy.run_path(sys.argv[0],run_name="__main__")')
                launch_argv = [sys.executable, '-I', '-B', '-c', monitor_bootstrap,
                    str(Path(psutil.__file__).resolve().parent.parent),
                    str(containment_helper), str(request_path)]
                launch_executable = None
                # The monitor needs the management environment; the actual child
                # receives only the isolated scientific environment from request.
                kwargs['env'] = dict(os.environ)
            try:
                process = None
                with kwargs['stdout'] as stream:
                    process = subprocess.Popen(launch_argv, executable=launch_executable, **kwargs)
                    if spec.generation_id and os.name == 'nt':
                        try:
                            self._generation_jobs[attempt_id].attach(process)
                        except BaseException:
                            process.kill()
                            process.wait(timeout=5)
                            self._generation_jobs[attempt_id].close()
                            # Containment could not be established. Keep the lease.
                            raise
            except Exception as exc:
                if process is not None:
                    raise SupervisorError('Launch crossed the spawn boundary; containment requires reconciliation',
                                          code='recovery_required') from exc
                self._write(attempt_id, {'attempt_id': attempt_id, 'fence': int(fence), 'state': 'failed',
                                         'pid': None, 'created': None, 'boot_id': self.boot_id,
                                         'stdout_path': str(stdout), 'started_at': stamp,
                                         'error': f'{type(exc).__name__}: {exc}'})
                if spec.generation_id:
                    atomic_json(self.directory / (attempt_id + '.tree-exit.json'),
                        {'attempt_id': attempt_id, 'fence': fence, 'tree_exited': True, 'method': 'never-spawned'})
                    self.environment_store.release(attempt_id, fence)
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
                                      code='recovery_required')
            try:
                self._processes[attempt_id] = process
                if spec.generation_id and os.name != 'nt':
                    self._write(attempt_id, {'attempt_id': attempt_id, 'fence': int(fence), 'state': 'spawned',
                        'pid': identity.pid, 'created': identity.created, 'boot_id': identity.boot_id,
                        'stdout_path': str(stdout), 'started_at': stamp})
                    self._wait_monitor_ready(attempt_id, fence=fence, identity=identity, process=process)
                self._write(attempt_id, {'attempt_id': attempt_id, 'fence': int(fence), 'state': 'started',
                                         'pid': identity.pid, 'created': identity.created,
                                         'boot_id': identity.boot_id, 'stdout_path': str(stdout),
                                         'started_at': stamp})
                if spec.generation_id:
                    if os.name == 'nt':
                        psutil.Process(process.pid).resume()
                    else:
                        (self.directory / (attempt_id + '.start')).touch(exist_ok=False)
            except Exception as exc:
                raise SupervisorError('Spawned attempt could not complete its start handshake',
                                      code='recovery_required') from exc
            METRICS.increment('supervisor.launches')
            return LaunchReceipt(attempt_id=attempt_id, fence=int(fence), state='started',
                                 identity=identity, stdout_path=str(stdout), started_at=stamp)

    def generation_tree_exit(self, attempt_id, *, fence, stop=False):
        """Generation leases need containment proof, not a dead parent PID.

        Windows restart loses the unnamed job handle: fail closed. Linux requires
        the subreaper's ECHILD proof, including double-fork/setsid descendants.
        Permission/observation errors retain the lease for explicit recovery.
        """
        marker = self.directory / (attempt_id + '.environment.json')
        if not marker.exists():
            return True
        value = json.loads(marker.read_text(encoding='utf-8'))
        if value['fence'] != fence:
            raise SupervisorError('Generation lease fence differs', code='stale_attempt')
        proof_path = self.directory / (attempt_id + '.tree-exit.json')
        if proof_path.exists():
            proof = json.loads(proof_path.read_text(encoding='utf-8'))
            if proof.get('fence') != fence or proof.get('tree_exited') is not True:
                raise SupervisorError('Tree proof differs', code='recovery_required')
            receipt = self.read_receipt(attempt_id)
            if receipt is None or receipt.identity is None or proof.get('identity') != receipt.identity.to_json():
                return False
            self.environment_store.release(attempt_id, fence)
            return True
        receipt = self.read_receipt(attempt_id)
        if receipt is None or receipt.identity is None:
            return False
        try:
            if os.name == 'nt':
                owner = self._generation_jobs.get(attempt_id)
                if owner is None:
                    return False
                if stop:
                    owner.stop()
                if owner.active_processes():
                    return False
                method = 'windows-job'
            else:
                if (stop and identity_alive(receipt.identity)
                        and self._monitor_ready(attempt_id, fence=fence, identity=receipt.identity)):
                    import signal
                    os.kill(receipt.identity.pid, signal.SIGTERM)
                return False  # only the surviving subreaper can certify ECHILD
        except (OSError, psutil.Error):
            return False
        from .fs import atomic_json
        atomic_json(proof_path, {'attempt_id': attempt_id, 'fence': fence,
                                'tree_exited': True, 'method': method,
                                'identity': receipt.identity.to_json()})
        self.environment_store.release(attempt_id, fence)
        if os.name == 'nt':
            self._generation_jobs.pop(attempt_id).close()
        return True

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
            # The surviving Linux subreaper records the real child exit status.
            # This is not inferred from a missing PID or a scientific output file.
            proof_path = self.directory / (attempt_id + '.tree-exit.json')
            if proof_path.exists() and receipt.identity is not None:
                proof = json.loads(proof_path.read_text(encoding='utf-8'))
                if (proof.get('identity') == receipt.identity.to_json()
                        and proof.get('attempt_id') == attempt_id and proof.get('fence') == receipt.fence
                        and proof.get('method') == 'linux-subreaper' and proof.get('tree_exited') is True
                        and type(proof.get('exit_code')) is int):
                    return 'exited', proof['exit_code']
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
            raise StopUnconfirmedError('No durable launch outcome proves this attempt stopped',
                                       code='recovery_required')
        if fence is not None and receipt.fence != int(fence):
            raise SupervisorError('The launch receipt belongs to a stale fence', code='stale_attempt')
        if (self.directory / (attempt_id + '.environment.json')).exists():
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if self.generation_tree_exit(attempt_id, fence=receipt.fence, stop=True):
                    self._mark_stopped(attempt_id)
                    return StopReceipt(attempt_id, True, receipt.identity, True, 'generation-containment')
                time.sleep(.02)
            raise StopUnconfirmedError('Generation process tree is not confirmed stopped', code='recovery_required')
        if receipt.identity is None:
            if not self.no_spawn_proven(attempt_id, fence=receipt.fence):
                raise StopUnconfirmedError('Missing process identity does not prove no spawn',
                                           code='recovery_required')
            return StopReceipt(attempt_id=attempt_id, confirmed=True, identity=None, exited=True,
                               stop_method='never-spawned')
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
