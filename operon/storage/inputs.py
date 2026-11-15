"""Resolve saved storage selections into one host's existing input path policy.

These bindings perform metadata checks only. They neither copy payloads nor
grant new absolute-path access. The execution host must already allow the
resolved path through its ordinary input roots.
"""
from __future__ import annotations

from pathlib import Path
import os
import stat

from operon.contracts.storage import StorageInputRef
from .configuration import PROFILE_OWNER
from .mounts import LocalStorage, SFTPStorage
from .references import StorageError
from .service import _check_cancel


def _failure(message, code='storage_binding_unavailable', **details):
    return StorageError(message, code=code, details=details)


def _target(value):
    value = value or {}
    if value.get('kind', 'local') == 'local':
        return {'kind': 'local'}
    if value.get('kind') == 'ssh' and isinstance(value.get('profile_id'), str) and value['profile_id']:
        return {'kind': 'ssh', 'profile_id': value['profile_id']}
    raise _failure('Choose an explicit local or SSH execution target')


def selected_target(graph):
    config = graph.runtime.get('execution') or {}
    if config.get('mode') == 'auto':
        raise _failure('Configured storage inputs require an explicit single-host execution target',
                       'storage_route_unavailable')
    default = _target(config.get('target') or config)
    values = [_target((config.get('node_targets') or {}).get(node.id) or default)
              for node in graph.nodes if node.kind != 'source'] or [default]
    if any(value != values[0] for value in values):
        raise _failure('Storage input transfers across execution hosts are not configured', 'storage_route_unavailable')
    return values[0]


def source_nodes(graph):
    for node in graph.nodes:
        if node.source is not None and node.source.storage_ref is not None:
            yield node.id, node
    # Embedded route sources are interface placeholders. Their values are
    # replaced by outer edges during route expansion, never separate reads.


def resolve_input(storage, value, *, principal, execution_target, remote_profile=None, cancel=None):
    ref = StorageInputRef.model_validate(value)
    mount = storage.mounts.resolve(ref.storage_id, principal)
    target = _target(execution_target)
    if ref.digest is not None:
        raise _failure('This input selection requires content-digest verification unavailable in metadata binding',
                       'storage_digest_unverified')
    if isinstance(mount.backend, LocalStorage):
        location = {'kind': 'local'}
    elif isinstance(mount.backend, SFTPStorage):
        key = mount.execution_profile_id
        if not key or mount.endpoint is None or remote_profile is None:
            raise _failure('This storage-only SSH mount has no explicit compute profile mapping',
                           'storage_route_unavailable', storage_id=ref.storage_id)
        location = {'kind': 'ssh', 'profile_id': key}
        try:
            configured = remote_profile(key)
        except (KeyError, ValueError):
            raise _failure('Mapped compute profile is unavailable', 'storage_route_unavailable') from None
        actual = (str(configured.get('host', '')).casefold(), configured.get('port', 22), configured.get('username'))
        expected = (mount.endpoint[0].casefold(), mount.endpoint[1], mount.endpoint[2])
        if actual != expected:
            raise _failure('Mapped compute profile does not match the storage host, port and account',
                           'storage_route_unavailable', storage_id=ref.storage_id)
    else:
        raise _failure('Storage backend has no supported execution visibility binding')
    if location != target:
        raise _failure('Selected storage is not visible on the chosen execution host; no transfer was started',
                       'storage_route_unavailable', storage_id=ref.storage_id)
    with storage._io(principal):
        _check_cancel(cancel)
        session = mount.backend.open()
        try:
            before = session.stat(ref.storage_id, ref.relative_path)
            if not before.accessible or before.kind != 'file':
                raise _failure('A storage input must be an accessible regular file', 'storage_not_file')
            if before.ref.version != ref.version:
                raise _failure('Selected storage file changed; select the current version explicitly', 'storage_changed')
            path = session._resolve(ref.relative_path)
            after = session.stat(ref.storage_id, ref.relative_path)
            if (after.ref.version != ref.version or session._resolve(ref.relative_path) != path
                    or storage.mounts.resolve(ref.storage_id, principal) is not mount):
                raise _failure('Storage input changed while binding it', 'storage_changed')
            _check_cancel(cancel)
            return {'reference': ref.model_dump(mode='json'), 'path': str(path), 'location': location,
                    'check': {'kind': 'local-version', 'version': ref.version} if location['kind'] == 'local'
                    else {'kind': 'sftp-metadata', 'size_bytes': after.size_bytes,
                          'modified_ns': after.modified_ns}}
        finally:
            session.close()


def verify_execution_inputs(manifest, *, root=None):
    """Recheck a bounded submitted binding at every worker start, before reads.

    SFTP v3 exposes second-resolution metadata; this preserves that explicit
    version strength. It is not a content digest or a snapshot of an open file.
    This record grants no path permission: submission validates input roots.
    """
    audit = (manifest.get('runtime') or {}).get('storage_input_bindings')
    if audit is None:
        return
    if (not isinstance(audit, dict) or audit.get('format') != 'operon.storage-input-bindings'
            or type(audit.get('schema_version')) is not int or audit['schema_version'] != 1
            or not isinstance(audit.get('inputs'), dict) or len(audit['inputs']) > 128):
        raise _failure('Invalid storage input execution record', 'storage_binding_invalid')
    from operon.bytecode import io_path
    from .mounts import _signature
    def path_key(value):
        path = os.path.abspath(os.path.join(root or os.curdir, value))
        if os.name == 'nt':
            if path.startswith('\\\\?\\UNC\\'):
                path = '\\\\' + path[8:]
            elif path.startswith('\\\\?\\'):
                path = path[4:]
        return os.path.normcase(path)
    source_paths = {path_key(item['path']) for item in manifest.get('sources', {}).values()}
    for item in audit['inputs'].values():
        ref = StorageInputRef.model_validate(item['reference'])
        path, check = item['path'], item['check']
        if path_key(path) not in source_paths:
            raise _failure('Storage input execution path differs from its source', 'storage_binding_invalid')
        try:
            attrs = os.stat(io_path(path))
        except OSError as exc:
            raise _failure('Selected storage input is no longer accessible', 'storage_changed') from exc
        unchanged = stat.S_ISREG(attrs.st_mode)
        if check.get('kind') == 'local-version':
            unchanged = unchanged and _signature(attrs) == ref.version == check.get('version')
        elif check.get('kind') == 'sftp-metadata':
            unchanged = (unchanged and attrs.st_size == check.get('size_bytes')
                         and int(attrs.st_mtime) * 1_000_000_000 == check.get('modified_ns'))
        else:
            raise _failure('Unknown storage input execution check', 'storage_binding_invalid')
        if not unchanged:
            raise _failure('Selected storage file changed before execution; select it again', 'storage_changed')


def prepare_plan_inputs(plan, manifest, storage_bindings):
    """Bind frozen local RunPlan selections through existing confined roots."""
    refs = plan.execution_policy.get('storage_input_refs') or ()
    if not refs:
        return
    if len(refs) > 128:
        raise _failure('Too many selected storage inputs', 'storage_limit')
    from operon.environment_store.verification import confined
    sources = {item.get('path') for item in manifest.get('sources', {}).values()}
    records = {}
    for index, value in enumerate(refs):
        ref = StorageInputRef.model_validate(value)
        if ref.digest is not None:
            raise _failure('Content-digest verification is unavailable in metadata binding', 'storage_digest_unverified')
        root = storage_bindings.get(ref.storage_id)
        if root is None:
            raise _failure('RunPlan lacks the selected storage mount binding', 'missing_binding')
        path = str(confined(root, ref.relative_path))
        if path in sources:
            records[str(index)] = {'reference': ref.model_dump(mode='json'), 'path': path,
                                  'check': {'kind': 'local-version', 'version': ref.version}}
    if records:
        manifest.setdefault('runtime', {})['storage_input_bindings'] = {
            'format': 'operon.storage-input-bindings', 'schema_version': 1, 'inputs': records}
        verify_execution_inputs(manifest)


class StorageInputBindings:
    def __init__(self, application):
        self.app = application

    def authorize(self, graph):
        nodes = list(source_nodes(graph))
        if len(nodes) > 128:
            raise _failure('A workflow may select at most 128 storage inputs', 'storage_limit')
        for _, node in nodes:
            self.app.storage.mounts.resolve(node.source.storage_ref.storage_id, PROFILE_OWNER)
        return bool(nodes)

    def bind(self, graph):
        """Return an execution-only copy; never rewrite saved refs or versions."""
        if not self.authorize(graph):
            return graph
        target = selected_target(graph)
        result = graph.model_copy(deep=True)
        service = self.app.service
        records = {}
        for name, node in source_nodes(result):
            bound = resolve_input(self.app.storage, node.source.storage_ref, principal=PROFILE_OWNER,
                execution_target=target, remote_profile=service.remotes.profile if service.remotes else None)
            if target['kind'] == 'local':
                from operon.planning.graph_compiler import input_path
                # A browse grant does not silently widen legacy execution roots.
                input_path(service.root, bound['path'], '.', service.settings.input_roots)
            node.source.storage_ref = None
            node.source.path = bound['path']
            node.source.location = None if target['kind'] == 'local' else bound['location']
            records[name] = bound
        result.runtime['storage_input_bindings'] = {
            'format': 'operon.storage-input-bindings', 'schema_version': 1, 'inputs': records}
        return result

    def validate_plan(self, plan, binding):
        refs = plan.execution_policy.get('storage_input_refs') or ()
        if not refs:
            return
        if len(refs) > 128 or any(unit.placement.executor != 'local' for unit in plan.units):
            raise _failure('Storage-backed RunPlans require an explicitly bound local execution host',
                           'storage_route_unavailable')
        from operon.environment_store.verification import confined
        for value in refs:
            ref = StorageInputRef.model_validate(value)
            resolved = resolve_input(self.app.storage, ref, principal=PROFILE_OWNER,
                                     execution_target={'kind': 'local'})
            root = binding.storage.get(ref.storage_id)
            if root is None:
                raise _failure('RunPlan lacks the selected storage mount binding', 'missing_binding')
            supplied = confined(confined(self.app.service.root, root), ref.relative_path)
            if supplied != Path(resolved['path']):
                raise _failure('RunPlan storage binding differs from the authorized selected file',
                               'storage_path_forbidden')


__all__ = ['StorageInputBindings', 'resolve_input', 'selected_target']
