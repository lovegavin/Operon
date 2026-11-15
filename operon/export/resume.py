"""Explicit standalone lineage reuse, never a cross-run cache or retry policy.

Call only while holding the standalone controller FileLock, after submitting
the fresh child and before running its scheduler. Scientific bytes are checked
outside the StateStore writer transaction; the final attachment compares state
snapshots. Durable attachments rebuild publication indexes after interruption.
"""
from __future__ import annotations

import json
from pathlib import Path

from operon.contracts.base import ContractError
from operon.engine.artifacts import ArtifactCommitter
from operon.engine.fs import atomic_json
from operon.engine.supervisor import identity_alive
from operon.environment_store.verification import confined
from operon.execution.codecs import validate_reference


def _fail(message, *, code='resume_unsafe'):
    raise ContractError(message, code=code)


def _read(path):
    try:
        value = json.loads(Path(path).read_text(encoding='utf-8'))
        if not isinstance(value, dict):
            raise ValueError('expected object')
        return value
    except (OSError, ValueError) as exc:
        raise ContractError('Resume requires a readable durable receipt: ' + str(path),
                            code='resume_unsafe') from exc


def _exited(root, attempts, environment_store):
    """Released generation leases and supervisor proofs, not a caller boolean."""
    if environment_store is None:
        _fail('Standalone resume requires its environment lease store')
    supervisor = (root / 'supervisor').resolve()
    for attempt in attempts:
        if attempt['state'] not in ('succeeded', 'failed', 'cancelled'):
            _fail('Parent has an active or uncertain attempt')
        process = attempt.get('process') or {}
        if process and _possibly_alive(process):
            _fail('Parent process identity is still alive or cannot be disproved')
        launch_path = confined(supervisor, attempt['id'] + '.launch.json')
        launch = _read(launch_path) if launch_path.exists() else None
        if launch and launch.get('pid') and _possibly_alive({
                'pid': launch['pid'], 'created': launch.get('created'),
                'boot_id': launch.get('boot_id'), 'host': launch.get('host')}):
            _fail('Parent supervisor process is still alive or uncertain')
        lease_path = confined(environment_store.root / 'leases', attempt['id'] + '.json')
        if not lease_path.exists():
            # RunPlanExecutor acquires a generation lease before any spawn.
            if process or launch or attempt['state'] == 'succeeded':
                _fail('A launched parent attempt lacks an environment lease')
            continue
        lease = _read(lease_path)
        if (lease.get('attempt_id') != attempt['id'] or lease.get('fence') != attempt['fence']
                or lease.get('state') != 'released'):
            _fail('Parent environment lease is active or uncertain')
        if not lease.get('supervisor_directory'):
            if process or launch or attempt['state'] == 'succeeded':
                _fail('A released-before-spawn lease has a process record')
            continue
        if Path(lease['supervisor_directory']).resolve() != supervisor:
            _fail('Parent environment lease names a different supervisor')
        proof = _read(supervisor / (attempt['id'] + '.tree-exit.json'))
        if (proof != lease.get('proof') or proof.get('attempt_id') != attempt['id']
                or proof.get('fence') != attempt['fence'] or proof.get('tree_exited') is not True
                or proof.get('method') not in ('linux-subreaper', 'windows-job', 'never-spawned')):
            _fail('Parent process tree exit lacks matching supervisor evidence')
        if proof['method'] == 'never-spawned':
            if process or (launch and launch.get('pid')) or attempt['state'] == 'succeeded':
                _fail('Never-spawned proof conflicts with the parent execution record')
        elif not launch or not launch.get('pid'):
            _fail('Exited process tree has no durable launch identity')
        if launch and (launch.get('attempt_id') != attempt['id'] or launch.get('fence') != attempt['fence']):
            _fail('Parent launch receipt has a different attempt identity')


def _possibly_alive(identity):
    if (type(identity.get('pid')) is not int or identity['pid'] <= 0
            or type(identity.get('created')) not in (int, float) or identity['created'] <= 0):
        _fail('Parent process identity is malformed and cannot prove exit')
    return identity_alive(identity)


def _verify_published(store, committer, published, contracts):
    receipt, outputs = published.get('receipt'), published.get('outputs')
    if not isinstance(receipt, dict) or not isinstance(outputs, dict):
        _fail('Published output descriptor is incomplete', code='artifact_mismatch')
    record = store.artifact(receipt.get('artifact_id'))
    if not record or record['state'] != 'committed' or receipt.get('state') != 'committed':
        _fail('Parent output is not durably committed', code='artifact_mismatch')
    for key, column in (('artifact_id', 'id'), ('digest', 'digest'), ('attempt_id', 'attempt_id'),
                        ('fence', 'fence'), ('location', 'location')):
        if receipt.get(key) != record[column]:
            _fail('Published output differs from its durable artifact receipt', code='artifact_mismatch')
    if not committer.verify_existing(receipt, manifest=record['manifest'])['valid']:
        _fail('Parent artifact contents changed after publication', code='artifact_mismatch')
    declarations = {item['name']: item for item in contracts}
    if not set(outputs).issubset(declarations) or any(
            item.get('required', True) and name not in outputs for name, item in declarations.items()):
        _fail('Parent output ports differ from the frozen unit contract', code='artifact_mismatch')
    location = Path(record['location']).resolve(strict=True)
    files = {item['path']: item for item in record['manifest']['files']}
    for name, reference in outputs.items():
        if not isinstance(reference, dict) or reference.get('representation') != declarations[name]['representation']:
            _fail('Parent output representation differs from its frozen contract', code='artifact_mismatch')
        path = validate_reference(reference)
        try:
            relative = path.relative_to(location).as_posix()
        except ValueError:
            _fail('Parent output reference escapes the committed payload', code='artifact_mismatch')
        item = files.get(relative)
        if not item or item['size'] != reference['size_bytes'] or item['sha256'] != reference['sha256']:
            _fail('Parent output reference is absent from its committed manifest', code='artifact_mismatch')
        # Form attachments are all rehashed by validate_reference; require them
        # to be members of this same committed artifact as well.
        if reference.get('representation') == 'form':
            for attached in reference['metadata']['inventory']:
                attached_path = confined(path.parent, attached)
                if not attached_path.is_relative_to(location) or attached_path.relative_to(location).as_posix() not in files:
                    _fail('Form attachment escapes the committed artifact', code='artifact_mismatch')
    return record


def _materialize(root, run_id, attachments):
    directory = confined(root / 'runs', run_id) / 'published'
    for item in attachments:
        atomic_json(confined(directory, item['local_id'] + '.json'), item['published'])


def attach_verified_resume(store, *, root, parent_run_id, run_id, run_identity,
                           request_id, principal, environment_store):
    """Verify and attach the successful ancestor-closed prefix to a fresh run.

    A corrupt otherwise-reusable output rejects the operation. Failed units and
    successful units whose ancestors were not retained execute normally in the
    new run. An interrupted post-commit descriptor write is repaired on replay.
    """
    root = Path(root).resolve()
    if not request_id or len(request_id) > 200:
        _fail('Resume requires a bounded nonempty request ID')
    source, destination = store.run(parent_run_id), store.run(run_id)
    if (source['principal'] != principal or destination['principal'] != principal
            or source['workspace_id'] != destination['workspace_id'] or parent_run_id == run_id):
        _fail('Resume requires two distinct runs belonging to this caller and workspace')
    if source['status'] not in ('failed', 'cancelled'):
        _fail('Only failed or cancelled parents require an explicit new run')
    if source['plan_key'] != run_identity or destination['plan_key'] != run_identity:
        _fail('Plan, input or environment identity changed', code='resume_identity_mismatch')
    contracts = {unit['unit_id']: unit.get('output_contracts', [])
                 for unit in source['plan']['graph'].get('units', [])}
    committer = ArtifactCommitter(root, store)
    previous = store.resume_receipt(principal=principal, request_id=request_id)
    if previous is not None:
        if any(previous.get(key) != value for key, value in (
                ('parent_run_id', parent_run_id), ('run_id', run_id), ('run_identity', run_identity))):
            _fail('Resume request ID belongs to another lineage', code='idempotency_conflict')
        attachments = store.resume_attachments(run_id)
        for item in attachments:
            _verify_published(store, committer, item['published'], contracts.get(item['local_id'], []))
        _materialize(root, run_id, attachments)
        return previous
    attempts = store.attempts(parent_run_id)
    _exited(root, attempts, environment_store)
    units = store.units(parent_run_id)
    pending = {unit['local_id']: unit for unit in units if unit['state'] == 'succeeded'}
    verified = {}
    # Iterate in dependency order, independent of saved ordinal ordering.
    while pending:
        ready = [name for name, unit in pending.items() if set(unit['depends_on']).issubset(verified)]
        if not ready:
            break
        for name in ready:
            published = _read(confined(root / 'runs' / parent_run_id / 'published', name + '.json'))
            record = _verify_published(store, committer, published, contracts.get(name, []))
            verified[name] = {'artifact': record, 'published': published}
            del pending[name]
    receipt = store.attach_resume(principal=principal, request_id=request_id,
        parent_run_id=parent_run_id, run_id=run_id, run_identity=run_identity,
        source_revision=source['revision'], destination_revision=destination['revision'],
        attempt_revisions={attempt['id']: attempt['revision'] for attempt in attempts}, verified=verified)
    _materialize(root, run_id, store.resume_attachments(run_id))
    return receipt


__all__ = ['attach_verified_resume']
