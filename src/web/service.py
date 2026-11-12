"""Local assets and isolated worker processes; no execution in HTTP handlers."""
from dataclasses import dataclass
from datetime import datetime, timezone
import getpass
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import subprocess
import sys
import threading
import time
import traceback
import uuid

import yaml
from operon.run_log import append_event

from .graph import GraphError, compile_graph, relative_manifest
from .models import Graph
from .routes import RouteLibrary, expand_routes
from .storage import FileLock, atomic_json, io_path
from .admission import HostAdmission, MIB, process_alive, process_identity


def safe_json(value):
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {str(k): safe_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe_json(v) for v in value]
    numpy = sys.modules.get("numpy")
    scalar_type = vars(numpy).get("generic") if numpy is not None else None
    if scalar_type is not None and isinstance(value, scalar_type):
        return safe_json(value.item())
    return value


def read_json(path, default=None):
    try:
        return json.loads(io_path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path, value):
    atomic_json(path, safe_json(value))


def _glob_paths(directory, pattern):
    """Enumerate through native I/O, keeping service/public paths logical."""
    directory = Path(directory)
    native = io_path(directory)
    return (directory / path.relative_to(native) for path in native.glob(pattern))


class PoolSubmissionError(GraphError):
    code = 'engine_unavailable'
    status = 503


class SubmissionConflictError(GraphError):
    code = 'idempotency_conflict'
    status = 409


class _AdoptedWorker:
    """Popen-compatible wait surface for a worker adopted after a launcher restart."""

    def __init__(self, identity):
        self.pid = int(identity['pid'])
        self.identity = dict(identity)

    def wait(self, timeout=None):
        import psutil
        deadline = None if timeout is None else time.monotonic() + float(timeout)
        while True:
            if not process_alive(self.identity):
                return 0
            if deadline is not None and time.monotonic() >= deadline:
                raise subprocess.TimeoutExpired(str(self.pid), timeout)
            time.sleep(.1)


@dataclass
class Settings:
    root: Path
    data_dir: Path
    dist_dir: Path
    max_upload: int | None = None
    testing: bool = False
    code_root: Path | None = None
    desktop: bool = False
    profile: dict | None = None
    builtin_routes: bool = False
    instance_url: str | None = None
    input_roots: list[Path] | None = None
    admission_dir: Path | None = None
    manifest_only_registry: bool = False
    # Tests can explicitly choose a real managed pool; old unit fixtures remain
    # in-process so they never create a daemon in the user's account.
    engine_mode: str | None = None
    engine_journal: bool = True
    engine_dir: Path | None = None
    pool_address: str | None = None
    pool_token: str | None = None
    pool_principal: str | None = None
    worker_python: str | None = None


class JobService:
    def __init__(self, settings, catalog, *, pool=None, principal=None):
        self.settings, self.base_catalog = settings, catalog
        self.pool = pool
        self._pool_principal = principal
        self._configured_engine_mode = (os.environ.get('OPERON_ENGINE_MODE') or
                                        settings.engine_mode or ('legacy' if settings.testing else 'pool'))
        self.pool_address = None if pool is not None else (os.environ.get('OPERON_POOL_ADDRESS') or
                                                         settings.pool_address)
        self.pool_token = (os.environ.get('OPERON_POOL_TOKEN') or
                           settings.pool_token)
        self.pool_managed = (pool is None and not self.pool_address and
                             self._configured_engine_mode in ('auto', 'pool'))
        self.pool_remote = pool is None and (bool(self.pool_address) or self.pool_managed)
        self.pool_principal = (os.environ.get('OPERON_POOL_PRINCIPAL') or
                               settings.pool_principal or
                               os.environ.get('OPERON_ENGINE_PRINCIPAL') or
                               getpass.getuser())
        self.pool_client = None
        self.pool_session_id = None
        self.pool_error = None
        self._pool_session_lock = threading.RLock()
        self.remotes = None
        self.root = settings.root.resolve()
        if settings.input_roots is None:
            settings.input_roots = list(dict.fromkeys([self.root, (settings.code_root or self.root).resolve()]))
        self.directory = settings.data_dir.resolve()
        from operon.plugins import PluginManager
        self.plugins = PluginManager(self.directory, manifest_only=settings.manifest_only_registry,
                                     python=settings.worker_python)
        from operon.dependencies import DependencySession
        self.dependencies = DependencySession(self.plugins)
        self.dependencies.sync(self.plugins.state())
        self.catalog = self.plugins.extend_catalog(catalog)
        self._catalog_stamp = None
        self._catalog_lock = threading.Lock()
        self._catalog_version = 0
        if not self.directory.is_relative_to(self.root):
            raise ValueError("Studio data directory must be inside the project")
        self.jobs_dir = self.directory / "jobs"
        self.assets_dir = self.directory / "assets"
        io_path(self.jobs_dir).mkdir(parents=True, exist_ok=True)
        io_path(self.assets_dir).mkdir(exist_ok=True)
        self.lock = FileLock(self.directory / ".jobs.lock")
        self.processes, self.threads, self.jobs = {}, {}, {}
        self._closed = threading.Event()
        self._wake = threading.Event()
        self._dispatch_lock = threading.RLock()
        self._starting = set()
        self.engine_error = None
        self.pool = pool
        self._pool_principal = principal
        import psutil
        self.owner = {"pid": os.getpid(), "created": psutil.Process().create_time(), "service_id": uuid.uuid4().hex}
        admission_dir = settings.admission_dir or (self.root / '.admission' if settings.testing else None)
        self.admission = None if self.pool_remote else HostAdmission(admission_dir)
        with self.lock:
            self._refresh_jobs()
            self.demo = self._demo()
            write_json(self.directory / "operators.json", self.catalog)
        self.routes = RouteLibrary(self.directory / "workflows", self.catalog, self.root,
                                   self.graph_catalog, input_roots=settings.input_roots)
        if settings.builtin_routes:
            self.routes.install_builtins()
        self.shadow_decisions = 0
        self.coordinator = None
        self.artifact_committer = None
        self._coordinator_claimed = False
        if self.pool_remote:
            self.engine = None
            self._engine_journal = None
            self.engine_mode = 'pool'
            self.environment_error = None
            self.environment_guard = self._open_environment_guard()
            self._wrap_environment_mutations()
            from operon.pool_service import PoolClient
            try:
                if self.pool_managed:
                    from operon.managed_pool import ManagedPoolClient
                    self.pool_client = ManagedPoolClient(settings, principal=self.pool_principal)
                else:
                    host, port = self.pool_address.rsplit(':', 1)
                    self.pool_client = PoolClient((host, int(port)), self.pool_token,
                                                  timeout=60)
            except (ValueError, TypeError) as exc:
                self.pool_error = f'invalid pool address: {exc}'
            self.scheduler = None
        elif pool is not None:
            # Pool client: the dedicated pool service owns the coordinator and
            # the only resource ledger.  This workspace owns its job records,
            # frozen parameters and worker processes.
            self.engine = pool.workspace_engine(self.root, self._pool_principal)
            self._engine_journal = self.engine.journal
            self.engine_mode = 'coordinator'
            self.environment_error = None
            self.environment_guard = pool.environment_guard
            self._wrap_environment_mutations()
            from operon.engine.artifacts import ArtifactCommitter
            self.artifact_committer = ArtifactCommitter(self.jobs_dir, self.engine.store)
            self.scheduler = None
            self._adopt_running_jobs()
        else:
            self.engine = self._open_engine(settings)
            self._engine_journal = getattr(self.engine, 'journal', None)
            self.engine_mode = getattr(self.engine, 'mode', self._configured_engine_mode)
            self.environment_error = None
            self.environment_guard = self._open_environment_guard()
            self._wrap_environment_mutations()
            if self.engine is not None and self._configured_engine_mode == 'coordinator':
                self._enable_coordinator()
            if self.coordinator is None:
                active_coordinated = [job for job in self.jobs.values()
                                      if job.get('scheduling') == 'coordinator'
                                      and job.get('status') in ('queued', 'preparing', 'uploading',
                                                                'running', 'waiting_connection')]
                if active_coordinated:
                    raise RuntimeError(
                        'Active coordinator-owned jobs exist; restart in coordinator mode or '
                        'finish them before reverting to legacy scheduling')
                self.scheduler = threading.Thread(target=self._schedule, name='operon-admission', daemon=True)
                self.scheduler.start()
            else:
                self.scheduler = None

    def _open_environment_guard(self):
        try:
            from operon.engine.environment import EnvironmentGuard
            path = os.environ.get('OPERON_ENVIRONMENT_GATE')
            if not path:
                if self.admission is None:
                    path = self.directory / 'environment-gate.json'
                else:
                    # Sibling of the shared admission ledger, not a workspace path.
                    path = self.admission.directory.parent / 'environment-gate.json'
            return EnvironmentGuard(path)
        except Exception as exc:  # noqa: BLE001 - reported and fails closed at launch
            self.environment_error = f'{type(exc).__name__}: {exc}'
            return None

    def _adopt_running_jobs(self):
        """Resume observation of live workers after a pool/launcher restart."""
        for key, job in list(self.jobs.items()):
            worker = job.get('worker') or {}
            if job.get('status') != 'running' or not worker or not process_alive(worker):
                continue
            if key in self.processes or key in self.threads:
                continue
            adopted = _AdoptedWorker(worker)
            try:
                console = open(io_path(self.jobs_dir / key / 'console.log'), 'a', encoding='utf-8')
            except OSError:
                console = None
            self.processes[key] = adopted
            thread = threading.Thread(target=self._watch, args=(key, adopted, console),
                                      daemon=True, name='adopt-' + key)
            self.threads[key] = thread
            thread.start()

    def environment_identity(self, *, directory=None, plugins_lock=None):
        """Resolve the real interpreter/dependency generation, not a workspace.

        Workspaces and installation directories that use the same interpreter
        therefore share one exclusion domain.  The code root is intentionally
        excluded from the identity.
        """
        from operon.engine.environment import environment_identity
        lock = plugins_lock
        if lock is None:
            try:
                lock = read_json((directory or self.jobs_dir) / 'plugins.lock.json', {})
            except (OSError, TypeError):
                lock = {}
        python = None
        try:
            python = self.plugins.python_for(lock or {})
        except Exception as exc:
            from operon.engine.environment import EnvironmentGuardError
            raise EnvironmentGuardError('Cannot resolve the execution interpreter for environment locking') from exc
        return environment_identity(
            python or sys.executable)

    def _wrap_environment_mutations(self):
        """Serialize extension/environment replacement against running attempts."""
        guard = self.environment_guard
        if guard is None:
            return
        original = self.plugins._install_many

        def guarded(*args, **kwargs):
            guard = self.execution_environment_guard()
            with guard.maintenance(owner=self.owner, kind='plugin-install',
                                   environment=self.environment_identity()):
                return original(*args, **kwargs)

        self.plugins._install_many = guarded

    def execution_environment_guard(self):
        if self.pool_remote:
            self._ensure_pool_session()
            path = self.pool_client.status()['environment_gate']['path']
            from operon.engine.environment import EnvironmentGuard
            if not Path(path).is_absolute():
                raise PoolSubmissionError('The pool did not return an absolute shared environment gate')
            self.environment_guard = EnvironmentGuard(path)
        if self.environment_guard is None:
            raise PoolSubmissionError('The execution environment gate is unavailable')
        return self.environment_guard

    def _enable_coordinator(self):
        """Drain/inventory, then hand all local execution to one coordinator.

        There is no silent fallback to the legacy allocator: if a legacy
        reservation or legacy active job exists, coordinator mode refuses to
        start.  Engine-owned attempts from a previous coordinator are left for
        the coordinator recovery path.
        """
        from dataclasses import replace
        from operon.engine.executor import JobServiceExecutor
        with self.lock:
            self._refresh_jobs()
            active = [job for job in self.jobs.values()
                      if job.get('status') in ('queued', 'preparing', 'uploading', 'running',
                                               'waiting_connection')]
        legacy_active = [job for job in active if job.get('scheduling') != 'coordinator']
        if legacy_active:
            raise RuntimeError(
                'Coordinator mode requires a drained legacy queue; active legacy jobs: ' +
                ', '.join(str(job.get('id')) for job in legacy_active[:10]))
        reservations = self.admission.resources().get('reservations') or {}
        if reservations:
            raise RuntimeError(
                'Coordinator mode requires a drained admission ledger; legacy reservations exist: ' +
                ', '.join(sorted(reservations)[:10]))
        if self.processes:
            raise RuntimeError('Coordinator mode requires no legacy worker processes')
        guard = getattr(self, 'environment_guard', None)
        if guard is not None:
            gate = guard.status()
            if gate.get('maintenance'):
                raise RuntimeError(
                    'Coordinator mode cannot start while an environment repair/install holds the gate')
        workspaces = self.engine.store.connection.execute(
            'SELECT workspace_id FROM workspaces WHERE pool_id=?',
            (self.engine.spec.pool_id,)).fetchall()
        if len({row['workspace_id'] for row in workspaces}) > 1:
            raise RuntimeError(
                'The JobService coordinator executor is workspace-scoped; drain the other '
                'workspaces in this pool or run the engine coordinator as a dedicated pool service')
        # Atomic inventory + ownership claim.  Legacy reserve() checks this
        # record under the same ledger lock, closing the scan-then-launch race.
        self.admission.claim_coordinator(self.owner)
        self._coordinator_claimed = True
        try:
            executor = JobServiceExecutor(self)
            from operon.engine.artifacts import ArtifactCommitter
            self.artifact_committer = ArtifactCommitter(self.jobs_dir, self.engine.store)
            facade = self.engine.coordinator(executor, project='default',
                                             artifact_committer=self._commit_job_artifacts)
            coordinator = facade.coordinator
            coordinator.start()
        except Exception:
            self.admission.release_coordinator(self.owner)
            self._coordinator_claimed = False
            raise
        coordinator.spec = replace(coordinator.spec, mode='coordinator')
        self.engine.mode = 'coordinator'
        self.engine.spec = replace(self.engine.spec, mode='coordinator')
        self.engine_mode = 'coordinator'
        self.coordinator = coordinator

    def _open_engine(self, settings):
        """Open the durable journal without making it a second executor.

        A corrupt or newer state database is reported and legacy execution
        continues; it is never silently recreated.
        """
        if os.environ.get('OPERON_ENGINE_DISABLE', '').strip().lower() in ('1', 'true', 'yes'):
            return None
        try:
            from operon.engine.facade import EngineRuntime
            runtime = EngineRuntime.open(
                data_dir=settings.engine_dir,
                workspace_root=self.root, admission=self.admission,
                mode=self._configured_engine_mode, journal=settings.engine_journal)
            if runtime.error:
                self.engine_error = runtime.error
            return runtime
        except Exception as exc:  # noqa: BLE001 - legacy execution must stay diagnosable
            self.engine_error = f'{type(exc).__name__}: {exc}'
            return None

    def graph_catalog(self, graph):
        from .source_paths import remote_profile
        if self.remotes and remote_profile(graph):
            return self.remotes.catalog(graph)
        # Validation and dependency receipts must not observe a half-replaced
        # catalog while a background refresh is running.
        with self._catalog_lock:
            return self.plugins.catalog_for(graph, self.base_catalog)

    @property
    def catalog_version(self):
        return self._catalog_version

    def prepare_graph(self, graph):
        from .source_paths import remote_profile
        from .parameters import freeze_graph
        from .routes import prepare_interface
        if self.remotes and remote_profile(graph):
            return self.remotes.prepare(graph)
        graph = self.plugins.pin(graph)
        catalog = self.graph_catalog(graph)
        return prepare_interface(freeze_graph(graph, catalog, self.root, input_roots=self.settings.input_roots),
                                 catalog, self.root, input_roots=self.settings.input_roots)

    def validate_graph(self, graph, require_files=True):
        from .source_paths import remote_profile
        from .contracts import analyze_graph
        if self.remotes and remote_profile(graph):
            return self.remotes.call(remote_profile(graph), 'validate', {'graph': graph.model_dump(mode='json'),
                                                                       'require_files': require_files})
        catalog = self.graph_catalog(graph)
        manifest, order = compile_graph(graph, catalog, self.root, require_files=require_files,
                                        input_roots=self.settings.input_roots)
        return {'valid': True, 'order': order, 'manifest': manifest,
                'contracts': analyze_graph(graph, catalog, self.root, input_roots=self.settings.input_roots)}

    def refresh_catalog(self):
        with self._catalog_lock:
            stamp = self.plugins.catalog_stamp()
            if stamp is not None and stamp == self._catalog_stamp:
                return False
            # Record the stamp from BEFORE reading. A concurrent atomic replace
            # must invalidate the next read, rather than hiding its generation.
            state = self.plugins.state()
            changed = state["generation"] != self.catalog.get("plugin_generation")
            if changed:
                self.dependencies.sync(state)
                value = self.plugins._catalog(state, self.base_catalog)
                # Replace by identity: a reader either holds the previous
                # complete generation or the next one, never a mixture.
                catalog = {**self.catalog, **value}
                self.catalog = catalog
                self.routes.catalog = catalog
                self._catalog_version += 1
                write_json(self.directory / "operators.json", self.catalog)
            self._catalog_stamp = stamp
            return changed

    def _reconcile_coordinated_job(self, value, record):
        """Project a terminal coordinator run onto its JobService record."""
        if value.get('scheduling') != 'coordinator' or value.get('status') not in ('queued', 'preparing'):
            return False
        engine = getattr(self, 'engine', None)
        store = getattr(engine, 'store', None)
        if store is None:
            return False
        try:
            run = store.run(value['id'])
        except Exception:  # noqa: BLE001 - absence means the coordinator has no opinion yet
            return False
        status = str(run.get('status') or '')
        if status not in ('failed', 'cancelled'):
            return False
        error = run.get('error') or ('The run was cancelled' if status == 'cancelled' else 'The run failed during admission')
        reason = run.get('reason')
        value['status'] = status
        value['error'] = error
        value['finished_at'] = run.get('finished_at') or datetime.now(timezone.utc).isoformat()
        value['logs_complete'] = True
        value['queued_reason'] = None
        value['admission'] = {'status': status, 'reason': reason, 'error': error}
        value['progress'] = self._progress(value)
        write_json(record, value)
        return True

    def _refresh_jobs(self, *, active_only=False):
        if getattr(self, 'pool_remote', False):
            # A pool client is a viewer; never kill/adopt workers or write a
            # second resource authority. The pool service owns those transitions.
            records = _glob_paths(self.jobs_dir, '*/job.json')
            for record in records:
                value = read_json(record)
                if value:
                    self.jobs[value['id']] = value
            return
        import psutil
        records = ((self.jobs_dir / key / 'job.json' for key, value in list(self.jobs.items())
                    if value['status'] in ('queued', 'running') or value.get('logs_complete') is False)
                   if active_only else _glob_paths(self.jobs_dir, '*/job.json'))
        for record in records:
            value = read_json(record)
            if value:
                self._reconcile_coordinated_job(value, record)
                if value["status"] == "queued":
                    if not process_alive(value.get('owner', {})):
                        value['owner'] = self.owner
                        write_json(record, value)
                elif value["status"] == "running" or value.get("logs_complete") is False:
                    owner = value.get("owner", {})
                    try:
                        alive = psutil.Process(owner["pid"]).create_time() == owner["created"]
                    except (KeyError, psutil.NoSuchProcess):
                        alive = False
                    except psutil.AccessDenied:
                        alive = True  # Insufficient permission is not proof of a dead worker.
                    if not alive:
                        # Do not replay a half-finished analysis after a launcher
                        # crash.  Coordinator-owned jobs are the exception: the
                        # coordinator recovery path must adopt a live worker.
                        worker = value.get('worker', {})
                        coordinated_live = (value.get('scheduling') == 'coordinator'
                                            and worker and process_alive(worker)
                                            and (getattr(self, '_configured_engine_mode', None) == 'coordinator'
                                                 or getattr(self, 'pool', None) is not None))
                        if not coordinated_live:
                            worker_stopped = True
                            if worker and process_alive(worker):
                                process = psutil.Process(worker['pid'])
                                try:
                                    process.suspend()
                                    children = process.children(recursive=True)
                                    for child in children:
                                        try: child.suspend(); child.kill()
                                        except psutil.NoSuchProcess: pass
                                    process.kill()
                                    psutil.wait_procs([process, *children], timeout=5)
                                except psutil.NoSuchProcess:
                                    pass
                                except psutil.AccessDenied:
                                    worker_stopped = False
                                worker_stopped = worker_stopped and not process_alive(worker)
                            if not worker_stopped:
                                # The launcher is gone but the worker still owns
                                # the environment and (for legacy jobs) the host
                                # reservation.  Never release either on an
                                # unverified stop; a human/supervisor must
                                # reconcile it.
                                value['status'] = 'recovery_required'
                                value['error'] = ('The launcher died while its worker is still alive; '
                                                  'the worker tree could not be confirmed stopped')
                                value['logs_complete'] = False
                                write_json(record, value)
                                self.jobs[value['id']] = value
                                continue
                            if value["status"] == "running":
                                value["status"] = "interrupted"
                                value["error"] = "本地服务重启，之前的任务未完成。"
                            self._launcher_event(value, "worker_interrupted", status=value["status"], error=value.get("error"))
                            value["finished_at"] = datetime.now(timezone.utc).isoformat()
                            value["logs_complete"] = True
                            self._release(value)
                            write_json(record, value)
                guard = getattr(self, 'environment_guard', None)
                if guard is not None:
                    try:
                        worker = value.get('worker') or {}
                        environment = (value.get('environment') or
                                       self.environment_identity(directory=record.parent))
                        terminal = value.get('status') in ('complete', 'failed', 'cancelled', 'interrupted')
                        if value.get('status') == 'running' and worker and process_alive(worker):
                            guard.ensure_job(value['id'], service=self.owner, worker=worker,
                                             workspace=str(self.root), environment=environment)
                        elif terminal and value.get('tree_exited', True):
                            guard.release_job(value['id'])
                    except Exception as exc:  # noqa: BLE001 - reported, not hidden
                        self.environment_error = f'{type(exc).__name__}: {exc}'
                self.jobs[value["id"]] = value

    def _demo(self):
        path = self.assets_dir / "expression-demo.csv"
        if not io_path(path).exists():
            import csv, random
            rng = random.Random(42)
            with io_path(path).open('w', newline='', encoding='utf-8') as handle:
                writer = csv.writer(handle)
                writer.writerow(f"gene_{i+1:02d}" for i in range(24))
                for row in range(128):
                    writer.writerow('nan' if rng.random() < .015 else f"{rng.gauss(0, 1) + (2 if row < 64 and col < 6 else 0):.5f}" for col in range(24))
        return {
            "schema_version": 2, "name": "表达矩阵 · 质量控制与降维", "base_dir": ".",
            "memory": {"enabled": True, "auto_spill": True},
            "nodes": [
                {"id": "expression", "kind": "source", "title": "表达矩阵", "position": {"x": 60, "y": 160},
                 "source": {"path": str(path.relative_to(self.root)).replace("\\", "/"), "dims": ["sample", "feature"],
                            "labels": {"sample": "auto", "feature": "builtin"}, "args": {}}},
                {"id": "quality", "kind": "operator", "operator": "missing", "title": "缺失值过滤",
                 "position": {"x": 340, "y": 160}, "params": {"dim": "feature", "threshold": .05, "output": "clean"}},
                {"id": "pca", "kind": "operator", "operator": "pca", "title": "主成分分析",
                 "position": {"x": 620, "y": 60}, "params": {"dim": "feature", "n_components": 2, "output": "pcs"}},
                {"id": "summary", "kind": "operator", "operator": "describe", "title": "数据概览",
                 "position": {"x": 620, "y": 260}, "params": {}}
            ],
            "edges": [{"id": "expression-quality", "source": "expression", "target": "quality", "targetHandle": "in-0", "sourceHandle": "out"},
                      {"id": "quality-pca", "source": "quality", "target": "pca", "targetHandle": "in-0", "sourceHandle": "out"},
                      {"id": "quality-summary", "source": "quality", "target": "summary", "targetHandle": "in-0", "sourceHandle": "out"}]
        }

    def _ensure_pool_session(self):
        with self._pool_session_lock:
            if self._closed.is_set():
                raise PoolSubmissionError('The application service is closing; no new pool work was submitted')
            if self.pool_client is None:
                raise PoolSubmissionError(self.pool_error or
                                          'The shared pool is not configured for this service')
            if self.pool_session_id:
                return self.pool_session_id
            try:
                record = self.pool_client.open_session(self.root, principal=self.pool_principal)
                self.pool_session_id = record['session_id']
                self.pool_error = None
                return self.pool_session_id
            except Exception as exc:  # noqa: BLE001 - pool failure is explicit, never local fallback
                self.pool_error = f'{type(exc).__name__}: {exc}'
                error = PoolSubmissionError(f'The shared pool is unavailable: {type(exc).__name__}: {exc}')
                error.code = getattr(exc, 'code', error.code)
                error.details = getattr(exc, 'details', {})
                raise error from exc

    def launch(self, graph: Graph, *, request_id=None, principal=None):
        from .source_paths import remote_profile
        if self.remotes and remote_profile(graph):
            return self.remotes.launch(graph)
        if self.pool_remote:
            self._ensure_pool_session()
            try:
                return self.pool_client.submit(
                    self.root, graph.model_dump(mode='json'),
                    request_id=request_id, principal=principal or self.pool_principal)
            except Exception as exc:  # noqa: BLE001 - no second allocator
                self.pool_error = f'{type(exc).__name__}: {exc}'
                if isinstance(exc, PoolSubmissionError):
                    raise
                if getattr(exc, 'code', None) == 'idempotency_conflict':
                    raise SubmissionConflictError(str(exc)) from exc
                raise PoolSubmissionError(
                    f'The shared pool rejected this submission: {type(exc).__name__}: {exc}') from exc
        if getattr(self, 'pool', None) is None and self.coordinator is None:
            owner = self.admission.coordinator_owner()
            if owner:
                raise GraphError(
                    'This host pool is owned by a coordinator; the legacy launcher is blocked. '
                    'Submit through the pool service or stop the coordinator first')
        if getattr(self, 'pool', None) is not None:
            allowed = self._pool_principal or self.engine.principal
            principal = principal or allowed
            if principal != allowed:
                raise GraphError('This workspace does not accept work for another scheduling principal')
        plugin_snapshot = self.plugins.snapshot(graph)
        graph = self.plugins.pin(graph, snapshot=plugin_snapshot)
        catalog = self.plugins._catalog(plugin_snapshot, self.base_catalog)
        from .parameters import freeze_graph
        from operon.parameter_values import split_task
        graph = freeze_graph(graph, catalog, self.root, input_roots=self.settings.input_roots)
        manifest, order = compile_graph(graph, catalog, self.root, require_files=True, input_roots=self.settings.input_roots)
        try:
            allocation = self.admission.request(manifest)
        except ValueError as exc:
            raise GraphError(str(exc)) from exc
        if request_id is not None:
            if not isinstance(request_id, str) or not request_id or len(request_id) > 512:
                raise GraphError('request_id must be a non-empty string of at most 512 characters')
            key = 'req-' + hashlib.sha256(request_id.encode('utf-8')).hexdigest()[:24]
        else:
            key = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
        directory = self.jobs_dir / key
        memory = manifest['runtime']['memory']
        if allocation['memory_enabled']:
            memory['budget_mb'] = allocation['budget_bytes'] / MIB
            memory['process_limit_mb'] = allocation['process_limit_bytes'] / MIB
        task, parameter_values = split_task(relative_manifest(manifest, directory, catalog))
        request_digest = hashlib.sha256(json.dumps(
            {'graph': graph.model_dump(mode='json'), 'parameters': parameter_values},
            sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()
        existing = None
        with self.lock:
            self._refresh_jobs()
            if self._closed.is_set():
                raise GraphError('Studio is shutting down; no new jobs can be submitted')
            existing = read_json(directory / 'job.json') if directory.exists() else None
            if existing is not None:
                prior = existing.get('request_digest')
                if prior and prior != request_digest:
                    raise SubmissionConflictError('idempotency_conflict: this request_id was already used '
                                     'with different content')
                existing_key = existing.get('id') or key
            else:
                io_path(directory).mkdir(exist_ok=True)
                write_json(directory / "plugins.lock.json", plugin_snapshot)
                # Keep the saved graph unchanged. Only this run receives the fixed
                # host reservation; a worker never independently claims 90% again.
                write_json(directory / "parameters.json", parameter_values)
                io_path(directory / "task.yaml").write_text(yaml.safe_dump(task, sort_keys=False, allow_unicode=True), encoding="utf-8")
                job = {"id": key, "name": graph.name, "status": "queued", "created_at": datetime.now(timezone.utc).isoformat(),
                       "finished_at": None, "error": None, "exit_code": None, "logs_complete": False,
                       "order": order, "graph": graph.model_dump(mode="json"), "owner": self.owner,
                       "request_id": request_id, "request_digest": request_digest,
                       "principal": principal or (self._pool_principal or
                                                  (self.engine.principal if self.engine is not None else None) or
                                                  self.owner.get('service_id')),
                       "allocation": allocation, 'queued_reason': 'Waiting for available host memory and CPU',
                       'reservation_key': str(directory.resolve()),
                       'compute_complete': False, 'tree_exited': False,
                       'artifact_committed': False, 'resources_released': False,
                       'scheduling': 'coordinator' if (self.coordinator is not None or
                                                       getattr(self, 'pool', None) is not None) else 'local',
                       'progress': {'phase': 'queued', 'completed': 0, 'total': len(order), 'percent': 0}}
                job["plugins"] = {"generation": plugin_snapshot["generation"], "packages": plugin_snapshot["packages"]}
                if plugin_snapshot.get('bundled_updates'):
                    job['plugins']['bundled_updates'] = plugin_snapshot['bundled_updates']
                if plugin_snapshot.get('library_pin_updates'):
                    job['plugins']['library_pin_updates'] = plugin_snapshot['library_pin_updates']
                if any(node.kind == "route" for node in graph.nodes):
                    _, job["node_owners"] = expand_routes(graph, self.catalog)
                self.jobs[key] = job
                write_json(directory / "job.json", job)
                self._launcher_event(job, 'job_queued', allocation=allocation)
        if existing is not None:
            return {**self.details(existing_key), 'reused': True, 'request_id': request_id}
        if self.coordinator is not None:
            self._submit_coordinated(job)
        elif getattr(self, 'pool', None) is not None:
            try:
                self.pool.submit_run(self, job, principal=job.get('principal'))
            except Exception as exc:
                with self.lock:
                    current = self.jobs.get(key) or job
                    current['status'] = 'failed'
                    current['finished_at'] = datetime.now(timezone.utc).isoformat()
                    current['logs_complete'] = True
                    current['error'] = f'pool submission failed: {type(exc).__name__}: {exc}'
                    current['progress']['phase'] = 'failed'
                    write_json(self.jobs_dir / key / 'job.json', current)
                raise PoolSubmissionError(current['error']) from exc
        else:
            self._shadow_decision(job)
            # Admission and process launch happen after releasing the job-state
            # lock so concurrent status/cancel requests are not serialized behind
            # a worker spawn.
            self._dispatch()
            self._wake.set()
        return {**self.details(key), 'reused': False, 'request_id': request_id}

    def _submit_coordinated(self, job):
        """Register a prepared JobService run with the pool coordinator."""
        key = job['id']
        try:
            parameters = read_json(self.jobs_dir / key / 'parameters.json', {})
            execution = (job.get('graph', {}).get('runtime', {}).get('execution') or {})
            allocation = job['allocation']
            digest = hashlib.sha256(json.dumps({'graph': job['graph'], 'parameters': parameters},
                                              sort_keys=True, separators=(',', ':')).encode()).hexdigest()
            self.engine.facade.submit(
                key=key, digest=digest, graph=job['graph'], parameters=parameters,
                execution=execution,
                units=[{'unit_id': 'main', 'node_ids': list(job.get('order') or []),
                        'depends_on': [], 'target': {'kind': 'local'},
                        'requirement': {
                            'managed_budget_bytes': int(allocation.get('budget_bytes', 0)),
                            'process_reservation_bytes': int(allocation.get('reserved_bytes', 0)),
                            'cpu_threads': max(1, int(allocation.get('cpu_threads', 1))),
                            'scratch_reserved_bytes': 0},
                        'capability': 'legacy-sequential', 'retry_limit': 1}],
                run_id=key, operation='job')
        except Exception as exc:
            with self.lock:
                current = self.jobs.get(key) or job
                current['status'] = 'failed'
                current['finished_at'] = datetime.now(timezone.utc).isoformat()
                current['logs_complete'] = True
                current['error'] = f'coordinator submission failed: {type(exc).__name__}: {exc}'
                current['progress']['phase'] = 'failed'
                write_json(self.jobs_dir / key / 'job.json', current)
            raise GraphError(current['error']) from exc

    def _commit_job_artifacts(self, payload, result):
        """Publish the final JobService output as an immutable artifact receipt."""
        if self.artifact_committer is None:
            return {}
        run, unit = payload['run'], payload['unit']
        attempt = payload.get('attempt') or payload
        job_id = run['id']
        output = self.jobs_dir / job_id / 'output'
        if not output.is_dir():
            return {}
        files = []
        for base, directories, names in os.walk(io_path(output)):
            directories[:] = [name for name in directories
                              if not (Path(base) / name).is_symlink()]
            for name in names:
                path = Path(base) / name
                if path.is_symlink():
                    continue
                files.append(path.relative_to(io_path(output)).as_posix())
        if not files:
            return {}
        receipt = self.artifact_committer.commit_existing(
            attempt=attempt, unit=unit, fence=int(attempt['fence']),
            source_root=output, files=files, run_id=job_id,
            metadata={'job_id': job_id, 'status': result.state,
                      'plugin_generation': (payload.get('run', {}).get('plan', {})
                                            .get('execution', {}) or {}).get('plugin_generation')})
        with self.lock:
            current = self.jobs.get(job_id) or self.require(job_id)
            current['artifact_committed'] = bool(receipt)
            current['artifact_id'] = receipt.get('artifact_id') if receipt else None
            write_json(self.jobs_dir / job_id / 'job.json', current)
        return receipt
    def _shadow_decision(self, job):
        """Record what the pool policy would decide without taking authority.

        Shadow/coordinator-labelled installations compute diagnostics only.
        No lease is created and no scheduler decision is changed.
        """
        if self.engine_mode not in ('shadow', 'coordinator'):
            return
        engine = getattr(self, 'engine', None)
        if engine is None or getattr(engine, 'store', None) is None or self._engine_journal is None:
            return
        try:
            from operon.engine.contracts import ResourceRequest
            from operon.engine.policy import Demand, Usage, aggregate, select_ready
            allocation = job['allocation']
            demand = Demand(
                key=job['id'], principal=engine.principal, project='default',
                requirement=ResourceRequest(
                    managed_budget_bytes=int(allocation.get('budget_bytes', 0)),
                    process_reservation_bytes=int(allocation.get('reserved_bytes', 0)),
                    cpu_threads=int(allocation.get('cpu_threads', 1))),
                age_seconds=0.0, submitted_at=time.time(), run_id=job['id'])
            snapshot = engine.resources.snapshot()
            usage = aggregate([{'principal': lease.get('principal') or '',
                                'ram': lease['committed'].process_reservation_bytes,
                                'cpu': lease['committed'].cpu_threads}
                               for lease in engine.store.lease_details(engine.spec.pool_id)
                               if lease.get('principal')])
            selection = select_ready([demand], capacity=snapshot.capacity, free=snapshot.free,
                                     usage=usage, cpu_capacity=engine.spec.cpu_threads)
            self.shadow_decisions += 1
            self._engine_journal.record_event(
                'shadow_decision', job_id=job['id'], would_admit=bool(selection.chosen),
                reason=(selection.deferred[0]['reason'] if selection.deferred else
                        selection.infeasible[0]['reason'] if selection.infeasible else 'admit'),
                free_bytes=snapshot.free.ram, requested_bytes=demand.ram,
                reservation=selection.reservation, mode=self.engine_mode)
        except Exception as exc:  # noqa: BLE001 - diagnostics never change execution
            self._engine_journal.record_event('shadow_error', job_id=job['id'],
                                              error=f'{type(exc).__name__}: {exc}')

    def _schedule(self):
        while not self._closed.is_set():
            self._wake.wait(.25)
            self._wake.clear()
            try:
                with self.lock:
                    self._refresh_jobs(active_only=True)
                # Process launch and admission occur outside the job-state
                # lock so status/cancel can proceed while a worker spawns.
                self._dispatch()
                with self.lock:
                    self.scheduler_error = None
            except Exception as exc:
                # Exposed in resources; do not silently abandon a durable queue.
                self.scheduler_error = f'{type(exc).__name__}: {exc}'

    def _dispatch(self):
        if self._closed.is_set():
            return
        with self._dispatch_lock:
            starts = []
            with self.lock:
                pending = [job for job in self.jobs.values()
                           if job['status'] == 'queued' and job.get('owner') == self.owner
                           and job.get('scheduling') != 'coordinator']
                owner = self.admission.coordinator_owner()
                if owner and pending and getattr(self, 'pool', None) is None:
                    for job in pending:
                        job.update(status='failed',
                                   error='The host pool is owned by a coordinator; this legacy '
                                         'launcher cannot start queued work',
                                   finished_at=datetime.now(timezone.utc).isoformat(),
                                   logs_complete=True, queued_reason=None)
                        job['allocation']['state'] = 'released'
                        job['progress']['phase'] = 'failed'
                        self._launcher_event(job, 'admission_failed', error=job['error'])
                        write_json(self.jobs_dir / job['id'] / 'job.json', job)
                    return
                for job in sorted(pending, key=lambda value: value['created_at']):
                    if (job['allocation']['reserved_bytes'] > self.admission.capacity or
                            job['allocation']['cpu_threads'] > self.admission.cpus):
                        job.update(status='failed',
                                   error='The queued reservation exceeds this host session capacity; resubmit with a smaller budget',
                                   finished_at=datetime.now(timezone.utc).isoformat(),
                                   logs_complete=True, queued_reason=None)
                        job['allocation']['state'] = 'released'
                        job['progress']['phase'] = 'failed'
                        self._launcher_event(job, 'admission_failed', error=job['error'])
                        write_json(self.jobs_dir / job['id'] / 'job.json', job)
                        continue
                    if not self.admission.reserve(job['reservation_key'], job['allocation']):
                        # FIFO within a launcher avoids starvation of a larger job.
                        break
                    job['allocation']['state'] = 'reserved'
                    job['progress']['phase'] = 'preparing'
                    starts.append(job)
            for job in starts:
                # Worker spawn/announcement happens after the state lock is
                # released; the reservation is already committed.
                self._start(job)

    def _start(self, job, *, allocation=None, coordinated=False):
        key = job['id']; directory = self.jobs_dir / key
        console = None
        process = None
        environment_lease = False
        allocation = allocation or job['allocation']
        job['allocation'] = allocation
        try:
            with self.lock:
                if job['status'] == 'cancelled':
                    self._release(job)
                    return
                job['status'] = 'running'
                job['started_at'] = datetime.now(timezone.utc).isoformat()
                job['queued_reason'] = None
                job['progress']['phase'] = 'preparing'
                self._starting.add(key)
                write_json(directory / 'job.json', job)
            # Preserve failures during interpreter/gate validation too, before
            # a scientific process exists or a maintenance lease is acquired.
            console = open(io_path(directory / 'console.log'), 'a', encoding='utf-8')
            guard = getattr(self, 'environment_guard', None)
            if guard is None:
                raise RuntimeError(
                    self.environment_error or
                    'The environment maintenance gate is unavailable; refusing to start work without exclusion')
            environment = self.environment_identity(directory=directory)
            job['environment'] = environment
            # Dependency mutation is blocked for the lifetime of the worker.
            guard.acquire_job(key, service=self.owner, workspace=str(self.root),
                              environment=environment)
            environment_lease = True
            temporary = directory / 'tmp'; io_path(temporary).mkdir(exist_ok=True)
            env = dict(os.environ, PYTHONUNBUFFERED='1', PYTHONIOENCODING='utf-8', PYTHONFAULTHANDLER='1',
                       TEMP=str(io_path(temporary)), TMP=str(io_path(temporary)), MPLCONFIGDIR=str(io_path(self.directory / 'matplotlib')))
            threads = str(allocation['cpu_threads'])
            for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
                         'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'BLIS_NUM_THREADS', 'OPERON_CPU_LIMIT'):
                env[name] = threads
            env['OPERON_AVAILABLE_AT_START_BYTES'] = str(allocation['available_at_start_bytes'])
            code_root = self.settings.code_root or self.root
            python = self.plugins.python_for(read_json(directory / 'plugins.lock.json'))
            if io_path(code_root / 'operon/worker.py').is_file():
                # Wheels have no scripts/ tree. Preserve code selection when
                # dependency resolution chooses a different Python runtime.
                env['PYTHONPATH'] = os.pathsep.join(part for part in (str(code_root), env.get('PYTHONPATH')) if part)
                command = [python, '-P', '-m', 'operon.worker', str(directory)]
            else:
                # Older server distributions and explicit custom worker roots.
                command = [python, str(code_root / 'scripts/run.py'), str(directory)]
            console.write(f'[Operon launcher] Job {key}\nPython: {python}\nTask: {directory}\n')
            console.flush()
            self._launcher_event(job, 'worker_launching', python=python, allocation=allocation, message='Starting analysis worker')
            process = subprocess.Popen(command,
                                       cwd=self.root, env=env, stdin=subprocess.DEVNULL,
                                       stdout=console, stderr=subprocess.STDOUT,
                                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            with self.lock:
                self.processes[key] = process
                self._starting.discard(key)
                try:
                    job['worker'] = process_identity(process.pid)
                except Exception:
                    pass  # Already-exited workers are finalized by _watch.
                cancelled = job['status'] == 'cancelled' or job.get('cancel_requested')
                worker_identity = job.get('worker')
            if worker_identity and guard is not None:
                # If this fails the worker must not keep using dependencies
                # outside the exclusion protocol.
                guard.bind_worker(key, worker_identity)
            if not coordinated:
                self.admission.started(job['reservation_key'], process.pid)
            self._launcher_event(job, 'worker_spawned', pid=process.pid)
            with self.lock:
                write_json(directory / 'job.json', job)
            if cancelled:
                # Cancellation arrived between admission and spawn. Stop the
                # owned tree; the watcher finalizes release.
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    from operon.processes import stop_tree
                    stop_tree(process)
            watcher = threading.Thread(target=self._watch, args=(key, process, console), daemon=True)
            with self.lock:
                self.threads[key] = watcher
            watcher.start()
        except Exception as exc:
            with self.lock:
                self._starting.discard(key)
                self.threads.pop(key, None)
            if environment_lease:
                try:
                    guard.release_job(key)
                except Exception as release_error:  # noqa: BLE001 - retain the launch failure
                    self.environment_error = f'{type(release_error).__name__}: {release_error}'
            if process is not None:
                from operon.processes import stop_tree
                try:
                    stop_tree(process)
                except Exception:  # noqa: BLE001 - retain the original failure
                    pass
            with self.lock:
                job['status'], job['error'] = 'failed', f'{type(exc).__name__}: {exc}'
                if console is not None:
                    try:
                        console.write(traceback.format_exc()); console.close()
                    except OSError:
                        pass
                self._launcher_event(job, 'worker_start_failed', error=job['error'])
                job['finished_at'] = datetime.now(timezone.utc).isoformat()
                job['logs_complete'] = True
                job['progress']['phase'] = 'failed'
                self._release(job)
                write_json(directory / 'job.json', job)

    def _start_coordinated(self, job_id, attempt_id, committed):
        """Start a JobService worker under a coordinator lease.

        Called only by :class:`JobServiceExecutor` from the coordinator launch
        outbox.  No legacy admission reservation is taken; the lease is the
        only resource authority.
        """
        with self.lock:
            job = self.require(job_id)
            if job.get('status') in ('complete', 'failed', 'cancelled'):
                return
            if job.get('status') == 'running' or job_id in self.processes or job_id in self._starting:
                return
            allocation = dict(job.get('allocation') or {})
            allocation.update({
                'budget_bytes': int(committed.managed_budget_bytes),
                'reserved_bytes': int(committed.process_reservation_bytes),
                'process_limit_bytes': int(committed.process_reservation_bytes),
                'cpu_threads': max(1, int(committed.cpu_threads)),
                'state': 'coordinated',
            })
            job['scheduling'] = 'coordinator'
            job['coordinator_attempt'] = attempt_id
            write_json(self.jobs_dir / job_id / 'job.json', job)
        self._start(job, allocation=allocation, coordinated=True)

    def _release(self, job):
        allocation = job.get('allocation', {})
        if allocation.get('state') == 'reserved':
            self.admission.release(job['reservation_key'])
            allocation['state'] = 'released'
            allocation['released_at'] = datetime.now(timezone.utc).isoformat()
            job['resources_released'] = True

    def resources(self):
        if self.pool_remote:
            try:
                self._ensure_pool_session()
                status = self.pool_client.status()
                coordinator = status.get('coordinator') or {}
                pool = coordinator.get('pool') or {}
                return {
                    'capacity_bytes': pool.get('capacity_bytes', 0),
                    'reserved_bytes': ((pool.get('used') or {}).get('ram') or 0),
                    'free_bytes': ((pool.get('free') or {}).get('ram') or 0),
                    'cpu_capacity': ((pool.get('pool') or {}).get('cpu_threads') or 0),
                    'cpu_reserved': ((pool.get('used') or {}).get('cpu') or 0),
                    'queued_jobs': sum(job['status'] == 'queued' for job in self.jobs.values()),
                    'scheduler_error': None,
                    'pool': status,
                    'engine': {'available': True, 'mode': 'pool', 'pool': status},
                    'environment_gate': self._environment_status(),
                }
            except Exception as exc:  # noqa: BLE001 - report the unavailable authority
                self.pool_error = f'{type(exc).__name__}: {exc}'
                return {'capacity_bytes': 0, 'reserved_bytes': 0, 'free_bytes': 0,
                        'cpu_capacity': 0, 'cpu_reserved': 0,
                        'queued_jobs': sum(job['status'] == 'queued' for job in self.jobs.values()),
                        'scheduler_error': None,
                        'engine': {'available': False, 'mode': 'pool', 'error': self.pool_error},
                        'environment_gate': self._environment_status()}
        with self.lock:
            result = self.admission.resources()
            result['queued_jobs'] = sum(job['status'] == 'queued' for job in self.jobs.values())
            result['scheduler_error'] = getattr(self, 'scheduler_error', None)
            result['engine'] = self._engine_status()
            result['environment_gate'] = self._environment_status()
            return result

    def _environment_status(self):
        guard = getattr(self, 'environment_guard', None)
        if guard is None:
            return {'available': False, 'error': self.environment_error}
        try:
            status = guard.status()
            status['error'] = self.environment_error
            return status
        except Exception as exc:  # noqa: BLE001 - diagnostics never break scheduling
            return {'available': False, 'error': f'{type(exc).__name__}: {exc}'}

    def _engine_status(self):
        if self.pool_remote:
            try:
                self._ensure_pool_session()
                status = self.pool_client.status()
                return {'available': True, 'mode': 'pool', 'pool': status,
                        'error': self.pool_error}
            except Exception as exc:  # noqa: BLE001 - diagnostics never break scheduling
                return {'available': False, 'mode': 'pool',
                        'error': f'{type(exc).__name__}: {exc}'}
        engine = getattr(self, 'engine', None)
        if engine is None:
            return {'available': False, 'error': self.engine_error, 'mode': self.settings.engine_mode}
        try:
            status = engine.status()
        except Exception as exc:  # noqa: BLE001 - diagnostics must never break scheduling
            return {'available': False, 'error': f'{type(exc).__name__}: {exc}',
                    'mode': self.settings.engine_mode}
        status['error'] = self.engine_error
        status['shadow_decisions'] = getattr(self, 'shadow_decisions', 0)
        return status

    def _watch(self, key, process, console):
        # The runtime first attempts emergency spilling. If a plugin/native
        # process remains above its reservation, contain that job after a grace
        # period rather than allowing it to consume another admitted job's RAM.
        import psutil
        over_since = None
        pressure_error = None
        tracked_children = {}
        while True:
            try:
                code = process.wait(timeout=.25)
                break
            except subprocess.TimeoutExpired:
                children = []
                try:
                    parent = psutil.Process(process.pid)
                    rss = parent.memory_info().rss
                    children = parent.children(recursive=True)
                    for child in children:
                        try:
                            rss += child.memory_info().rss
                            tracked_children[child.pid] = child.create_time()
                        except psutil.Error:
                            pass
                except psutil.Error:
                    continue
                limit = self.jobs[key]['allocation']['process_limit_bytes']
                if rss > limit:
                    over_since = over_since or time.monotonic()
                    if time.monotonic() - over_since >= 2:
                        pressure_error = f'Worker tree RSS {rss} exceeds its host reservation {limit}; emergency spill could not recover enough memory'
                        from operon.processes import stop_tree
                        stop_tree(process)
                else:
                    over_since = None
        # The root has exited.  A native grandchild can outlive it, so verify
        # every descendant observed while the root was alive before publishing
        # completion or releasing the reservation/lease.
        remaining = []
        for pid, created in tracked_children.items():
            try:
                child = psutil.Process(pid)
                if child.create_time() == created and child.is_running() and \
                        child.status() != psutil.STATUS_ZOMBIE:
                    remaining.append(child)
            except psutil.Error:
                continue
        tree_error = None
        if remaining:
            for child in remaining:
                try: child.kill()
                except psutil.Error: pass
            try:
                gone, alive = psutil.wait_procs(remaining, timeout=2)
            except psutil.Error:
                alive = remaining
            remaining = [child for child in alive if child.is_running()]
            if remaining:
                tree_error = 'Worker descendants are still alive after the root exited: ' + \
                             ', '.join(str(child.pid) for child in remaining[:10])
        tree_exited = not remaining
        with self.lock:
            job = self.jobs[key]
            summary = read_json(self.jobs_dir / key / "output/run_summary.json", {})
            compute_complete = bool(code == 0 and summary.get("status") == "complete" and
                                    not pressure_error and not tree_error)
            job['compute_complete'] = compute_complete
            job['tree_exited'] = tree_exited
            if job["status"] != "cancelled":
                if not tree_exited:
                    job["status"] = "recovery_required"
                    job["error"] = tree_error
                else:
                    job["status"] = "complete" if compute_complete else "failed"
                    job["error"] = pressure_error or tree_error or summary.get("error") or (None if job["status"] == "complete" else
                        f"Worker exited with code {code} (0x{code & 0xffffffff:08X}) "
                        + ("without producing a run summary." if not summary else "without completing the run."))
            elif not tree_exited:
                job['status'] = 'recovery_required'
                job['error'] = tree_error
            job["exit_code"] = code
            try:
                if console is not None:
                    console.write(f"\n[Operon launcher] Worker exit code {code} (0x{code & 0xffffffff:08X}); status={job['status']} tree_exited={tree_exited}\n")
                    if job.get("error"):
                        console.write(job["error"] + "\n")
            except OSError as exc:
                job["log_error"] = str(exc)
            finally:
                try:
                    if console is not None:
                        console.close()
                except OSError as exc:
                    job["log_error"] = str(exc)
            self._launcher_event(job, "worker_finished", exit_code=code, status=job["status"],
                                 error=job.get("error"), tree_exited=tree_exited)
            job["finished_at"] = datetime.now(timezone.utc).isoformat()
            # Publish terminal completion only after both writers have flushed.
            job["logs_complete"] = True
            if job["status"] == "cancelled":
                job["cancel_state"] = "stopped"
                job["cancel_requested"] = True
            if tree_exited:
                self._release(job)
            guard = getattr(self, 'environment_guard', None)
            if guard is not None and tree_exited:
                try:
                    guard.release_job(key)
                except Exception as exc:  # noqa: BLE001 - stale lease pruning will retry
                    self.environment_error = f'{type(exc).__name__}: {exc}'
            job['progress'] = self._progress(job)
            write_json(self.jobs_dir / key / "job.json", job)
            self.processes.pop(key, None)
            self.threads.pop(key, None)
            self._wake.set()

    def _launcher_event(self, job, event, **details):
        # Separate journal: the parent never competes with the worker's JSONL writer.
        try:
            append_event(self.jobs_dir / job["id"] / "launcher.events.jsonl", event, **details)
        except OSError as exc:
            job["log_error"] = str(exc)
        journal = getattr(self, '_engine_journal', None)
        if journal is not None:
            # The durable engine journal is an index, not a second execution
            # authority; a failure here must not lose the launcher event file.
            try:
                journal.record_event(event, job_id=job.get('id'), **details)
            except Exception as exc:  # noqa: BLE001
                self.engine_error = f'event journal failed: {type(exc).__name__}: {exc}'

    def require(self, key):
        # Jobs created by the other launcher become visible without restarting.
        with self.lock:
            value = read_json(self.jobs_dir / key / "job.json") if key.replace("-", "").isalnum() else None
            if value:
                self.jobs[key] = value
            if key not in self.jobs:
                raise KeyError("找不到这次运行。")
            return self.jobs[key]

    def events_path(self, key):
        self.require(key)
        paths = list(_glob_paths(self.jobs_dir / key / "output/runs", "*/events.jsonl"))
        return paths[0] if paths else None

    def event_paths(self, key):
        self.require(key)
        directory = self.jobs_dir / key
        return [p for p in [directory / "launcher.events.jsonl",
                *sorted(_glob_paths(directory / "output/runs", "*/events.jsonl"))] if io_path(p).is_file()]

    def console_snapshot(self, key, job, previous=None, limit=64 * 1024):
        """A bounded display tail; the downloadable file remains complete."""
        path = self.jobs_dir / key / "console.log"
        try:
            stat = io_path(path).stat()
            signature = (stat.st_size, stat.st_mtime_ns, job.get("status"), job.get("error"))
            if signature == previous:
                return signature, None
            if stat.st_size:
                with io_path(path).open("rb") as file:
                    file.seek(max(0, stat.st_size - limit))
                    content = file.read(limit).decode("utf-8", errors="replace")
                return signature, {"console": content, "console_truncated": stat.st_size > limit}
        except FileNotFoundError:
            signature = (None, job.get("status"), job.get("error"))
            if signature == previous:
                return signature, None
        # Old empty files are evidence too: display a fallback without rewriting them.
        content = f"No worker output was captured for this run.\nStatus: {job['status']}\n"
        if job.get("error"):
            content += f"Recorded error: {job['error']}\n"
        return signature, {"console": content, "console_truncated": False}

    def details(self, key):
        if self.remotes and self.remotes.owns(key):
            return self.remotes.job(key)
        if self.pool_remote:
            self._ensure_pool_session()
            return self.pool_client.details(self.root, key, principal=self.pool_principal)
        with self.lock:
            job = dict(self.require(key))
            queued = sorted((value for value in self.jobs.values() if value['status'] == 'queued'),
                            key=lambda value: value['created_at'])
            job['queue_position'] = next((index + 1 for index, value in enumerate(queued) if value['id'] == key), None)
            job['lifecycle'] = self._lifecycle(job)
        # File reads and progress parsing happen on a snapshot, outside the
        # state lock: a large report must not block another client's status.
        directory = self.jobs_dir / key
        summary = read_json(directory / "output/run_summary.json")
        job["summary"] = summary
        job['progress'] = self._progress(job)
        report = read_json(self._record_path(key, summary["memory_report"], summary)) if summary and summary.get("memory_report") else None
        if report:
            # Reports retain original audit locations on disk. API paths follow a moved workspace.
            for artifact in report.get("artifacts", []):
                if artifact.get("disk_uri"):
                    artifact["disk_uri"] = str(self._record_path(key, artifact["disk_uri"], summary))
            job["spill_counts"] = self.spill_counts(key)
        job["report"] = report
        return safe_json(job)

    def _lifecycle(self, job):
        """Distinguish computation, publication, process exit and release."""
        lease = None
        lease_state = None
        attempt_id = job.get('coordinator_attempt')
        engine = getattr(self, 'engine', None)
        if attempt_id and engine is not None and getattr(engine, 'store', None) is not None:
            try:
                lease = engine.store.lease(attempt_id)
                lease_state = lease.get('state')
            except Exception:  # noqa: BLE001 - diagnostics only
                lease = None
        resources_released = bool(job.get('resources_released'))
        if lease_state is not None:
            resources_released = lease_state == 'released'
        return {
            'compute_complete': bool(job.get('compute_complete')),
            'artifact_committed': bool(job.get('artifact_committed')),
            'tree_exited': bool(job.get('tree_exited')),
            'resources_released': resources_released,
            'lease_state': lease_state,
            'resource_authority': 'coordinator' if attempt_id else 'legacy-admission',
        }

    def _progress(self, job):
        total = len(job.get('order', []))
        progress = dict(job.get('progress') or {'completed': 0, 'total': total, 'percent': 0})
        progress['phase'] = job['status']
        progress['total'] = total
        # Read a bounded journal tail, using real step indices instead of a
        # timer-derived percentage. Long-running tools remain at their step.
        paths = sorted(_glob_paths(self.jobs_dir / job['id'] / 'output/runs', '*/events.jsonl'))
        current = None
        if paths:
            with io_path(paths[-1]).open('rb') as stream:
                size = stream.seek(0, os.SEEK_END)
                stream.seek(max(0, size - 65536))
                lines = stream.read().decode('utf-8', errors='replace').splitlines()
            for line in lines:
                try: event = json.loads(line)
                except json.JSONDecodeError: continue
                if event.get('event') == 'step_started' and isinstance(event.get('index'), int):
                    current = event['index']
                    progress['completed'] = max(progress['completed'], current - 1)
                    progress['current'] = event.get('name')
                elif event.get('event') == 'step_finished':
                    completed = event.get('index', current)
                    if isinstance(completed, int):
                        progress['completed'] = max(progress['completed'], completed)
        if job['status'] == 'complete':
            progress['completed'] = total
            progress.pop('current', None)
        progress['completed'] = min(total, progress['completed'])
        progress['percent'] = round(100 * progress['completed'] / total, 1) if total else 0
        return progress

    def _record_path(self, key, value, summary):
        """Resolve current or historical paths without depending on the original machine."""
        directory = self.jobs_dir / key
        # Read Windows-authored records on POSIX as well as POSIX records on Windows.
        path_type = PureWindowsPath if PureWindowsPath(value).drive or "\\" in value else PurePosixPath
        stored = path_type(value)
        if not stored.is_absolute():
            candidate = directory.joinpath(*stored.parts).resolve()
        else:
            old_task = path_type(summary.get("task_dir", str(directory)))
            old_root = old_task
            for _ in directory.relative_to(self.root).parts:
                old_root = old_root.parent
            try:
                relative = stored.relative_to(old_root)
            except ValueError as exc:
                raise KeyError("记录中的文件不在原工作目录内，请迁移完整工作目录。") from exc
            candidate = self.root.joinpath(*relative.parts).resolve()
        if not candidate.is_relative_to(self.root):
            raise KeyError("记录中的路径超出当前工作目录。")
        return candidate

    def spill_counts(self, key):
        counts = {"planned": 0, "emergency": 0, "final": 0, "correction": 0}
        path = self.events_path(key)
        if path:
            with open(io_path(path), encoding="utf-8") as lines:
                for line in lines:
                    try:
                        item = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if item.get("event") == "spill":
                        reason = item.get("reason")
                        category = ("final" if reason == "final_output" else "emergency" if reason in ("rss_pressure", "managed_pressure")
                                    else "correction" if reason in ("actual_output_size", "actual_input_size", "step_boundary") else "planned")
                        counts[category] += 1
        return counts

    def events(self, after=0, *, run_id=None, limit=200):
        if self.pool_remote:
            self._ensure_pool_session()
            page = self.pool_client.request('events.page', {
                'workspace': str(self.root), 'after': int(after), 'limit': int(limit),
                'session_id': self.pool_session_id, 'principal': self.pool_principal})
            return {**page, 'available': True}
        journal = getattr(self, '_engine_journal', None)
        if journal is None:
            return {'events': [], 'cursor': after, 'has_more': False, 'available': False}
        page = journal.page(after, limit=limit, run_id=run_id)
        return {**page.to_json(), 'available': True}

    def history(self):
        with self.lock:
            self._refresh_jobs()
            snapshots = [dict(value) for value in
                         sorted(self.jobs.values(), key=lambda j: j["created_at"], reverse=True)[:60]]
        local = [{**{k: value.get(k) for k in ("id", "name", "status", "created_at", "finished_at", "error")},
                  'progress': self._progress(value), 'allocation': value.get('allocation'),
                  'execution_parent_id': value.get('graph', {}).get('runtime', {}).get('execution_parent_id'),
                  'queued_reason': value.get('queued_reason')}
                 for value in snapshots]
        return sorted(local + (self.remotes.history() if self.remotes else []),
                      key=lambda item: item['created_at'], reverse=True)[:60]

    def cancel(self, key):
        if self.remotes and self.remotes.owns(key):
            return self.remotes.cancel(key)
        if self.pool_remote:
            self._ensure_pool_session()
            return self.pool_client.cancel(self.root, key,
                                           principal=self.pool_principal)
        job = self.require(key)
        if self.pool is not None and job.get('scheduling') == 'coordinator':
            self.pool.cancel(self, key, principal=job.get('principal') or self._pool_principal)
            with self.lock:
                current = self.jobs.get(key)
                if current is not None and current.get('status') in ('queued', 'running', 'preparing'):
                    current['cancel_requested'] = True
                    current['cancel_state'] = 'requesting'
                    write_json(self.jobs_dir / key / 'job.json', current)
            return self.details(key)
        if self.coordinator is not None and job.get('scheduling') == 'coordinator':
            # The coordinator owns cancellation and lease release.  Persist a
            # visible request flag; the actual stop follows the attempt tree.
            self.coordinator.cancel(key, reason='public cancel request')
            with self.lock:
                current = self.jobs.get(key)
                if current is not None and current.get('status') in ('queued', 'running', 'preparing'):
                    current['cancel_requested'] = True
                    current['cancel_state'] = 'requesting'
                    write_json(self.jobs_dir / key / 'job.json', current)
            return self.details(key)
        return self._cancel_local(key)

    def _cancel_local(self, key, *, coordinated=False, timeout=10):
        process = None
        starting = False
        with self.lock:
            job = self.require(key)
            if job['status'] == 'queued':
                job['status'] = 'cancelled'
                job['finished_at'] = datetime.now(timezone.utc).isoformat()
                job['logs_complete'] = True
                job['queued_reason'] = None
                job['cancel_state'] = 'stopped'
                job['allocation']['state'] = 'released'
                job['progress']['phase'] = 'cancelled'
                self._launcher_event(job, 'job_cancelled', message='Cancelled before worker launch')
                write_json(self.jobs_dir / key / 'job.json', job)
                self._wake.set()
                return self.details(key)
            if job["status"] in ("running", "preparing") or job.get('cancel_state') == 'stopping':
                if job.get('logs_complete'):
                    return self.details(key)
                if key not in self.processes:
                    if key in self._starting:
                        # The worker is between admission and spawn. It will
                        # observe the durable flag and stop its own tree.
                        job['status'] = 'cancelled'
                        job['cancel_requested'] = True
                        job['cancel_state'] = 'stopping'
                        job['progress']['phase'] = 'cancelled'
                        (self.jobs_dir / key / 'cancel.requested').touch()
                        write_json(self.jobs_dir / key / 'job.json', job)
                        starting = True
                    else:
                        raise GraphError("任务由另一个 Operon 窗口运行，请在启动它的窗口停止。")
                else:
                    job["status"] = "cancelled"
                    job['cancel_requested'] = True
                    job['cancel_state'] = 'stopping'
                    job['progress']['phase'] = 'cancelled'
                    # Isolated calls poll this request and can flush their failure
                    # log and clean exchange files before the fallback tree kill.
                    (self.jobs_dir / key / 'cancel.requested').touch()
                    process = self.processes[key]
                    write_json(self.jobs_dir / key / "job.json", job)
        # Process-tree termination is deliberately outside the state lock: a
        # slow native child must not block another client's status query.
        if process is not None:
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                from operon.processes import stop_tree
                stop_tree(process)
            watcher = self.threads.get(key)
            if watcher and watcher is not threading.current_thread():
                watcher.join(timeout=timeout)
        elif starting:
            watcher = self.threads.get(key)
            if watcher and watcher is not threading.current_thread():
                watcher.join(timeout=timeout)
        return self.details(key)

    def shutdown(self, *, cancel_jobs=True):
        if self.pool_remote:
            # Closing an application/workspace session is not pool shutdown and
            # must not cancel work owned by the pool.
            self._closed.set()
            self._wake.set()
            self.dependencies.cancel.set()
            if self.remotes:
                self.remotes.close()
            if self.pool_client is not None and self.pool_session_id:
                try:
                    self.pool_client.close_session(workspace=self.root,
                                                   principal=self.pool_principal)
                except Exception as exc:  # noqa: BLE001 - session cleanup is best effort
                    self.pool_error = f'{type(exc).__name__}: {exc}'
                self.pool_session_id = None
            return
        if self.pool is not None and not cancel_jobs:
            # Closing a workspace client/session must not stop the shared pool
            # or cancel its own running work.  The pool service remains the
            # owner of the worker and environment lease.
            self._closed.set()
            self._wake.set()
            return
        self._closed.set()
        self._wake.set()
        if self.remotes:
            self.remotes.close()
        self.dependencies.cancel.set()
        if self.coordinator is not None:
            try:
                self.coordinator.stop(cancel_attempts=True)
            except Exception as exc:  # noqa: BLE001 - continue draining local workers
                self.engine_error = f'coordinator shutdown: {type(exc).__name__}: {exc}'
            self.coordinator = None
        # Cancel processes and queued jobs without holding the state lock while
        # a worker tree is stopped.
        for key in list(self.processes):
            try:
                self._cancel_local(key)
            except (GraphError, KeyError):
                pass
        with self.lock:
            queued = [job['id'] for job in self.jobs.values()
                      if job['status'] == 'queued' and job.get('owner') == self.owner]
        for key in queued:
            try:
                self._cancel_local(key)
            except (GraphError, KeyError):
                pass
        for watcher in list(self.threads.values()):
            watcher.join(timeout=10)
        if self.scheduler is not None and self.scheduler is not threading.current_thread():
            self.scheduler.join(timeout=5)
        guard = getattr(self, 'environment_guard', None)
        if guard is not None:
            try:
                guard.release_all(self.owner)
            except Exception as exc:  # noqa: BLE001 - shutdown diagnostics remain visible
                self.environment_error = f'{type(exc).__name__}: {exc}'
        self.admission.close()
        engine = getattr(self, 'engine', None)
        if engine is not None and self.pool is None:
            try:
                engine.close()
            except Exception as exc:  # noqa: BLE001 - shutdown diagnostics remain visible
                self.engine_error = f'{type(exc).__name__}: {exc}'
        if getattr(self, '_coordinator_claimed', False):
            try:
                self.admission.release_coordinator(self.owner)
            except Exception as exc:  # noqa: BLE001 - best effort; process identity reconciles
                self.engine_error = f'coordinator release: {type(exc).__name__}: {exc}'
            self._coordinator_claimed = False

    def artifact(self, key, artifact_id):
        report = self.details(key).get("report")
        match = next((a for a in (report or {}).get("artifacts", []) if a["artifact_id"] == artifact_id), None)
        if not match or not match["disk_uri"]:
            raise KeyError("产物尚未保存，或这次运行没有保留它。")
        path = (Path(match["disk_uri"]) / ("files.json" if match.get("kind") == "file" else "data.npy")).resolve()
        if not path.is_relative_to(self.root):
            raise KeyError("产物文件不可用。")
        # Validate containment before using Windows' extended I/O path. A cache
        # directory can be renamed successfully past MAX_PATH while ordinary
        # stat/open subsequently report that the existing payload is absent.
        from operon.bytecode import filesystem_path
        path = Path(filesystem_path(path))
        if not path.is_file():
            raise KeyError("产物文件不可用。")
        return path, match

    def preview(self, key, artifact_id, offset=0, limit=20):
        path, descriptor = self.artifact(key, artifact_id)
        if descriptor.get("kind") == "file":
            payload = self._file_payload(key, path)
            table = self._csv_table(payload, offset=offset, limit=limit)
            return {"descriptor": descriptor, "rows": table["rows"], "points": [], "format": payload["format"],
                    "columns": table["columns"], "row_labels": table["row_labels"],
                    "total": table["total"], "offset": table["offset"], "limit": table["limit"],
                    "files": [{"role": role, "name": Path(value).name,
                                 "downloadable": Path(value).resolve().is_relative_to((self.jobs_dir / key / "output").resolve()),
                                 "bytes": payload["fingerprints"][role]["size"]}
                              for role, value in payload["files"].items()], "info": payload["info"]}

        import numpy as np
        data = np.load(path, mmap_mode="r", allow_pickle=False)
        if data.ndim != 2 or data.dtype.kind not in "biuf":
            return {"descriptor": descriptor, "rows": [], "points": []}
        offset = max(0, int(offset))
        limit = max(1, min(int(limit), 1000))
        total = int(data.shape[0])
        window = data[offset:offset + limit, :min(data.shape[1], 12)].tolist()
        labels = self._artifact_labels(path)
        dims = labels.get("dims", []) if labels else []
        mapping = labels.get("labels", {}) if labels else {}
        columns = mapping.get(dims[1]) if len(dims) > 1 else None
        row_labels = mapping.get(dims[0]) if dims else None
        columns = columns or [f"c{index}" for index in range(data.shape[1])]
        row_labels = row_labels[offset:offset + len(window)] if row_labels else [str(offset + index) for index in range(len(window))]
        points = data[:200, :2].tolist() if data.shape[1] >= 2 else []
        del data
        return safe_json({"descriptor": descriptor, "rows": window, "points": points, "columns": columns,
                          "row_labels": row_labels, "total": total, "offset": offset, "limit": limit})

    def _csv_table(self, payload, offset=0, limit=20):
        """Bounded CSV preview for exported file artifacts."""
        import csv
        offset = max(0, int(offset))
        limit = max(1, min(int(limit), 1000))
        candidates = [value for value in (payload.get('files') or {}).values()
                      if str(value).lower().endswith(('.csv', '.tsv', '.txt'))]
        if not candidates:
            return {"columns": [], "rows": [], "row_labels": [], "total": 0, "offset": offset, "limit": limit}
        target = Path(sorted(candidates)[0])
        if not target.is_file():
            return {"columns": [], "rows": [], "row_labels": [], "total": 0, "offset": offset, "limit": limit}
        delimiter = '\t' if target.suffix.lower() in ('.tsv', '.txt') else ','
        try:
            with target.open('r', encoding='utf-8', errors='replace', newline='') as handle:
                reader = csv.reader(handle, delimiter=delimiter)
                header = next(reader, [])
                rows = list(reader)
        except OSError:
            return {"columns": [], "rows": [], "row_labels": [], "total": 0, "offset": offset, "limit": limit}
        window = rows[offset:offset + limit]
        return {"columns": header, "rows": window,
                "row_labels": [str(offset + index) for index in range(len(window))],
                "total": len(rows), "offset": offset, "limit": limit, "file": target.name}

    @staticmethod
    def _artifact_labels(path):
        import pickle
        metadata = Path(path).parent / "metadata.pkl"
        if not metadata.is_file():
            return None
        try:
            with metadata.open("rb") as handle:
                value = pickle.load(handle)
        except Exception:  # noqa: BLE001 - labels are optional metadata
            return None
        labels = value.get("labels") if isinstance(value, dict) else None
        if not isinstance(labels, dict):
            return None
        ordered = {}
        for dim, mapping in labels.items():
            if isinstance(mapping, dict):
                ordered[dim] = [name for name, _ in sorted(mapping.items(), key=lambda item: item[1])]
            elif isinstance(mapping, list):
                ordered[dim] = list(mapping)
        if not ordered:
            return None
        dims = value.get("dims") if isinstance(value.get("dims"), list) else list(ordered)
        return {"dims": dims, "labels": ordered}

    def _file_payload(self, key, path):
        payload = read_json(path)
        summary = self.details(key).get('summary') or {}
        for role, value in payload['files'].items():
            try:
                payload['files'][role] = str(self._record_path(key, value, summary))
            except KeyError:
                # External sources remain external and are never downloadable.
                pass
        return payload

    def artifact_file(self, key, artifact_id, role):
        path, descriptor = self.artifact(key, artifact_id)
        if descriptor.get("kind") != "file":
            raise KeyError("Not a file dataset")
        from src.core.files import FileArtifact
        artifact = FileArtifact(**self._file_payload(key, path))
        artifact.validate()
        if role not in artifact.files:
            raise KeyError("Unknown file role")
        # Download generated outputs only. Source references can point outside
        # the job, but the HTTP endpoint must not become an arbitrary file reader.
        target = Path(artifact.files[role]).resolve()
        if not target.is_relative_to((self.jobs_dir / key / "output").resolve()):
            raise KeyError("This file is an external input, not a downloadable job output")
        return target

    def export_file(self, key, index):
        summary = self.details(key).get("summary") or {}
        exports = summary.get("steps", [])
        if not 0 <= index < len(exports):
            raise KeyError("找不到步骤报告。")
        directory = self.jobs_dir / key
        path = (directory / "output" / exports[index]["export_path"]).resolve()
        if not path.is_relative_to(directory):
            raise KeyError("报告路径不可用。")
        return path

    def figure_file(self, key, index, format=None, figure_id=None):
        content = read_json(self.export_file(key, index), {})
        if not isinstance(content, dict):
            raise KeyError("此步骤没有图像产物。")
        if figure_id is not None:
            selected = [item for item in content.get("figures", []) if item.get("id", "default") == figure_id]
            if not selected:
                raise KeyError("Figure ID not found in this step")
            content = {"figures": selected, "path": selected[0]["path"]}
        value = content.get("path") or content.get("figure_path")
        if format is not None:
            if format not in {"png", "pdf", "svg", "jpg", "jpeg", "webp", "tif", "tiff"}:
                raise KeyError("不支持此图表格式。")
            recorded = next((item for item in content.get("figures", [])
                             if item.get("format") == format), None)
            if recorded:
                value = recorded.get("path")
            elif not value or Path(value).suffix.lower() != '.' + format:
                raise KeyError("此运行没有保存该格式的图表。")
        if not value or Path(value).suffix.lower() not in {".png", ".pdf", ".svg", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}:
            raise KeyError("此步骤没有图像产物。")
        summary = read_json(self.jobs_dir / key / "output/run_summary.json", {})
        path = self._record_path(key, value, summary)
        directory = (self.jobs_dir / key).resolve()
        if not path.is_relative_to(directory) or not io_path(path).is_file():
            raise KeyError("图像路径不可用。")
        return path
