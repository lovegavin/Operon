"""Server-owned jobs, reached through SSH and a private Unix socket only."""
import argparse
import hashlib
from biopipe.engine.transport import transport_admission
import json
import os
from pathlib import Path
import socket
import stat
import struct
import subprocess
import sys
import tempfile
import threading
import time

from .protocol import Decoder, transmit
from biopipe.engine.control import ControlLoop, limits_from_environment
from biopipe.documents import CommandError


def receive(sock, size):
    chunks = bytearray()
    while len(chunks) < size:
        block = sock.recv(min(size-len(chunks), 65536))
        if not block:
            raise ConnectionError('Remote control connection closed')
        chunks.extend(block)
    return bytes(chunks)


def send_message(sock, value):
    data = json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
    sock.sendall(struct.pack('!Q', len(data)) + data)


def read_message(sock):
    size = struct.unpack('!Q', receive(sock, 8))[0]
    if size > 128 * 1024**2:
        raise ValueError('Control metadata exceeds 128 MiB; input data must stay in server files')
    return json.loads(receive(sock, size))


def socket_path(workspace):
    if not hasattr(os, 'getuid') or not hasattr(socket, 'AF_UNIX'):
        raise RuntimeError('The remote job service requires a Linux/Unix Python runtime')
    directory = Path(tempfile.gettempdir()) / f'biopipe-ssh-{os.getuid()}'
    directory.mkdir(mode=0o700, exist_ok=True)
    info = directory.lstat()
    if stat.S_ISLNK(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise RuntimeError('Remote control directory must be owned by this user with mode 0700')
    key = hashlib.sha256(str(Path(workspace).resolve()).encode()).hexdigest()[:24]
    return directory / (key + '.sock')


class RemoteService:
    def __init__(self, workspace, input_roots=None):
        from src.web.service import JobService, Settings
        from src.web.operator_catalog import catalog_from_descriptors
        from src.task.memory.config import MemoryConfig, AUTO_BUDGET_FRACTION
        workspace = Path(workspace).expanduser().resolve()
        workspace.mkdir(parents=True, exist_ok=True)
        code = Path(__file__).resolve().parents[2]
        # Explicit interpreter selection must also select its command-line tools.
        binary_directory = str(Path(sys.executable).parent)
        current_path = os.environ.get('PATH', '')
        if os.path.normcase(current_path.split(os.pathsep)[0]) != os.path.normcase(binary_directory):
            os.environ['PATH'] = binary_directory + os.pathsep + current_path
        self.service = JobService(Settings(workspace, workspace/'.studio', code/'frontend/dist',
                                          code_root=code, input_roots=input_roots or [Path('/')],
                                          manifest_only_registry=True),
                                  catalog_from_descriptors())
        self.memory = {'automatic_memory_budget_bytes': self.service.resources()['capacity_bytes'],
                       'automatic_memory_fraction': AUTO_BUDGET_FRACTION}
        from .handshake import ManifestHandshake
        self.handshake = ManifestHandshake(self.service, self.memory)
        from .transfers import TransferStore
        self.transfers = TransferStore(workspace/'.studio'/'transfers', resolve_input=self.transfer_path)
        self.transport_leases = {}
        self.transport_active = {}
        self.lease_lock = threading.RLock()
        # Generated checkpoints and verified upload groups belong to this
        # service even when external input roots were restricted by the owner.
        if workspace not in self.service.settings.input_roots:
            self.service.settings.input_roots.append(workspace)

    def alive(self):
        """Daemon liveness includes every durable responsibility, not just workers."""
        handshake = getattr(self, 'handshake', None)
        transfers = getattr(self, 'transfers', None)
        with self._lease_guard():
            leases = bool(self.transport_leases) or bool(self.transport_active)
        return bool(self.service.processes or self.service.threads or leases or
                    (handshake is not None and handshake.maintenance_running) or
                    (transfers is not None and bool(getattr(transfers, 'tokens', {}))))

    def _lease_guard(self):
        # Lightweight dispatch fixtures construct RemoteService via __new__;
        # initialize concurrency state lazily so the public method contract
        # does not depend on the constructor.
        if not hasattr(self, 'lease_lock'):
            self.lease_lock = threading.RLock()
            self.transport_active = {}
        return self.lease_lock

    def _purge_transport_leases(self):
        now = time.monotonic()
        expired = []
        with self._lease_guard():
            for key, expires in list(self.transport_leases.items()):
                if expires < now and not self.transport_active.get(key):
                    del self.transport_leases[key]
                    expired.append(key)
        for key in expired:
            transport_admission(self.service).release(key)

    def _begin_transfer(self, key):
        """Pin a transport lease for the duration of an operation.

        Timeout cleanup must never release a buffer while a transfer still owns
        it; the active counter makes expiry conditional on no live operation.
        """
        with self._lease_guard():
            self.transport_active[key] = self.transport_active.get(key, 0) + 1
            if key not in self.transport_leases:
                ready = transport_admission(self.service).reserve(
                    key, {'reserved_bytes': 6 * 1024**2, 'cpu_threads': 0, 'kind': 'transport'})
                if not ready:
                    self.transport_active[key] -= 1
                    if not self.transport_active[key]:
                        del self.transport_active[key]
                    raise ValueError('Transfer memory is unavailable; retry admission')
            self.transport_leases[key] = time.monotonic() + 30

    def _end_transfer(self, key):
        with self._lease_guard():
            count = self.transport_active.get(key, 0) - 1
            if count > 0:
                self.transport_active[key] = count
            else:
                self.transport_active.pop(key, None)
            if key in self.transport_leases:
                self.transport_leases[key] = time.monotonic() + 30

    def transfer_path(self, value):
        from .transfers import no_symlinks
        no_symlinks((self.service.root/value).expanduser())
        return self.path(value)

    def graph_catalog(self, graph):
        return self.service.plugins.catalog_for(graph, self.service.base_catalog)

    def _journal(self):
        runtime = getattr(self.service, 'engine', None)
        if runtime is None or getattr(runtime, 'error', None):
            return None
        return getattr(runtime, 'journal', None)

    def _recover_run(self, request_id, digest):
        """Find durable job evidence for an interrupted submission."""
        for index, item in enumerate(self.service.jobs_dir.glob('*/job.json')):
            if index >= 10000:
                break
            try:
                record = json.loads(item.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                continue
            runtime = record.get('graph', {}).get('runtime', {})
            if runtime.get('remote_request_id') != request_id:
                continue
            if runtime.get('remote_request_digest') != digest:
                raise ValueError('Submission identity was already used with a different graph')
            return self.service.details(record['id'])
        return None

    def events(self, params):
        if self.service.pool_remote:
            return self.service.events(params.get('after', params.get('cursor', 0)),
                                       run_id=params.get('run_id'), limit=params.get('limit', 200))
        journal = self._journal()
        if journal is None:
            return {'available': False, 'events': [], 'cursor': int(params.get('after', 0) or 0),
                    'has_more': False}
        after = params.get('after', params.get('cursor', 0))
        limit = params.get('limit', 200)
        try:
            after = max(0, int(after))
            limit = max(1, min(int(limit), 1000))
        except (TypeError, ValueError) as exc:
            raise ValueError('Invalid event cursor or limit') from exc
        page = journal.page(after, run_id=params.get('run_id'), limit=limit,
                            max_bytes=params.get('max_bytes', 256 * 1024))
        return {**page.to_json(), 'available': True}

    def close(self):
        self.handshake.close()
        with self._lease_guard():
            leases = list(self.transport_leases)
            self.transport_leases.clear()
            self.transport_active.clear()
        for lease in leases:
            transport_admission(self.service).release(lease)
        self.service.shutdown()

    def path(self, value):
        path = (self.service.root / value).expanduser().resolve()
        if not any(path.is_relative_to(root.resolve()) for root in self.service.settings.input_roots):
            raise ValueError('Path is outside the configured server data roots')
        return path

    def dispatch(self, method, params):
        if method != 'transport_release':
            self._purge_transport_leases()
        if method in ('handshake', 'bootstrap'):
            return self.handshake.response(params, legacy=method == 'bootstrap')
        if method == 'refresh_registry':
            guard = (self.service.execution_environment_guard() if hasattr(self.service, 'execution_environment_guard') else getattr(self.service, 'environment_guard', None))
            environment = self.service.environment_identity() if guard is not None else None
            def acquire():
                return (guard, guard.begin(owner=self.service.owner, kind='registry-refresh',
                                           environment=environment)) if guard is not None else None
            # The handshake's single-flight decision owns acquisition. A
            # repeated refresh observes the existing operation, not a second
            # conflicting environment maintenance request.
            return self.handshake.refresh(params, maintenance_factory=acquire)
        if method == 'refresh_status':
            return self.handshake.response(params, legacy=True)
        if method in ('transport_reserve', 'transport_release'):
            key = params['id']
            if not isinstance(key, str) or not __import__('re').fullmatch('transfer-[a-f0-9]{32}', key):
                raise ValueError('Invalid transfer allocation identity')
            if method == 'transport_release':
                with self._lease_guard():
                    if self.transport_active.get(key):
                        raise ValueError('A transfer still owns this allocation')
                    self.transport_leases.pop(key, None)
                transport_admission(self.service).release(key)
                return {'released': True}
            # Framing/decoded buffers are bounded by the transport implementation.
            with self._lease_guard():
                reserved = transport_admission(self.service).reserve(
                    key, {'reserved_bytes': 6 * 1024**2, 'cpu_threads': 0, 'kind': 'transport'})
                if reserved:
                    self.transport_leases[key] = time.monotonic() + 30
            return {'reserved': reserved}
        if method.startswith('transfer_'):
            params = dict(params)
            lease = params.pop('_transport_lease', None)
            if lease:
                self._begin_transfer(lease)
                try:
                    return self.transfers.dispatch(method, params)
                finally:
                    self._end_transfer(lease)
            return self.transfers.dispatch(method, params)
        if method == 'events':
            return self.events(params)
        if method == 'engine_status':
            return self.service._engine_status()
        from src.web.models import Graph
        from src.web.service import safe_json
        from src.web.graph import compile_graph, relative_manifest
        from src.web.contracts import analyze_graph
        from src.web.parameters import freeze_graph
        from src.web.routes import prepare_interface
        service = self.service
        if method == 'validate_environment':
            from biopipe.readiness import inspect_declared_environment
            ids = params.get('ids')
            if not isinstance(ids, list) or any(not isinstance(key, str) for key in ids):
                raise ValueError('ids must be an explicit list of declaration IDs')
            scripts = params.get('scripts', {})
            if not isinstance(scripts, dict):
                raise ValueError('scripts must map node IDs to frozen script declarations')
            graph = Graph.model_validate(params['graph']) if params.get('graph') else None
            guard = (service.execution_environment_guard() if hasattr(service, 'execution_environment_guard') else getattr(service, 'environment_guard', None))
            token = None
            if params.get('repair') is True and guard is not None:
                token = guard.begin(owner=service.owner, kind='remote-repair',
                                    environment=service.environment_identity())
            try:
                return inspect_declared_environment(service, ids, graph=graph, scripts=scripts,
                                                    repair=params.get('repair') is True)
            finally:
                if token is not None:
                    guard.end(token)
        if method == 'resources':
            return service.resources()
        if method == 'pin_compatibility':
            from src.web.execution_pins import validated_pins
            return validated_pins(service, params.get('pins', {}))
        if method == 'file_stat':
            values = params.get('paths', [])
            if not isinstance(values, list) or len(values) > 256:
                raise ValueError('Invalid file metadata request')
            result = []
            for value in values:
                path = self.transfer_path(str(self.path(params.get('base', '.')) / value))
                result.append({'path': str(path), 'exists': path.is_file(),
                               'bytes': path.stat().st_size if path.is_file() else None})
            return result
        if method == 'exchange':
            key = params['job_id']; service.require(key)
            path = service.jobs_dir / key / 'output' / 'exchange.json'
            if not path.is_file():
                raise ValueError('The stage has no committed exchange outputs')
            value = json.loads(path.read_text(encoding='utf-8'))
            return value
        if method == 'preview':
            return service.preview(params['job_id'], params['artifact_id'],
                                   offset=params.get('offset', 0), limit=params.get('limit', 20))
        if method == 'output_file':
            key = params['job_id']; kind = params['kind']
            if kind == 'artifact':
                path, _ = service.artifact(key, params['artifact_id'])
            elif kind == 'artifact_file':
                path = service.artifact_file(key, params['artifact_id'], params['role'])
            elif kind == 'figure':
                path = service.figure_file(key, params['index'], format=params.get('format'), **({'figure_id': params['figure_id']} if 'figure_id' in params else {}))
            elif kind == 'export':
                path = service.export_file(key, params['index'])
            else:
                raise ValueError('Unknown output kind')
            return {'path': str(path), 'bytes': path.stat().st_size, 'name': path.name}
        if method == 'browse':
            folder = self.path(params.get('path') or '.')
            if not folder.is_dir():
                raise ValueError('Choose an existing server directory')
            offset = max(0, int(params.get('offset', 0)))
            entries = []
            with os.scandir(folder) as listing:
                for item in listing:
                    if item.name.startswith('.') and not params.get('hidden', False):
                        continue
                    try:
                        path = self.path(str(folder/item.name))
                        info = item.stat()
                        entries.append({'name': item.name, 'path': str(path), 'directory': item.is_dir(),
                                        'bytes': info.st_size, 'modified': info.st_mtime})
                    except (PermissionError, FileNotFoundError, ValueError):
                        continue
            entries.sort(key=lambda item: (not item['directory'], item['name'].lower()))
            return {'path': str(folder), 'parent': str(folder.parent), 'entries': entries[offset:offset+200],
                    'next_offset': offset+200 if offset+200 < len(entries) else None}
        if method == 'source':
            from biopipe.reader_selection import candidates as select
            path = self.path(params['path'])
            if not path.is_file():
                raise ValueError('Choose an existing server file')
            candidates = select(service.catalog['readers'], path, params.get('reader'), check_siblings=True)
            if len(candidates) != 1:
                raise ValueError('No unique registered Reader matches this server file')
            reader = candidates[0]; settings = reader.get('file_input', {})
            return {'filename': path.name, 'reader': reader['id'], 'bytes': path.stat().st_size,
                    'source': {'reader': reader['id'], 'path': str(path), 'dims': settings.get('dims', ['sample', 'feature']),
                               'labels': settings.get('labels', {'sample': 'auto', 'feature': 'builtin'}),
                               'args': reader.get('runtime_defaults', {})}}
        if method in ('validate', 'prepare', 'export', 'run'):
            graph = Graph.model_validate(params['graph'])
            if method == 'run':
                request_id = params['request_id']
                digest = hashlib.sha256(json.dumps(params['graph'], sort_keys=True).encode()).hexdigest()
                if not isinstance(request_id, str) or not __import__('re').fullmatch('[a-f0-9-]{32,36}', request_id):
                    raise ValueError('Invalid submission identity')
                # Reconnect/retry must return the original job, even if the SSH
                # response vanished after the process was spawned.
                recovered = self._recover_run(request_id, digest)
                if recovered is not None:
                    return recovered
                graph.runtime['remote_request_id'] = request_id
                graph.runtime['remote_request_digest'] = digest
                from biopipe.readiness import required_ids, required_scripts, inspect_declared_environment
                checked = inspect_declared_environment(service, required_ids(graph, self.graph_catalog(graph)),
                                                       graph=graph, scripts=required_scripts(graph))
                missing = [key for key, item in {**checked['entries'], **checked['scripts']}.items()
                           if item.get('status') != 'passed']
                if missing:
                    raise ValueError('Execution dependencies are not ready: ' + ', '.join(missing))
                if getattr(service, 'pool_remote', False):
                    # The pool owns the durable claim. Forward the original key,
                    # including after a lost SSH response; never scan then launch
                    # with a new identity in a different allocator.
                    return service.launch(graph, request_id=request_id)
                journal = self._journal()
                if journal is None:
                    from .client import RemoteError
                    raise RemoteError('The submission journal is unavailable; no job was started.',
                                      code='engine_unavailable')
                try:
                    claim = journal.claim(request_id, digest, operation='run',
                                          receipt={'request_id': request_id})
                except Exception as exc:
                    if getattr(exc, 'code', None) == 'idempotency_conflict':
                        raise ValueError('Submission identity was already used with a different graph') from exc
                    from .client import RemoteError
                    from biopipe.engine.contracts import CommitOutcomeUnknown
                    if isinstance(exc, CommitOutcomeUnknown):
                        recovered = self._recover_run(request_id, digest)
                        if recovered is not None:
                            return recovered
                        raise RemoteError('Submission acknowledgement was lost; retry the same request identity.',
                                          code='submission_uncertain') from exc
                    raise RemoteError('The submission journal is unavailable; no job was started.',
                                      code='engine_unavailable') from exc
                if not claim.created:
                    record = claim.record
                    if record.get('run_id'):
                        return service.details(record['run_id'])
                    if record['state'] in ('claimed', 'launching'):
                        record = journal.wait(request_id, timeout=120) or record
                        if record.get('run_id'):
                            return service.details(record['run_id'])
                    recovered = self._recover_run(request_id, digest)
                    if recovered is not None:
                        journal.bind(request_id, recovered['id'])
                        return recovered
                    raise CommandError('submission_uncertain',
                                       'Submission was interrupted; inspect jobs before retrying', 409,
                                       {'request_id': request_id})
                try:
                    result = service.launch(graph)
                except Exception as exc:
                    recovered = self._recover_run(request_id, digest)
                    if recovered is not None:
                        journal.bind(request_id, recovered['id'])
                        return recovered
                    journal.fail(request_id, str(exc))
                    raise
                journal.bind(request_id, result['id'])
                return result
            catalog = self.graph_catalog(graph)
            if method == 'prepare':
                return prepare_interface(freeze_graph(service.plugins.pin(graph), catalog, service.root), catalog,
                                         service.root).model_dump(mode='json')
            manifest, order = compile_graph(graph, catalog, service.root,
                                            require_files=method == 'validate' and params.get('require_files', True), input_roots=service.settings.input_roots)
            if method == 'export':
                import yaml
                return {'yaml': yaml.safe_dump(relative_manifest(manifest, service.root/graph.base_dir, catalog),
                                               allow_unicode=True, sort_keys=False), 'order': order}
            return {'valid': True, 'order': order, 'contracts': analyze_graph(graph, catalog, service.root)}
        if method == 'history':
            return service.history()
        if method == 'console':
            key = params['job_id']; service.require(key)
            path = service.jobs_dir/key/'console.log'
            if not path.is_file():
                _, result = service.console_snapshot(key, service.details(key))
                return {'text': result['console'], 'offset': 0, 'done': True}
            with path.open('rb') as handle:
                handle.seek(max(0, int(params.get('offset', 0))))
                data = handle.read(64 * 1024)
                # Return bytes as base64 so chunk boundaries cannot split UTF-8.
                import base64
                return {'base64': base64.b64encode(data).decode(), 'offset': handle.tell(),
                        'done': not bool(handle.read(1))}
        if method == 'job':
            return service.details(params['job_id'])
        if method == 'cancel':
            return service.cancel(params['job_id'])
        if method == 'poll':
            key = params['job_id']; job = service.details(key)
            offsets = params.get('offsets', {}); result = {}; events = []; eof = True
            for path in service.event_paths(key):
                name = path.relative_to(service.jobs_dir/key).as_posix()
                start = max(0, int(offsets.get(name, 0)))
                with path.open('rb') as handle:
                    handle.seek(min(start, path.stat().st_size))
                    for _ in range(200):
                        position = handle.tell(); line = handle.readline()
                        if not line: break
                        if not line.endswith(b'\n'):
                            handle.seek(position); break
                        try: events.append(json.loads(line))
                        except (ValueError, UnicodeDecodeError): pass
                    result[name] = handle.tell()
                    eof = eof and not bool(handle.read(1))
            _, console = service.console_snapshot(key, job)
            job.pop('graph', None)
            return safe_json({'job': job, 'events': sorted(events, key=lambda e: e.get('time', '')),
                              'offsets': result, 'done': job['status'] not in ('running', 'queued', 'preparing', 'uploading') and job.get('logs_complete', True) and eof,
                              **(console or {})})
        raise ValueError('Unknown remote operation')


def rpc(workspace, request):
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(90)
        client.connect(str(socket_path(workspace)))
        send_message(client, request)
        return read_message(client)


def ensure_daemon(workspace):
    import fcntl
    from .handshake import daemon_request, validate_daemon_response
    address = socket_path(workspace)
    with address.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            response = rpc(workspace, daemon_request())
            validate_daemon_response(response)
            return
        except (FileNotFoundError, ConnectionRefusedError):
            pass
        directory = Path(workspace)/'.studio/remote'
        directory.mkdir(parents=True, exist_ok=True)
        with (directory/'service.log').open('ab') as log:
            subprocess.Popen([sys.executable, '-m', 'biopipe.remote.server', '--serve', '--workspace', str(workspace)],
                             cwd=Path(__file__).resolve().parents[2], stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                             start_new_session=True)
        deadline = time.monotonic()+60
        while time.monotonic() < deadline:
            try:
                validate_daemon_response(rpc(workspace, daemon_request()))
                return
            except (FileNotFoundError, ConnectionRefusedError):
                time.sleep(.15)
        raise RuntimeError('Remote service did not start; inspect .studio/remote/service.log on the server')


def serve(workspace):
    address = socket_path(workspace)
    service = RemoteService(workspace)
    address.unlink(missing_ok=True)
    loop = ControlLoop(service.dispatch, limits=limits_from_environment())
    with socket.socket(socket.AF_UNIX) as listener:
        listener.bind(str(address)); os.chmod(address, 0o600)
        listener.listen(64)
        try:
            loop.serve(listener, alive=service.alive, idle_seconds=300)
        finally:
            address.unlink(missing_ok=True)
            service.close()


class TerminalInput:
    """Unbuffered line input so select also observes already received lines."""
    def __init__(self):
        self.buffer = b''

    def line(self, deadline=None):
        import select
        while b'\n' not in self.buffer:
            timeout = None if deadline is None else max(0, deadline-time.monotonic())
            if not select.select([sys.stdin.fileno()], [], [], timeout)[0]:
                raise TimeoutError('SSH peer did not acknowledge the response')
            data = os.read(sys.stdin.fileno(), 65536)
            if not data: raise EOFError('SSH peer disconnected')
            self.buffer += data
        line, self.buffer = self.buffer.split(b'\n', 1)
        return line.decode('utf-8', errors='replace')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--serve', action='store_true')
    args = parser.parse_args()
    workspace = Path(args.workspace).expanduser().resolve()
    if args.serve:
        serve(workspace); return
    try:
        ensure_daemon(workspace)
    except Exception as exc:
        print('BIOPIPE_REMOTE_ERROR ' + json.dumps({'code': getattr(exc, 'code', 'service_unavailable'),
                                                   'error': str(exc)}, ensure_ascii=False), flush=True)
        return
    print('\nBIOPIPE_REMOTE_READY 1', flush=True)
    decoder = Decoder('Q')
    terminal = TerminalInput()
    def write(value):
        sys.stdout.write(value); sys.stdout.flush()
    while True:
        try: line = terminal.line()
        except EOFError: return
        if line.strip() == 'BIOPIPE_REMOTE_CLOSE 1':
            return
        try: request = decoder.feed(line)
        except ValueError: continue
        if decoder.ack: write(decoder.ack)
        if request is None: continue
        try: response = rpc(workspace, request)
        except Exception as exc:
            response = {'ok': False, 'error': str(exc), 'code': getattr(exc, 'code', 'remote_error')}
        response['id'] = request.get('id')
        try: transmit(response, 'R', write, terminal.line)
        except (EOFError, TimeoutError): return


if __name__ == '__main__':
    main()
