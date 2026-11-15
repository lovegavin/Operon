"""Explicit configured controller lifecycle; never started by status/import.

Deployments supply verified, immutable preparation files for exact ready-unit
specifications. This is an operational bridge, not an environment installer,
data mover, public API server, or an additional physical-resource allocator.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import signal
import threading
import time
from typing import Literal
import uuid

from pydantic import Field, model_validator

from operon.contracts.base import ContractModel, canonical_json, sha256_hex
from operon.contracts.run_plan import TargetSpec
from operon.execution.unit_executor import unit_dependencies
from operon.engine.contracts import BusyError
from operon.remote.client import SSHConnection, HostKeyRequired
from .executors.ssh_pool import SSHPoolExecutor, CAPABILITY
from .executors.slurm import SlurmExecutor, SSHCommandTransport, SlurmResources, allocation_script, _absolute
from .placement import PlacementPlanner, PreparedBinding
from .postgres import Leadership
from .receipts import ClusterError, LeadershipLost
from .repository import ClusterRepository
from .scheduler import ClusterController
from .invocation import ConsumerTemplate, InvocationTemplate, CAPABILITY as INVOCATION_CAPABILITY, CONSUMER_CAPABILITY


class HostKey(ContractModel):
    type: str = Field(min_length=1, max_length=80)
    base64: str = Field(min_length=1, max_length=8192)


class SSHSettings(ContractModel):
    host: str = Field(min_length=1, max_length=253)
    port: int = Field(default=22, ge=1, le=65535)
    username: str = Field(min_length=1, max_length=128)
    auth: Literal['agent', 'key', 'password'] = 'agent'
    host_key: HostKey
    key_path: str | None = Field(default=None, max_length=2048)
    password_environment: str | None = Field(default=None, pattern=r'^[A-Za-z_][A-Za-z0-9_]*$')
    passphrase_environment: str | None = Field(default=None, pattern=r'^[A-Za-z_][A-Za-z0-9_]*$')
    python: str = Field(default='python3', min_length=1, max_length=2048)
    app_dir: str = Field(min_length=1, max_length=2048)
    workspace: str = Field(min_length=1, max_length=2048)

    @model_validator(mode='after')
    def _authentication(self):
        if self.auth == 'key' and not self.key_path:
            raise ValueError('Key authentication requires an explicit key path')
        if self.auth == 'password' and not self.password_environment:
            raise ValueError('Password authentication requires a secret environment provider')
        return self


class NodeSettings(ContractModel):
    node_id: str = Field(min_length=1, max_length=128)
    capacity_domain: str = Field(min_length=1, max_length=200)
    executor: Literal['ssh', 'slurm']
    ssh: SSHSettings
    target: TargetSpec
    host_identity: str | None = Field(default=None, max_length=200)
    # Explicit, operator-verified deployment inventory; unknown costs stay null.
    environments: tuple[str, ...] = ()
    reachable_storage: tuple[str, ...] = ()
    devices: tuple[str, ...] = ()

    @model_validator(mode='after')
    def _host_identity(self):
        if self.executor == 'ssh' and not self.host_identity:
            raise ValueError('SSH pool requires its expected durable host identity')
        return self


class PreparedSettings(ContractModel):
    run_id: str | None = Field(default=None, min_length=1, max_length=200)
    plan_id: str | None = Field(default=None, min_length=1, max_length=64)
    unit_id: str = Field(min_length=1, max_length=200)
    node_id: str = Field(min_length=1, max_length=128)
    spec_digest: str = Field(pattern=r'^[0-9a-f]{64}$')
    payload_file: str = Field(min_length=1, max_length=2048)
    payload_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    binding_id: str | None = Field(default=None, max_length=200)

    @model_validator(mode='after')
    def _identity(self):
        if (self.run_id is None) == (self.plan_id is None):
            raise ValueError('Preparation requires exactly one source plan_id or admitted run_id')
        return self


class ControllerSettings(ContractModel):
    format: Literal['operon.cluster-controller'] = 'operon.cluster-controller'
    schema_version: Literal[1] = 1
    dsn_environment: str = Field(default='OPERON_CLUSTER_DSN', pattern=r'^[A-Za-z_][A-Za-z0-9_]*$')
    schema_name: str = Field(default='public', pattern=r'^[a-z_][a-z0-9_]{0,62}$')
    principal: str = Field(min_length=1, max_length=128)
    cluster_id: str = Field(min_length=1, max_length=128)
    controller_id: str = Field(min_length=1, max_length=128)
    nodes: tuple[NodeSettings, ...] = Field(min_length=1, max_length=256)
    prepared: tuple[PreparedSettings, ...] = Field(default=(), max_length=1024)
    tick_seconds: float = Field(default=1.0, gt=0, le=10)
    heartbeat_seconds: float = Field(default=10.0, ge=5, le=20)

    @model_validator(mode='after')
    def _unique(self):
        names = [node.node_id for node in self.nodes]
        domains = [node.capacity_domain for node in self.nodes]
        if len(set(names)) != len(names) or len(set(domains)) != len(domains):
            raise ValueError('Node IDs and physical capacity domains must be unique')
        keys = [(item.run_id, item.plan_id, item.unit_id, item.node_id) for item in self.prepared]
        if len(set(keys)) != len(keys) or any(item.node_id not in names for item in self.prepared):
            raise ValueError('Prepared bindings must name configured nodes without duplicate keys')
        return self


class TransportLeases:
    """One authenticated connection per bounded I/O operation, never shared RPCs."""
    def __init__(self, nodes):
        self.nodes = {node.node_id: node for node in nodes}
        self.lock, self.closed, self.connections = threading.RLock(), False, set()

    @staticmethod
    def _secrets(settings):
        values = {}
        for key, name in (('password', settings.password_environment), ('passphrase', settings.passphrase_environment)):
            if name:
                if not os.environ.get(name):
                    raise ClusterError('Configured SSH secret provider is unavailable', code='secret_unavailable')
                values[key] = os.environ[name]
        return values

    @contextmanager
    def lease(self, node_id, lane):
        if lane not in ('control', 'lifecycle'):
            raise ValueError('Unknown transport lane')
        node = self.nodes[node_id]
        with self.lock:
            if self.closed:
                raise ClusterError('Controller transports are stopping')
        settings, connection = node.ssh, None
        secrets = self._secrets(settings)
        profile = settings.model_dump(mode='json')
        profile.pop('password_environment', None)
        profile.pop('passphrase_environment', None)
        try:
            if node.executor == 'ssh':
                connection = SSHConnection(profile, secrets, install=False)
            else:
                import paramiko
                connection = paramiko.SSHClient()
                trusted = settings.host_key
                class Trust(paramiko.MissingHostKeyPolicy):
                    def missing_host_key(self, client, hostname, key):
                        if trusted.type != key.get_name() or trusted.base64 != key.get_base64():
                            raise HostKeyRequired(key, changed=True)
                connection.set_missing_host_key_policy(Trust())
                connection.connect(settings.host, port=settings.port, username=settings.username,
                    password=secrets.get('password'), passphrase=secrets.get('passphrase'),
                    key_filename=settings.key_path, allow_agent=settings.auth == 'agent',
                    look_for_keys=settings.auth == 'agent', timeout=10, auth_timeout=20, banner_timeout=20)
                connection.get_transport().set_keepalive(10)
            with self.lock:
                if self.closed:
                    raise ClusterError('Controller stopped while connecting')
                self.connections.add(connection)
            yield connection
        finally:
            if connection is not None:
                with self.lock:
                    self.connections.discard(connection)
                connection.close()

    def close(self):
        with self.lock:
            self.closed = True
            active = tuple(self.connections)
        for connection in active:
            try:
                connection.close()
            except Exception:
                pass


class ConfiguredPlanner:
    def __init__(self, settings, *, directory):
        self.settings = settings
        self.prepared, self.templates, self.specs, self.sources = {}, {}, {}, {}
        self.consumer_nodes = set()
        self.nodes = {node.node_id: node for node in settings.nodes}
        for item in settings.prepared:
            path = Path(item.payload_file)
            path = path if path.is_absolute() else Path(directory) / path
            with path.open('rb') as stream:
                raw = stream.read(8 * 1024 * 1024 + 1)
            if len(raw) > 8 * 1024 * 1024 or hashlib.sha256(raw).hexdigest() != item.payload_sha256:
                raise ValueError('Prepared payload exceeds the bound or its immutable checksum changed')
            payload = json.loads(raw.decode('utf-8'))
            if not isinstance(payload, dict):
                raise ValueError('Prepared payload must be an object')
            node = self.nodes[item.node_id]
            if node.executor == 'ssh':
                template = InvocationTemplate.model_validate(payload)
                if template.workspace != node.ssh.workspace or template.source_unit_id != item.unit_id:
                    raise ValueError('Invocation template must name its configured workspace and unit')
                if item.plan_id is not None and template.source_plan.plan_id != item.plan_id:
                    raise ValueError('Template source plan differs from its preparation key')
                source = next((unit for unit in template.source_plan.units if unit.unit_id == item.unit_id), None)
                if source is None or sha256_hex(source) != item.spec_digest:
                    raise ValueError('Template source unit differs from its frozen specification checksum')
                if unit_dependencies(template.source_plan)[item.unit_id]:
                    prepared = ConsumerTemplate(**template.model_dump(mode='json', exclude={'format'}),
                        target_node_id=item.node_id, target_host_identity=node.host_identity)
                    self.consumer_nodes.add(item.node_id)
                else:
                    prepared = template.project()
                payload = prepared.model_dump(mode='json')
            else:
                if item.plan_id is not None:
                    raise ValueError('Pre-admission plan templates currently require the typed SSH invocation adapter')
                resources = SlurmResources(**payload['resources'])
                for field in ('script_path', 'stdout_path', 'stderr_path'):
                    _absolute(payload[field])
                for field in ('script_sha256', 'invocation_sha256'):
                    checksum = payload.get(field, '')
                    if not isinstance(checksum, str) or len(checksum) != 64 or any(c not in '0123456789abcdef' for c in checksum):
                        raise ValueError('Slurm requires immutable staged script and invocation checksums')
                expected_script = allocation_script(python=payload['python'], invocation_path=payload['invocation_path'],
                    memory_bytes=resources.memory_bytes, cpu_threads=resources.cpu_threads)
                if hashlib.sha256(expected_script.encode()).hexdigest() != payload['script_sha256']:
                    raise ValueError('Slurm script must invoke the existing worker inside its allocation')
            scope, identifier = ('plan', item.plan_id) if item.plan_id else ('run', item.run_id)
            key = (identifier, item.unit_id, item.node_id)
            (self.templates if scope == 'plan' else self.prepared)[key] = PreparedBinding(canonical_json(payload), item.binding_id)
            self.specs[(scope, *key)] = item.spec_digest
            if node.executor == 'ssh':
                self.sources[(scope, *key)] = (template.source_plan.plan_id, source.model_dump(mode='json'))
        self.planner = PlacementPlanner(controller_id=settings.controller_id, prepared={}, prepared_templates={})

    def validate(self, repository):
        for identity, expected in self.specs.items():
            scope, run_or_plan, unit_id, node_id = identity
            key = (run_or_plan, unit_id, node_id)
            if scope == 'run':
                spec = repository.unit_spec(self.settings.principal, run_or_plan, unit_id)
                source = self.sources.get(identity)
                if source and repository.status(self.settings.principal, run_or_plan)['plan_id'] != source[0]:
                    raise ClusterError('Prepared invocation belongs to another source RunPlan', code='artifact_mismatch')
            else:
                spec = self.sources[identity][1]
            if sha256_hex(spec) != expected:
                raise ClusterError('Prepared payload names another frozen execution unit', code='artifact_mismatch')
            if spec['placement']['executor'] != self.nodes[node_id].executor:
                raise ValueError('Prepared executor differs from the frozen unit')
            prepared = (self.templates if scope == 'plan' else self.prepared)[key]
            if spec['invocation'].get('environment_ref') and not prepared.binding_id:
                raise ValueError('A frozen environment requirement needs a committed binding ID')
        # Unit spec is immutable after admission. Startup validation and payload
        # hashing happen outside the 50ms scheduling path.
        self.planner.prepared = self.prepared
        self.planner.prepared_templates = self.templates

    def __call__(self, ready, nodes):
        allowed = [row for row in ready if row['principal'] == self.settings.principal]
        return self.planner(allowed, [node for node in nodes if node['node_id'] in self.nodes])


def serve(settings, database, *, directory, stop_event=None):
    """Own one controller until signal/explicit stop; return only after cleanup."""
    stop = stop_event or threading.Event()
    repository = ClusterRepository(database)
    leadership = Leadership(database, cluster_id=settings.cluster_id, owner_id=uuid.uuid4().hex)
    transports = TransportLeases(settings.nodes)
    command = SSHCommandTransport(transports.lease)
    slurm = SlurmExecutor(command)
    expected = {node.node_id: node.host_identity for node in settings.nodes}
    executors = {'ssh': SSHPoolExecutor(transports.lease, controller_epoch=lambda: leadership.epoch,
                                       expected_host_identity=expected.__getitem__), 'slurm': slurm}
    planner = ConfiguredPlanner(settings, directory=directory)
    controller = ClusterController(repository, leadership, executors=executors, planner=planner,
                                   tick_seconds=settings.tick_seconds)
    handlers, future, next_probe, cursor = {}, None, 0.0, 0

    def probe(node):
        leadership.assert_current(dispatch=False)
        observed_epoch = None
        if node.executor == 'ssh':
            with transports.lease(node.node_id, 'lifecycle') as connection:
                if not connection.supports(CAPABILITY) or not connection.supports(INVOCATION_CAPABILITY):
                    raise ClusterError('Host does not advertise configured fenced control', code='capability_unavailable')
                if node.node_id in planner.consumer_nodes and not connection.supports(CONSUMER_CAPABILITY):
                    raise ClusterError('Host lacks verified same-host artifact preparation', code='capability_unavailable')
                value = connection.call('cluster.lookup', {'controller_id': settings.controller_id,
                    'controller_epoch': leadership.epoch, 'request_key': 'controller-probe-' + leadership.owner_id,
                    'command_id': 'controller-probe', 'cluster_run_id': 'controller-probe',
                    'cluster_unit_id': 'controller-probe', 'cluster_attempt_id': 'controller-probe',
                    'workspace': node.ssh.workspace, 'principal': settings.principal})
                observed = value.get('target', {})
                if (value.get('host_identity') != node.host_identity or value.get('capacity_domain') != node.capacity_domain
                        or any(observed.get(key) != getattr(node.target, key) for key in ('os', 'arch'))
                        or (node.target.python_abi and observed.get('python_abi') != node.target.python_abi)):
                    raise ClusterError('Configured host identity, capacity or target differs from observation', code='receipt_identity_mismatch')
                observed_epoch = value.get('host_pool_epoch')
                if type(observed_epoch) is not int or observed_epoch < 1:
                    raise ClusterError('Host pool has no durable owner epoch', code='receipt_identity_mismatch')
        else:
            slurm.probe(node.node_id)
        return observed_epoch

    def prepare():
        planner.validate(repository)
        for node in settings.nodes:
            leadership.assert_current(dispatch=False)
            repository.register_node(node_id=node.node_id, capacity_domain=node.capacity_domain, executor=node.executor,
                inventory={**node.target.model_dump(mode='json'), 'environments': list(node.environments),
                           'reachable_storage': list(node.reachable_storage), 'devices': list(node.devices)})
            try:
                epoch = probe(node)
                for key, prepared in planner.prepared.items():
                    if key[2] == node.node_id and node.executor == 'slurm':
                        payload = json.loads(prepared.payload_json)
                        for path_field, hash_field in (('script_path', 'script_sha256'), ('invocation_path', 'invocation_sha256')):
                            result = command.run(node.node_id, ['sha256sum', '--', payload[path_field]])
                            fields = result.stdout.split(maxsplit=1)
                            if result.returncode or not fields or fields[0] != payload[hash_field]:
                                raise ClusterError('Staged Slurm input is missing or changed', code='artifact_mismatch')
                repository.heartbeat(node.node_id, observed_pool_epoch=epoch)
            except Exception:
                repository.heartbeat(node.node_id, observed_pool_epoch=None, health='offline')
                raise

    try:
        if threading.current_thread() is threading.main_thread():
            for signum in (signal.SIGINT, signal.SIGTERM):
                handlers[signum] = signal.getsignal(signum)
                signal.signal(signum, lambda *_: stop.set())
        controller.start(prepare=prepare)
        while not stop.wait(.2):
            if controller._thread is None or not controller._thread.is_alive():
                raise controller.last_error or LeadershipLost('Controller scheduling thread stopped')
            if future is not None and future[1].done():
                node, pending = future
                try:
                    observed_epoch = pending.result()
                    repository.heartbeat(node.node_id, observed_pool_epoch=observed_epoch)
                except Exception:
                    repository.heartbeat(node.node_id, observed_pool_epoch=None, health='offline')
                future = None
            if future is None and time.monotonic() >= next_probe:
                node = settings.nodes[cursor % len(settings.nodes)]
                try:
                    pending = controller.io.submit('poll', probe, node)
                except BusyError:
                    continue
                future = (node, pending)
                cursor += 1
                next_probe = time.monotonic() + settings.heartbeat_seconds / len(settings.nodes)
        return {'state': 'stopped', 'controller_id': settings.controller_id, 'epoch': leadership.epoch}
    finally:
        controller.request_stop()
        try:
            transports.close()
        finally:
            try:
                controller.stop()
            finally:
                for signum, handler in handlers.items():
                    signal.signal(signum, handler)


__all__ = ['ControllerSettings', 'serve']
