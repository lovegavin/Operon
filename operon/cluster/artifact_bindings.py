"""Authenticated committed outputs visible in one host workspace.

This is a visibility resolver, not a copier or a cross-host transport. The
caller supplies an authenticated principal/controller and a trusted process-tree
verifier. Paths and content records come only from this host's durable producer.
Consumers must resolve again before use: a reference pins lifetime, not bytes
against an external writer. Uncertain failures retain the pin for inspection.
"""
from __future__ import annotations

import json
import ntpath
import os
from pathlib import Path
import stat
from typing import Literal

from pydantic import Field, model_validator

from operon.bytecode import io_path
from operon.contracts.base import ContractModel, ContractError, canonical_json, sha256_hex
from operon.contracts.plan_operations import BoundInput, binding_path
from operon.engine.artifacts import ArtifactCommitter
from operon.engine.contracts import EngineError, UnauthorizedError, digest
from operon.execution.codecs import validate_reference


MAX_METADATA_BYTES = 1024 * 1024
MAX_ARTIFACT_FILES = 4096


class ProducerArtifactRequest(ContractModel):
    controller_epoch: int = Field(ge=1)
    request_key: str = Field(min_length=1, max_length=512)
    command_id: str = Field(min_length=1, max_length=200)
    cluster_run_id: str = Field(min_length=1, max_length=200)
    cluster_unit_id: str = Field(min_length=1, max_length=200)
    cluster_attempt_id: str = Field(min_length=1, max_length=200)
    host_run_id: str = Field(min_length=1, max_length=200)
    host_unit_id: str = Field(min_length=1, max_length=512)
    host_attempt_id: str = Field(min_length=1, max_length=200)
    host_fence: int = Field(ge=0)
    artifact_id: str = Field(min_length=1, max_length=200)
    artifact_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    output_port: str = Field(min_length=1, max_length=200)
    binding_key: str = Field(min_length=1, max_length=512)


class SharedArtifactReceipt(ContractModel):
    format: Literal['operon.shared-artifact-receipt'] = 'operon.shared-artifact-receipt'
    schema_version: Literal[1] = 1
    receipt_id: str
    controller_id: str
    principal: str
    host_identity: str
    workspace_id: str
    source_plan_id: str
    source_unit_digest: str
    producer: ProducerArtifactRequest
    reference_id: str
    lease_id: str
    evidence_revision: str
    publication_digest: str
    files_verified: int
    input: BoundInput
    mode: Literal['same-host-visibility'] = 'same-host-visibility'

    @model_validator(mode='after')
    def _identity(self):
        value = self.model_dump(mode='json')
        _bounded(value)
        identity = {key: item for key, item in value.items()
                    if key not in ('format', 'schema_version', 'receipt_id', 'mode')}
        if sha256_hex(identity) != self.receipt_id:
            raise _error('Shared artifact receipt identity differs from its content')
        return self


def _error(message, code='artifact_mismatch', **details):
    return ContractError(message, code=code, details=details)


def _stamp(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


def _opened_matches(path_info, handle_info):
    """Compare a path and descriptor without mixing Win32 ctime semantics.

    Some CPython Windows builds expose creation time through stat().st_ctime
    and change time through fstat().st_ctime. Both supply the same birth time.
    File identity, mode, size, mtime and birth time must match across the open;
    callers also compare each full stamp within its own path/descriptor view,
    so an actual descriptor change-time mutation is still rejected.
    """
    if os.name == 'nt' and hasattr(path_info, 'st_birthtime_ns') and hasattr(handle_info, 'st_birthtime_ns'):
        return (_stamp(path_info)[:-1], path_info.st_birthtime_ns) == (
            _stamp(handle_info)[:-1], handle_info.st_birthtime_ns)
    return _stamp(path_info) == _stamp(handle_info)


def _bounded(value):
    if len(canonical_json(value).encode('utf-8')) > MAX_METADATA_BYTES:
        raise _error('Artifact metadata exceeds the bounded resolver allowance', 'artifact_metadata_limit')
    return value


def _logical_path(value):
    """Remove only equivalent Win32 extended-path spelling, without resolving links.

    Device namespaces and verbatim-only trailing-dot/space components are not
    aliases of ordinary workspace paths and must not be normalized into one.
    """
    text = os.fspath(value)
    if os.name == 'nt':
        text = text.replace('/', '\\')
        if text.startswith('\\\\?\\'):
            suffix = text[4:]
            text = '\\\\' + suffix[4:] if suffix.upper().startswith('UNC\\') else suffix
            drive, tail = ntpath.splitdrive(text)
            disk = len(drive) == 2 and drive[0].isalpha() and drive[1] == ':' and tail.startswith('\\')
            network = drive.startswith('\\\\') and len(drive[2:].split('\\')) == 2 and all(drive[2:].split('\\'))
            if not disk and not network:
                raise _error('Unsupported Windows device path', 'path_escape')
        if text.startswith(('\\\\.\\', '\\\\?\\')):
            raise _error('Windows device namespaces are not workspace paths', 'path_escape')
        drive, tail = ntpath.splitdrive(text)
        parts = (drive[2:].split('\\') if drive.startswith('\\\\') else []) + tail.split('\\')
        if any(part.endswith(('.', ' ')) or ':' in part for part in parts if part):
            raise _error('Verbatim-only Windows names are not portable workspace aliases', 'path_escape')
    return Path(text)


def _same_path(left, right):
    return (isinstance(left, (str, os.PathLike)) and isinstance(right, (str, os.PathLike))
            and _logical_path(left) == _logical_path(right))


class CommittedArtifactResolver:
    """No I/O is done inside a StateStore writer transaction.

    verify_stopped(run, unit, attempt, lease) must be trusted host code checking
    owned launch/tree-exit evidence, not a boolean supplied in the wire request.
    A released lease and terminal succeeded attempt are checked independently.
    """

    def __init__(self, store, *, invocation_root, workspace_root, workspace_id,
                 host_identity, authenticated_controller_id, verify_stopped):
        if not callable(verify_stopped) or not authenticated_controller_id:
            raise ValueError('An authenticated controller and process-tree verifier are required')
        self.store = store
        self.root = _logical_path(Path(invocation_root).resolve())
        self.workspace = _logical_path(Path(workspace_root).resolve())
        if not self.root.is_relative_to(self.workspace):
            raise ValueError('Invocation evidence must remain in its registered workspace')
        self.workspace_id, self.host_identity = workspace_id, host_identity
        self.controller_id, self.verify_stopped = authenticated_controller_id, verify_stopped
        self.committer = ArtifactCommitter(self.root, store)

    def _safe(self, path, *, root=None):
        root = _logical_path(root or self.workspace)
        path = _logical_path(path)
        try:
            relative = path.relative_to(root)
        except ValueError as exc:
            raise _error('Published artifact escapes its authorized root', 'path_escape') from exc
        current = root
        for part in ('.', *relative.parts):
            current = current if part == '.' else current / part
            info = io_path(current).lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise _error('Published artifact contains a link or reparse point', 'path_escape')
        if not _logical_path(io_path(path).resolve(strict=True)).is_relative_to(root):
            raise _error('Published artifact changed its confinement boundary', 'path_escape')
        return path

    def _json(self, path):
        path = self._safe(path)
        before_info = io_path(path).stat()
        before = _stamp(before_info)
        with io_path(path).open('rb') as stream:
            opened = os.fstat(stream.fileno())
            if not _opened_matches(before_info, opened):
                raise _error('Publication changed while opening metadata')
            raw = stream.read(MAX_METADATA_BYTES + 1)
            if len(raw) > MAX_METADATA_BYTES:
                raise _error('Artifact metadata exceeds the bounded resolver allowance', 'artifact_metadata_limit')
            after = _stamp(os.fstat(stream.fileno()))
        if _stamp(opened) != after or before != _stamp(io_path(self._safe(path)).stat()):
            raise _error('Publication changed while reading metadata')
        def unique(items):
            value = {}
            for key, item in items:
                if key in value:
                    raise _error('Duplicate publication metadata field')
                value[key] = item
            return value
        return json.loads(raw.decode('utf-8'), object_pairs_hook=unique), before

    def _authority(self, request, principal):
        record = self.store.cluster_request(controller_id=self.controller_id,
            epoch=request.controller_epoch, principal=principal, request_key=request.request_key)
        if not record or record['state'] == 'rejected' or record['host_run_id'] != request.host_run_id:
            raise UnauthorizedError('Producer is not owned by this authenticated controller request')
        envelope = record['envelope']
        expected = {name: getattr(request, name) for name in
                    ('request_key', 'command_id', 'cluster_run_id', 'cluster_unit_id', 'cluster_attempt_id')}
        expected.update(workspace=str(self.workspace), principal=principal, submission_kind='plan')
        if (not _same_path(envelope.get('workspace'), self.workspace)
                or {**envelope, 'workspace': str(self.workspace)} != expected):
            raise UnauthorizedError('Producer controller envelope differs from its durable owner')
        workspace = self.store.workspace(self.workspace_id)
        run, unit = self.store.run(request.host_run_id), self.store.unit(request.host_unit_id)
        attempt, artifact = self.store.attempt(request.host_attempt_id), self.store.artifact(request.artifact_id)
        lease = self.store.lease(request.host_attempt_id)
        if (workspace['principal'] != principal or workspace['pool_id'] != self.host_identity
                or not _same_path(workspace['root'], self.workspace)
                or run['principal'] != principal or run['workspace_id'] != self.workspace_id
                or unit['run_id'] != run['id'] or unit['local_id'] != request.cluster_unit_id
                or attempt['unit_id'] != unit['id']):
            raise UnauthorizedError('Producer belongs to another principal, workspace or unit')
        if (attempt['state'] != 'succeeded' or unit['state'] != 'succeeded'
                or attempt['ordinal'] != unit['attempts'] or attempt['fence'] != request.host_fence
                or not lease or lease['state'] != 'released' or lease['pool_id'] != self.host_identity):
            raise _error('Producer attempt/fence or resource exit is not confirmed', 'producer_not_committed')
        receipt = attempt['receipt']
        identities = {'artifact_id': request.artifact_id, 'digest': request.artifact_digest,
                      'attempt_id': request.host_attempt_id, 'fence': request.host_fence,
                      'run_id': request.host_run_id, 'unit_id': request.host_unit_id, 'state': 'committed'}
        if any(receipt.get(key) != value for key, value in identities.items()):
            raise _error('Attempt receipt does not own the requested publication', 'producer_not_committed')
        if (not artifact or artifact['state'] != 'committed' or artifact['attempt_id'] != attempt['id']
                or artifact['fence'] != attempt['fence'] or artifact['digest'] != request.artifact_digest
                or not _same_path(artifact['location'], receipt.get('location'))):
            raise _error('Artifact registration differs from its producer', 'producer_not_committed')
        manifest = _bounded(artifact['manifest'])
        if manifest.get('kind') != 'invocation-output' or digest(manifest) != request.artifact_digest:
            raise _error('Committed artifact manifest identity differs')
        graph = run['plan'].get('graph', {})
        lineage = graph.get('execution_policy', {}).get('cluster_projection', {})
        if (graph.get('format') != 'operon.run-plan' or lineage.get('source_unit_id') != unit['local_id']
                or not lineage.get('source_plan_id') or not lineage.get('source_unit_digest')):
            raise _error('Producer lacks its frozen cluster projection lineage', 'unverified_artifact_provenance')
        fingerprint = sha256_hex({'envelope': envelope, 'run_id': run['id'], 'plan_id': graph['plan_id'],
            'unit_state': unit['state'], 'ordinal': unit['attempts'], 'attempt': attempt,
            'artifact': artifact, 'lease': {'id': lease['id'], 'state': lease['state'], 'revision': lease['revision']}})
        return run, unit, attempt, artifact, lease, lineage, fingerprint

    def _files(self, location, manifest):
        entries = manifest.get('files')
        if not isinstance(entries, list) or not 1 <= len(entries) <= MAX_ARTIFACT_FILES:
            raise _error('Committed artifact file count exceeds the resolver allowance', 'artifact_metadata_limit')
        expected, snapshots = {}, {}
        self._safe(location)
        for item in entries:
            name = binding_path(item['path'])
            if name != item['path'] or name in expected:
                raise _error('Committed artifact contains duplicate or non-normalized paths')
            path = self._safe(location / name, root=location)
            info = io_path(path).stat()
            if not stat.S_ISREG(info.st_mode):
                raise _error('Committed artifact contains a non-file payload')
            expected[name], snapshots[name] = item, _stamp(info)
        # Bound unexpected-file/directory enumeration before the existing full
        # verification, and reject links instead of silently skipping them.
        count, pending = 0, [location]
        while pending:
            directory = pending.pop()
            with os.scandir(io_path(directory)) as children:
                for child in children:
                    count += 1
                    if count > MAX_ARTIFACT_FILES * 2:
                        raise _error('Artifact directory enumeration exceeds its bound', 'artifact_metadata_limit')
                    path = self._safe(directory / child.name, root=location)
                    relative = path.relative_to(location).as_posix()
                    if child.is_dir(follow_symlinks=False):
                        pending.append(path)
                    elif not child.is_file(follow_symlinks=False) or relative not in expected:
                        raise _error('Uncommitted or non-file payload was added to the artifact')
        return expected, snapshots

    def resolve(self, value, *, principal):
        request = ProducerArtifactRequest.model_validate(value)
        pin = None
        try:
            with self.store.transaction():
                authority = self._authority(request, principal)
            run, unit, attempt, artifact, lease, lineage, fingerprint = authority
            if self.verify_stopped(run, unit, attempt, lease) is not True:
                raise _error('Owned producer process-tree exit is unconfirmed', 'producer_not_stopped')
            publication_path = self.root / 'runs' / run['id'] / 'published' / (binding_path(unit['local_id']) + '.json')
            publication, publication_stamp = self._json(publication_path)
            published_receipt = publication.get('receipt')
            if (not isinstance(published_receipt, dict) or not published_receipt
                    or any(attempt['receipt'].get(key) != value for key, value in published_receipt.items() if key != 'location')
                    or not _same_path(published_receipt.get('location'), attempt['receipt'].get('location'))
                    or any(published_receipt.get(key) != attempt['receipt'].get(key) for key in
                           ('artifact_id', 'digest', 'attempt_id', 'fence', 'run_id', 'unit_id', 'state'))):
                raise _error('Published output index differs from the committed attempt receipt')
            selected = publication.get('outputs', {}).get(request.output_port)
            if not isinstance(selected, dict):
                raise _error('Producer has no committed output with that name', 'artifact_port_not_found')
            location = self._safe(Path(artifact['location']))
            path = self._safe(Path(selected['path']), root=location)
            bound = BoundInput.model_validate({**selected, 'path': path.relative_to(self.workspace).as_posix()})
            # Recheck authority and pin in one short transaction; no filesystem
            # scanning or network call holds the StateStore writer.
            owner = 'materialization:' + sha256_hex({'controller': self.controller_id, 'principal': principal,
                'workspace': self.workspace_id,
                'request': request.model_dump(mode='json', exclude={'controller_epoch'})})
            with self.store.transaction():
                if self._authority(request, principal)[-1] != fingerprint:
                    raise _error('Producer authority changed before pinning', 'producer_changed')
                pin = self.store.add_reference(request.artifact_id, owner=owner, reason='shared-artifact-input')
                if pin['state'] != 'pinned':
                    raise _error('This materialization reference was already released', 'artifact_reference_released')
            expected, before = self._files(location, artifact['manifest'])
            relative = path.relative_to(location).as_posix()
            entry = expected.get(relative)
            if not entry or entry['size'] != bound.size_bytes or entry['sha256'] != bound.sha256:
                raise _error('Selected port is not covered by its committed file manifest')
            if bound.representation == 'form':
                for name, item in bound.metadata.get('inventory', {}).items():
                    attachment = self._safe(path.parent / binding_path(name), root=location)
                    committed = expected.get(attachment.relative_to(location).as_posix())
                    if (not committed or item.get('kind') != 'file' or item.get('size') != committed['size']
                            or item.get('sha256') != committed['sha256']):
                        raise _error('Form attachment is not bound to the committed producer manifest')
            verification = self.committer.verify_existing(attempt['receipt'], manifest=artifact['manifest'])
            if not verification['valid']:
                raise _error('Committed producer bytes failed verification', errors=verification['errors'])
            source = next(item for item in run['plan']['graph']['units'] if item['unit_id'] == unit['local_id'])
            if source['invocation']['kind'] == 'native':
                if 'exchange.json' not in expected or bound.representation != 'form':
                    raise _error('Native output needs a committed named exchange manifest')
                exchange, _ = self._json(location / 'exchange.json')
                named = exchange.get(request.output_port, {})
                if self._safe(Path(named['path']), root=location) != path:
                    raise _error('Named native output differs from the committed exchange manifest')
            else:
                declared = source.get('payload', {}).get('outputs', {}).get(request.output_port, {})
                if (binding_path(declared['path']) != relative
                        or declared['representation'] != bound.representation):
                    raise _error('Named output differs from its frozen port declaration')
            validate_reference(selected)
            if self._files(location, artifact['manifest'])[1] != before:
                raise _error('Producer payload changed during verification', 'producer_changed')
            again, stamp = self._json(publication_path)
            if stamp != publication_stamp or again != publication:
                raise _error('Published output index changed during verification', 'producer_changed')
            with self.store.transaction():
                current = self._authority(request, principal)
                if current[-1] != fingerprint or not any(ref['id'] == pin['id']
                        for ref in self.store.references(request.artifact_id)):
                    raise _error('Producer authority or retention changed during verification', 'producer_changed')
            if self.verify_stopped(current[0], current[1], current[2], current[4]) is not True:
                raise _error('Producer process-tree evidence changed', 'producer_not_stopped')
            receipt = dict(controller_id=self.controller_id, principal=principal, host_identity=self.host_identity,
                workspace_id=self.workspace_id, source_plan_id=lineage['source_plan_id'],
                source_unit_digest=lineage['source_unit_digest'], producer=request, reference_id=pin['id'],
                lease_id=lease['id'], evidence_revision=str(attempt['revision']),
                publication_digest=sha256_hex(publication), files_verified=len(expected), input=bound)
            return SharedArtifactReceipt(receipt_id=sha256_hex(receipt), **receipt)
        except EngineError as exc:
            if pin is not None:
                exc.details.update(reference_id=pin['id'], reference_release_attempted=False)
            raise
        except (OSError, KeyError, TypeError, ValueError, AttributeError, StopIteration) as exc:
            if isinstance(exc, ContractError):
                error = exc
            else:
                error = _error('Committed producer evidence is missing or invalid', error=type(exc).__name__)
            if pin is not None:
                # Never hide uncertainty behind a best-effort release. A caller
                # can reconcile the named reference; no payload is deleted here.
                error.details.update(reference_id=pin['id'], reference_release_attempted=False)
            raise error from (None if error is exc else exc)

    def audit(self, value, *, principal, controller_epoch=None):
        """Revalidate saved evidence; a receipt alone never authorizes file use.

        A new authenticated controller epoch may observe the same producer. It
        does not create a new retention owner or change a prepared payload.
        """
        saved = SharedArtifactReceipt.model_validate(value)
        if (saved.principal != principal or saved.controller_id != self.controller_id
                or saved.workspace_id != self.workspace_id or saved.host_identity != self.host_identity):
            raise UnauthorizedError('Artifact receipt belongs to another authenticated scope')
        request = saved.producer.model_dump(mode='json')
        if controller_epoch is not None:
            request['controller_epoch'] = controller_epoch
        fresh = self.resolve(request, principal=principal)
        def immutable(receipt):
            raw = receipt.model_dump(mode='json', exclude={'receipt_id'})
            raw['producer'].pop('controller_epoch')
            return raw
        if immutable(saved) != immutable(fresh):
            raise _error('Cached producer receipt no longer matches current committed evidence', 'producer_changed',
                         reference_id=saved.reference_id, reference_release_attempted=False)
        return saved


__all__ = ['CommittedArtifactResolver', 'ProducerArtifactRequest', 'SharedArtifactReceipt']
