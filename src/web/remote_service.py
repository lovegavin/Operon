"""Editor-side remote references and on-demand, bounded result transfers."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import threading
import time
import uuid

from pydantic import Field, field_validator, model_validator
from .models import StrictModel, Graph
from .storage import atomic_json
from .service import read_json
from .source_paths import remote_profile
from operon.remote.client import SSHConnection, HostKeyRequired, RemoteError


class ConnectionProfile(StrictModel):
    id: str | None = Field(default=None, pattern='^[a-f0-9]{32}$')
    name: str = Field(min_length=1, max_length=80)
    host: str = Field(min_length=1, max_length=253, pattern=r'^[A-Za-z0-9.:\[\]-]+$')
    port: int = Field(default=22, ge=1, le=65535)
    username: str = Field(min_length=1, max_length=128)
    auth: str = Field(default='password', pattern='^(password|key|agent)$')
    key_path: str = ''
    python: str = 'python3'
    app_dir: str = ''
    workspace: str = ''
    environment: str = Field(default='existing', pattern='^(existing|managed)$')
    managed_root: str = ''
    mode: str = Field(default='exec', pattern='^(exec|shell)$')
    menu_choice: str = Field(default='', pattern='^([0-9]{1,4})?$')

    @field_validator('username', 'key_path', 'python', 'app_dir', 'workspace', 'managed_root')
    @classmethod
    def no_control(cls, value):
        if any(ord(char) < 32 for char in value):
            raise ValueError('Connection fields cannot contain control characters')
        return value

    @field_validator('app_dir', 'workspace', 'managed_root')
    @classmethod
    def absolute_server_path(cls, value):
        if value and (not PurePosixPath(value).is_absolute() or '..' in PurePosixPath(value).parts):
            raise ValueError('Use an absolute Linux server path')
        return value

    @model_validator(mode='after')
    def required_existing_paths(self):
        if self.environment == 'existing' and (not self.app_dir or not self.workspace or not self.python):
            raise ValueError('Existing environments require Operon, Python and workspace paths')
        return self


def _has_dependency_status(info):
    """True when the handshake already carries a populated dependency snapshot."""
    dependencies = (info or {}).get('dependencies') or {}
    return bool(isinstance(dependencies, dict) and dependencies.get('entries'))


class RemoteManager:
    def __init__(self, service, connection_factory=SSHConnection):
        self.service, self.factory = service, connection_factory
        self.directory = service.directory/'remote'; self.directory.mkdir(exist_ok=True)
        self.path = self.directory/'profiles.json'
        self.state = read_json(self.path, {'profiles': {}, 'jobs': {}, 'pending': {}})
        self.connections, self.credentials, self.pending_keys = {}, {}, {}
        self.connecting, self.progress = {}, {}
        self.library_operations = {}
        self.lock = threading.RLock()
        self._build = None

    def local_build(self):
        """Identity of the application and operator library this desktop ships."""
        if self._build is None:
            try:
                from operon.build_identity import build_identity
                root = getattr(self.service.settings, 'code_root', None) or self.service.root
                self._build = build_identity(root)
            except Exception:  # noqa: BLE001 - old checkouts and isolated tests
                self._build = {}
        return deepcopy(self._build)

    def build(self, key):
        from operon.build_identity import matches
        connection = self.connections.get(key)
        if not connection or not connection.connected:
            raise RemoteError('请先连接服务器。', code='remote_disconnected')
        local = self.local_build()
        remote = connection.call('build_info', {})
        return {'local': local, 'remote': remote,
                'matches': bool(local and remote.get('build') and matches(local, remote['build']))}

    def persist(self):
        with self.lock:
            atomic_json(self.path, self.state)
            self.path.chmod(0o600)

    def profile(self, key):
        if key not in self.state['profiles']: raise KeyError('找不到服务器连接配置。')
        return self.state['profiles'][key]

    def status(self):
        return [{'profile': {k: v for k, v in profile.items() if k != 'host_key'},
                 'fingerprint': profile.get('host_key', {}).get('fingerprint'),
                 'connected': bool(self.connections.get(key) and self.connections[key].connected),
                 'info': read_json(self.directory/(key+'.catalog.json'))}
                for key, profile in self.state['profiles'].items()]

    def save(self, value):
        with self.lock:
            profile = ConnectionProfile.model_validate(value).model_dump()
            key = profile['id'] or uuid.uuid4().hex; profile['id'] = key
            if key in self.connecting:
                raise RemoteError('连接准备中，请先取消。')
            old = self.state['profiles'].get(key, {})
            if old.get('host') == profile['host'] and old.get('port') == profile['port'] and old.get('host_key'):
                profile['host_key'] = old['host_key']
            if old and profile != old:
                self.disconnect(key)
                (self.directory/(key+'.catalog.json')).unlink(missing_ok=True)
            self.state['profiles'][key] = profile; self.persist()
            return {k: v for k, v in profile.items() if k != 'host_key'}

    def trust(self, key, fingerprint):
        with self.lock:
            observed = self.pending_keys.get(key)
            if not observed or observed['fingerprint'] != fingerprint:
                raise ValueError('主机指纹已过期，请重新连接以核对。')
            self.profile(key)['host_key'] = observed
            del self.pending_keys[key]; self.persist()

    def connect(self, key, credentials, *, install=False):
        with self.lock:
            if key in self.connecting:
                raise RemoteError('此服务器正在连接或准备环境。')
            profile = deepcopy(self.profile(key))
            build = self.local_build()
            profile['build'] = build
            if install and profile.get('environment') != 'managed':
                raise RemoteError('已有环境请由服务端管理员维护；自动安装仅用于托管安装目录。')
            secret = credentials or self.credentials.get(key, {})
            if self.connections.get(key): self.connections.pop(key).close()
            cancel = self.connecting[key] = threading.Event()
            self.progress[key] = {'running': True, 'lines': [], 'error': ''}
        def report(message):
            with self.lock:
                lines = self.progress[key]['lines']
                if not lines or lines[-1] != message:
                    lines.append(message); del lines[:-60]
        try:
            report('正在连接 SSH')
            cached = read_json(self.directory/(key+'.catalog.json'))
            if cached and build.get('build_id') != (cached.get('build_id') or
                                                    cached.get('handshake', {}).get('build_id')):
                # A catalog cached against another local build cannot be used
                # to migrate execution pins; force a fresh handshake catalog.
                cached = None
            connection = (self.factory(profile, secret, progress=report, cancel=cancel,
                                       install=install, cached_info=cached)
                          if self.factory is SSHConnection else self.factory(profile, secret))
            with self.lock:
                if cancel.is_set():
                    connection.close()
                    raise RemoteError('连接已取消。', code='remote_cancelled')
                self.connections[key] = connection; self.credentials[key] = secret
                info = connection.info
                if not self.profile(key)['workspace']:
                    self.profile(key)['workspace'] = info['workspace']
                if info.get('build'): info.setdefault('build_id', info['build'].get('build_id', ''))
                atomic_json(self.directory/(key+'.catalog.json'), info)
                for job in info.get('history', []): self.wrap_job(key, job)
                self.persist()
                report('已连接')
            if install or not _has_dependency_status(info):
                try:
                    report('正在核对依赖状态')
                    info = self.refresh(key, verify_all=True)
                    report('依赖状态已更新')
                except RemoteError as exc:
                    report(f'依赖状态将在刷新后更新：{exc}')
            if hasattr(self.service, 'plugins'):
                try:
                    self.check_library(key)
                    info = connection.info
                except Exception as exc:
                    # A comparison failure must not turn a working SSH session
                    # into a failed connection. It is retryable in Settings.
                    info['library_check'] = {'error': str(exc)}
                    atomic_json(self.directory/(key+'.catalog.json'), info)
            return info
        except HostKeyRequired as exc:
            with self.lock:
                self.pending_keys[key] = exc.key
            raise
        except Exception as exc:
            message = str(exc) if isinstance(exc, RemoteError) else f'SSH 连接失败：{type(exc).__name__}。请核对主机、认证方式及远端环境。'
            with self.lock:
                self.progress[key]['error'] = message
            if isinstance(exc, RemoteError): raise
            raise RemoteError(message) from exc
        finally:
            with self.lock:
                self.connecting.pop(key, None)
                self.progress[key]['running'] = False

    def refresh(self, key, *, verify_all=False):
        """Explicit maintenance only; ordinary connect never scans/installs."""
        connection = self.connections.get(key)
        if not connection or not connection.connected:
            raise RemoteError('请先连接服务器。', code='remote_disconnected')
        info = connection.call('refresh_registry', {'verify_all': bool(verify_all)})
        deadline = time.monotonic() + 600
        while True:
            if not isinstance(info, dict) or not isinstance(info.get('catalog'), dict):
                raise RemoteError('服务端没有返回有效的算子清单。')
            with self.lock:
                if self.connections.get(key) is not connection:
                    raise RemoteError('连接已改变；服务端维护仍可独立完成。', code='remote_disconnected')
                connection.info = info
                atomic_json(self.directory/(key+'.catalog.json'), info)
            maintenance = info.get('registry_refresh', {})
            if not maintenance.get('running'):
                if maintenance.get('error'):
                    raise RemoteError(maintenance['error'], code='registry_refresh_failed')
                if hasattr(self.service, 'plugins'):
                    self.check_library(key)
                return connection.info
            if time.monotonic() >= deadline:
                raise RemoteError('服务端维护仍在进行，可稍后刷新查看结果。', code='registry_refresh_pending')
            time.sleep(.5)
            info = connection.call('refresh_status')

    def setup_status(self, key):
        with self.lock:
            self.profile(key)
            return deepcopy(self.progress.get(key, {'running': False, 'lines': [], 'error': ''}))

    def check_library(self, key):
        from operon.remote.library import inventory, compare
        connection = self.connections.get(key)
        if not connection or not connection.connected:
            raise RemoteError('请先连接服务器。', code='remote_disconnected')
        supported = 'library_sync_v1' in connection.info.get('handshake', {}).get('library_capabilities', [])
        local = inventory(self.service.plugins.state())
        if supported:
            remote = connection.call('library_manifest', {})
        else:
            # Older servers can still report missing IDs through their catalog;
            # they require an explicit server upgrade before package transfer.
            catalog = connection.info.get('catalog', {})
            entries = [{'id': d['id'], 'kind': kind} for kind, field in
                       (('operator', 'operators'), ('reader', 'readers')) for d in catalog.get(field, [])]
            remote = {'revision': '', 'packages': [{'name': 'older-server', 'enabled': True, 'entries': entries}]}
        result = compare(local, remote, supported=supported)
        remote_build = remote.get('build') or connection.info.get('build') or {}
        local_build = self.local_build()
        try:
            from operon.build_identity import matches
            same_build = bool(local_build and remote_build and matches(local_build, remote_build))
        except Exception:  # noqa: BLE001 - malformed old receipts simply need an upgrade
            same_build = False
        result['build'] = {'local': local_build.get('build_id', ''),
                           'remote': remote_build.get('build_id', ''),
                           'matches': same_build}
        managed = self.profile(key).get('environment') == 'managed'
        result['replacement_required'] = bool(result.get('changed_count')) or (managed and not same_build)
        with self.lock:
            if self.connections.get(key) is not connection:
                raise RemoteError('连接已改变，请重新检查。', code='remote_disconnected')
            connection.info['library_check'] = result
            atomic_json(self.directory/(key+'.catalog.json'), connection.info)
        return result

    def library_status(self, key):
        with self.lock:
            self.profile(key)
            return deepcopy(self.library_operations.get(key, {'status': 'idle'}))

    def start_library_install(self, key, payload):
        names = payload.get('packages')
        if not isinstance(names, list) or not names or any(not isinstance(n, str) for n in names) or len(set(names)) != len(names):
            raise RemoteError('请选择要补齐的算子包。')
        with self.lock:
            self.profile(key)
            if self.library_operations.get(key, {}).get('status') == 'running':
                raise RemoteError('算子库正在安装，请等待完成。', code='maintenance_busy')
            connection = self.connections.get(key)
            if not connection or not connection.connected:
                raise RemoteError('请先连接服务器。', code='remote_disconnected')
            self.library_operations[key] = {'status': 'running', 'phase': 'checking', 'error': None}
            worker = threading.Thread(target=self._install_library, args=(key, connection, deepcopy(payload)),
                                      name='operon-library-transfer', daemon=True)
            worker.start()
            return deepcopy(self.library_operations[key])

    def _install_library(self, key, connection, payload):
        from tempfile import TemporaryDirectory
        from operon.remote.library import inventory, export_provider
        from operon.engine.transport import transport_admission
        from .transfers import TransferClient
        lease = 'transfer-' + uuid.uuid4().hex
        admission = None
        local_reserved = remote_reserved = False
        def progress(value):
            with self.lock:
                self.library_operations[key].update(value)
        def cancelled():
            return self.connections.get(key) is not connection or not connection.connected
        try:
            checked = self.check_library(key)
            if not checked['supported']:
                raise RemoteError('请先升级服务端，再补齐算子库。', code='capability_missing')
            if any(checked[k] != payload.get(k) for k in ('local_revision', 'remote_revision')):
                raise RemoteError('算子库已变化，请重新检查并选择。', code='library_changed')
            allowed = {p['name'] for p in checked['packages'] if p['selectable']}
            if not set(payload['packages']) <= allowed:
                raise RemoteError('选中的包无法安全补齐，请重新检查算子库。')
            state = self.service.plugins.state()
            if inventory(state)['revision'] != checked['local_revision']:
                raise RemoteError('本地算子库已变化，请重新检查。')
            admission = transport_admission(self.service)
            transfer = TransferClient(lambda method, params: connection.call(method, {**params, '_transport_lease': lease}),
                                      self.directory/'library-transfers')
            local_reserved = admission.reserve(lease, {'reserved_bytes': transfer.buffer_budget_bytes,
                                                      'cpu_threads': 0, 'kind': 'transport'})
            if not local_reserved:
                raise RemoteError('本地传输内存暂不可用，请稍后重试。')
            remote_reserved = connection.call('transport_reserve', {'id': lease})['reserved']
            if not remote_reserved:
                raise RemoteError('服务器传输内存暂不可用，请稍后重试。')
            with TemporaryDirectory(prefix='library-', dir=self.directory) as temporary:
                files = []
                for index, name in enumerate(payload['packages']):
                    if cancelled():
                        raise RemoteError('连接已断开；重连后可重试并复用已上传文件。')
                    progress({'phase': 'packaging', 'package': name, 'index': index + 1, 'total': len(payload['packages'])})
                    wheel = export_provider(self.service.plugins, state, name, Path(temporary)/str(index))
                    reference = transfer.upload(wheel, progress=progress, cancel=cancelled)
                    files.append({'filename': wheel.name, 'reference': reference})
                progress({'phase': 'installing'})
                info = connection.call('library_install', {'files': files, 'remote_revision': checked['remote_revision']})
                deadline = time.monotonic() + 900
                while info.get('registry_refresh', {}).get('running'):
                    if cancelled() or time.monotonic() > deadline:
                        raise RemoteError('服务端安装可能仍在继续；重新连接并检查算子库以确认结果。')
                    time.sleep(.5)
                    info = connection.call('refresh_status', {})
                if info.get('registry_refresh', {}).get('error'):
                    raise RemoteError(info['registry_refresh']['error'])
                with self.lock:
                    if cancelled():
                        raise RemoteError('连接已改变；请重新检查算子库。')
                    connection.info = info
                result = self.check_library(key)
                if any(p['missing'] for p in result['packages'] if p['name'] in payload['packages']):
                    raise RemoteError('服务端仍缺少选中的算子，请重新检查维护结果。')
                progress({'status': 'complete', 'phase': 'complete', 'result': result})
        except Exception as exc:
            progress({'status': 'failed', 'error': str(exc)})
        finally:
            if remote_reserved:
                try:
                    connection.call('transport_release', {'id': lease})
                except Exception:
                    pass  # The server expires inactive transport reservations.
            if local_reserved:
                admission.release(lease)

    def disconnect(self, key):
        with self.lock:
            if key in self.connecting: self.connecting[key].set()
            connection = self.connections.pop(key, None)
            if connection: connection.close()
            self.credentials.pop(key, None)

    def close(self):
        for event in self.connecting.values(): event.set()
        for key in list(self.connections): self.disconnect(key)
        self.pending_keys.clear()

    def remove(self, key):
        with self.lock:
            if key in self.connecting:
                raise RemoteError('请先取消连接，等待环境准备结束后移除。')
            self.profile(key); self.disconnect(key)
            del self.state['profiles'][key]
            self.state['jobs'] = {k:v for k,v in self.state['jobs'].items() if v['profile_id'] != key}
            (self.directory/(key+'.catalog.json')).unlink(missing_ok=True)
            self.persist()

    def call(self, key, method, params=None):
        self.profile(key)
        connection = self.connections.get(key)
        if not connection or not connection.connected:
            raise RemoteError('服务器未连接。请在服务器面板重新连接，服务器上的任务会继续运行。', code='remote_disconnected')
        return connection.call(method, params)

    def catalog(self, graph):
        key = remote_profile(graph)
        self.profile(key)
        info = read_json(self.directory/(key+'.catalog.json'))
        if not info: raise RemoteError('先连接服务器，读取服务器算子注册表。')
        return info['catalog']

    def prepare(self, graph):
        from .parameters import freeze_graph
        from .routes import prepare_interface
        catalog = self.catalog(graph)
        state = read_json(self.directory/(remote_profile(graph)+'.catalog.json')) or {}
        check = state.get('library_check') or {}
        if check.get('replacement_required'):
            raise RemoteError('服务端算子库与本地版本不一致，请先安装 / 升级服务端后再运行。',
                              code='library_replacement_required')
        graph = graph.model_copy(deep=True)
        from operon.pins import graphs
        for part in graphs(graph):
            used = {node.operator for node in part.nodes if node.kind == 'operator'}
            # Readers are keyed by file extension; the server resolves ambiguous
            # companion formats when validating the actual server files.
            from .source_paths import source_candidates
            for node in part.nodes:
                if node.source and node.source.path and node.id not in part.runtime.get('exchange_inputs', []):
                    used.update(r['id'] for r in source_candidates(graph, catalog, self.service.root,
                                node.source.path, node.source.location, node.source.reader,
                                input_roots=self.service.settings.input_roots))
            for descriptor in catalog['operators'] + catalog.get('readers', []):
                if descriptor['id'] in used and descriptor.get('implementation'):
                    current = deepcopy(descriptor['implementation'])
                    previous = part.plugin_lock.get(descriptor['id'])
                    if previous != current:
                        if previous is not None:
                            # Keep the old pin as a string: plugin_lock values are
                            # dict[str, str] and must survive JSON round-trips.
                            current['migrated_from'] = json.dumps(previous, sort_keys=True)
                        part.plugin_lock[descriptor['id']] = current
        # Saved canvas snapshots remain editable offline. Fresh server pins are
        # resolved on submission; existing pins are never silently discarded.
        return prepare_interface(freeze_graph(graph, catalog, self.service.root,
                                 input_roots=self.service.settings.input_roots), catalog, self.service.root,
                                 input_roots=self.service.settings.input_roots)

    def wrap_job(self, key, job):
        job = deepcopy(job)
        remote_id = job['id']; local_id = 'ssh-'+key+'-'+remote_id
        profile = self.profile(key)
        remote = {'profile_id': key, 'job_id': remote_id, 'name': profile['name'], 'workspace': profile['workspace']}
        parent = (job.get('execution_parent_id') or
                  (job.get('graph') or {}).get('runtime', {}).get('execution_parent_id') or
                  self.state['jobs'].get(local_id, {}).get('summary', {}).get('execution_parent_id'))
        if parent:
            # Reconnect bootstrap commonly contains only history summaries.
            # Preserve lineage learned from a previous detailed job response.
            job['execution_parent_id'] = parent
        job.update(id=local_id, remote=remote)
        self.state['jobs'][local_id] = {'profile_id': key, 'job_id': remote_id,
            'summary': {k:job[k] for k in ('id','name','status','created_at','finished_at','error','remote',
                                          'execution_parent_id') if k in job}}
        return job

    def owns(self, key):
        return key.startswith('ssh-')

    def reference(self, key):
        if key not in self.state['jobs']: raise KeyError('找不到远程运行记录，请连接服务器刷新。')
        return self.state['jobs'][key]

    def launch(self, graph):
        key = remote_profile(graph)
        graph = self.prepare(graph)
        payload = graph.model_dump(mode='json')
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        pending_key = key+':'+digest
        with self.lock:
            request_id = self.state['pending'].setdefault(pending_key, uuid.uuid4().hex)
            self.persist()
        job = self.call(key, 'run', {'graph': payload, 'request_id': request_id})
        with self.lock:
            result = self.wrap_job(key, job)
            self.state['pending'].pop(pending_key, None); self.persist()
        return result

    def job(self, key):
        ref = self.reference(key)
        result = self.wrap_job(ref['profile_id'], self.call(ref['profile_id'], 'job', {'job_id': ref['job_id']}))
        self.persist(); return result

    def fetch_output(self, profile, job_id, kind, **fields):
        """Resolve an authorized job output, then reuse the resumable transfer cache."""
        from .transfers import TransferClient
        from operon.remote.transfers import basename
        self.profile(profile)
        result = self.call(profile, 'output_file', {'job_id': job_id, 'kind': kind, **fields})
        name = basename(result['name'])
        if kind == 'figure' and fields.get('format') and Path(name).suffix.lower() != '.' + fields['format']:
            raise ValueError('服务器尚不支持打开此图表格式，请更新服务端后重试。')
        client = TransferClient(lambda method, params=None: self.call(profile, method, params),
                                self.service.directory / 'exchange' / profile)
        identity = hashlib.sha256(json.dumps([job_id, kind, fields], sort_keys=True).encode()).hexdigest()[:24]
        downloaded = client.download(result['path'], client.cache_dir / 'results' / identity / name)
        return Path(downloaded['path'])

    def preview(self, key, artifact_id, offset=0, limit=100):
        ref = self.reference(key)
        # Sampling happens on the server; opening a preview never downloads the array.
        return self.call(ref['profile_id'], 'preview', {'job_id': ref['job_id'], 'artifact_id': artifact_id,
                                                        'offset': offset, 'limit': limit})

    def ensure(self, key):
        """Idempotently restore an SSH connection; key/agent auth needs no secret."""
        profile = self.profile(key)
        state = next((item for item in self.status()
                      if (item.get('profile') or {}).get('id') == key), None)
        if state and state.get('connected'):
            return {'connected': True, 'profile_id': key, 'latency': None}
        if profile.get('auth', 'password') == 'password':
            raise ValueError('服务器需要密码认证，请调用 /api/remote/{key}/connect 提供本次会话密码')
        value = self.connect(key, {})
        return {'connected': True, 'profile_id': key, 'latency': value.get('latency') if isinstance(value, dict) else None}

    def artifact(self, key, artifact_id):
        match = next((a for a in (self.job(key).get('report') or {}).get('artifacts', [])
                      if a['artifact_id'] == artifact_id and a.get('disk_uri')), None)
        if not match:
            raise KeyError('产物尚未保存，或这次运行没有保留它。')
        return self._output(key, 'artifact', artifact_id=artifact_id), match

    def _output(self, key, kind, **fields):
        ref = self.reference(key)
        return self.fetch_output(ref['profile_id'], ref['job_id'], kind, **fields)

    def artifact_file(self, key, artifact_id, role):
        return self._output(key, 'artifact_file', artifact_id=artifact_id, role=role)

    def export_file(self, key, index):
        return self._output(key, 'export', index=index)

    def figure_file(self, key, index, format=None, figure_id=None):
        return self._output(key, 'figure', index=index, **({'format': format} if format else {}), **({'figure_id': figure_id} if figure_id is not None else {}))

    def cancel(self, key):
        ref = self.reference(key)
        result = self.wrap_job(ref['profile_id'], self.call(ref['profile_id'], 'cancel', {'job_id': ref['job_id']}))
        self.persist(); return result

    def poll(self, key, offsets):
        ref = self.reference(key)
        result = self.call(ref['profile_id'], 'poll', {'job_id': ref['job_id'], 'offsets': offsets})
        result['job'] = self.wrap_job(ref['profile_id'], result['job'])
        self.persist(); return result

    def history(self):
        return [item['summary'] for item in self.state['jobs'].values()]
