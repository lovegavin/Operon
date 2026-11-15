"""Committed file/HTTP read integration; journal fixtures are not process E2E."""
import errno
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from operon.bytecode import io_path
from operon.contracts.base import ContractError
from operon.engine.artifacts import ArtifactCommitter
from operon.engine.contracts import EngineError, ResourceRequest
from test_plan_results import owned


def publish(owned, run_id='run-a', *, content=b'first\nsecond\nthird\n', name='report.txt'):
    store = owned.store
    attempt = owned.attempts[run_id][0]
    unit = store.unit(attempt['unit_id'])
    workspace = 'b' if run_id == 'run-b' else 'a'
    root = owned.services[workspace].directory / 'invocations'
    output = root / 'runs' / run_id / 'attempts' / attempt['id'] / 'outputs'
    output.mkdir(parents=True)
    io_path(output / name).write_bytes(content)
    lease = store.acquire_lease(attempt_id=attempt['id'], pool_id='pool-test', owner={},
                                request=ResourceRequest(process_reservation_bytes=10, cpu_threads=1))
    for state in ('starting', 'running', 'committing'):
        store.transition_attempt(attempt['id'], state)
    receipt = ArtifactCommitter(root, store).commit_existing(attempt=attempt, unit=unit, fence=attempt['fence'],
        source_root=output, files=[name], run_id=run_id, kind='invocation-output')
    store.transition_attempt(attempt['id'], 'succeeded', exit_code=0, receipt=receipt)
    store.release_lease(lease['id'])
    owned.app.service.directory = owned.services['a'].directory
    return receipt['artifact_id'], output / name


def selector(owned, artifact):
    return owned.plans.artifact_files('run-a', artifact_id=artifact)['files'][0]['file_id']


def test_committed_files_preview_and_verified_open_do_not_publish_paths(owned):
    artifact, path = publish(owned)
    before = owned.store.connection.total_changes
    page = owned.plans.artifact_files('run-a', artifact_id=artifact, limit=1)
    entry, = page['files']
    assert entry['name'] == 'report.txt' and not page['has_more']
    assert 'relative_path' not in entry and str(owned.services['a'].root) not in json.dumps(page)
    preview = owned.plans.artifact_preview('run-a', artifact_id=artifact, file_id=entry['file_id'], max_rows=1)
    assert preview['kind'] == 'text' and preview['content'] == 'first\n' and preview['truncated']
    assert preview['digest_verified'] is True
    with pytest.raises(ValueError):
        owned.plans.artifact_preview('run-a', artifact_id=artifact, file_id=entry['file_id'], path='private')
    opened = owned.plans.open_artifact('run-a', artifact_id=artifact, file_id=entry['file_id'])
    assert b''.join(opened.chunks()) == path.read_bytes() and opened.closed
    assert owned.store.connection.total_changes == before


def test_preview_is_byte_bounded_and_binary_does_not_relay_file(owned):
    artifact, _ = publish(owned, content=b'\0' * 100000, name='matrix.bin')
    result = owned.plans.artifact_preview('run-a', artifact_id=artifact, file_id=selector(owned, artifact), max_bytes=11)
    assert result['kind'] == 'binary' and result['content'] is None
    assert result['bytes_read'] == 11 and result['truncated'] and not result['digest_verified']


def test_other_run_artifact_and_wrong_file_id_do_not_grant_access(owned):
    artifact, _ = publish(owned, 'run-other')
    with pytest.raises(ContractError) as error:
        owned.plans.artifact_files('run-a', artifact_id=artifact)
    assert error.value.code == 'plan_artifact_not_found'
    artifact, _ = publish(owned)
    with pytest.raises(ContractError) as error:
        owned.plans.open_artifact('run-a', artifact_id=artifact, file_id='0' * 64)
    assert error.value.code == 'plan_artifact_file_not_found'


def test_corrupt_bytes_rejected_by_complete_preview_and_download(owned):
    artifact, path = publish(owned, content=b'original')
    file_id = selector(owned, artifact)
    path.write_bytes(b'modified')
    for method in (owned.plans.open_artifact, owned.plans.artifact_preview):
        with pytest.raises(ContractError) as error:
            method('run-a', artifact_id=artifact, file_id=file_id)
        assert error.value.code == 'corrupt_artifact'


@pytest.mark.parametrize('kind', ['symlink', 'hardlink', 'ancestor'])
def test_links_cannot_redirect_owned_file_read(owned, tmp_path, kind):
    artifact, path = publish(owned)
    file_id = selector(owned, artifact)
    outside = tmp_path / 'private'
    outside.mkdir()
    secret = outside / path.name
    secret.write_bytes(path.read_bytes())
    path.unlink()
    try:
        if kind == 'symlink': io_path(path).symlink_to(io_path(secret))
        elif kind == 'hardlink': os.link(io_path(secret), io_path(path))
        else:
            path.parent.rmdir()
            io_path(path.parent).symlink_to(io_path(outside), target_is_directory=True)
    except OSError as exc:
        if getattr(exc, 'winerror', None) in (5, 1314) or exc.errno in (errno.EPERM, errno.EACCES):
            pytest.skip('Filesystem link permission unavailable')
        raise
    with pytest.raises(ContractError) as error:
        owned.plans.artifact_preview('run-a', artifact_id=artifact, file_id=file_id)
    assert error.value.code == 'plan_artifact_unavailable'


def test_remote_full_open_requires_explicit_transfer_without_contacting_pool(owned):
    owned.app.service.pool_remote = True
    owned.app.service.pool_managed = False
    with pytest.raises(ContractError) as error:
        owned.plans.open_artifact('run-a', artifact_id='artifact', file_id='a' * 64)
    assert error.value.code == 'artifact_transfer_required'


def test_managed_local_pool_uses_authorized_descriptor_and_local_verified_handle(owned):
    artifact, path = publish(owned)
    file_id = selector(owned, artifact)
    calls = []
    def request(method, values):
        calls.append((method, values))
        values = dict(values)
        workspace, run_id = values.pop('workspace'), values.pop('run_id')
        values.pop('session_id')
        return owned.pool.plan_artifact_file(workspace, run_id, **values)
    service = owned.app.service
    service.pool_remote, service.pool_managed = True, True
    service.pool_principal, service.pool_session_id = 'owner', 'session'
    service._ensure_pool_session = lambda: None
    service.pool_client = SimpleNamespace(request=request)
    opened = owned.plans.open_artifact('run-a', artifact_id=artifact, file_id=file_id)
    assert b''.join(opened.chunks()) == path.read_bytes()
    assert calls[0][0] == 'plan.artifact_file' and calls[0][1]['session_id'] == 'session'


def test_reused_artifact_requires_explicit_completed_attachment_and_retained_reference(owned):
    artifact, path = publish(owned, 'run-other')
    consumer = owned.store.units('run-a')[0]
    source = owned.store.units('run-other')[0]
    with owned.store.transaction():
        owned.store.connection.execute('INSERT INTO unit_reuses(unit_id,source_run_id,source_unit_id,artifact_id,published_json,created_at) '
            'VALUES(?,?,?,?,?,?)', (consumer['id'], 'run-other', source['id'], artifact, '{}', 'test'))
    owned.store.update_unit(consumer['id'], state='succeeded')
    with pytest.raises(ContractError):
        owned.plans.artifact_files('run-a', artifact_id=artifact)
    pin = owned.store.add_reference(artifact, owner='run:run-a', reason='explicit-run-resume:one')
    opened = owned.plans.open_artifact('run-a', artifact_id=artifact, file_id=selector(owned, artifact))
    assert b''.join(opened.chunks()) == path.read_bytes()
    owned.store.release_reference(pin['id'])
    with pytest.raises(ContractError):
        owned.plans.artifact_files('run-a', artifact_id=artifact)


def test_preview_utf8_boundary_remains_text_and_never_reads_remainder(owned):
    artifact, _ = publish(owned, content='αβγ'.encode())
    result = owned.plans.artifact_preview('run-a', artifact_id=artifact, file_id=selector(owned, artifact), max_bytes=3)
    assert result['kind'] == 'text' and result['content'] == 'α'
    assert result['bytes_read'] == 3 and result['truncated'] and not result['digest_verified']


def test_unregistered_neighbor_files_never_appear_or_open(owned):
    artifact, path = publish(owned)
    (path.parent / 'private.txt').write_bytes(b'not committed')
    entries = owned.plans.artifact_files('run-a', artifact_id=artifact)['files']
    assert [entry['name'] for entry in entries] == ['report.txt']


def test_http_scope_strict_queries_and_active_formats_are_attachments(owned, tmp_path):
    from operon.headless import create_headless_app
    from src.web.service import Settings
    artifact, path = publish(owned, content=b'<svg onload="alert(1)"/>', name='unsafe.svg')
    file_id = selector(owned, artifact)
    root = tmp_path / 'http'; root.mkdir()
    app = create_headless_app(Settings(root, root / '.studio', root / 'ui', testing=True,
                                       code_root=Path(__file__).resolve().parents[1]))
    app.state.application.plans = owned.plans
    base = f'/api/v1/plans/run-a/artifacts/{artifact}/files'
    with TestClient(app, base_url='http://127.0.0.1') as client:
        assert client.get(base).status_code == 403
        token = client.post('/api/agent/connect', headers={'X-Operon-Bridge': app.state.bridge.secret},
            json={'name': 'Artifact reads', 'scopes': ['context']}).json()['token']
        client.headers['Authorization'] = 'Bearer ' + token
        assert client.get(base).status_code == 200
        assert client.get(base + '?path=private').status_code == 422
        assert client.get(base + f'/{file_id}/preview?max_bytes=65537').status_code == 422
        response = client.get(base + f'/{file_id}/open?inline=true')
        assert response.status_code == 200 and response.content == path.read_bytes()
        assert response.headers['content-disposition'].startswith('attachment;')
        assert response.headers['x-content-type-options'] == 'nosniff'
        assert 'sandbox' in response.headers['content-security-policy']


def test_artifact_rpc_uses_strict_ownership_checked_normal_lane(owned):
    from operon.pool_service import PoolControlServer
    from operon.engine.admission_limits import PrincipalLimiter
    from operon.engine.control import ControlError
    artifact, _ = publish(owned)
    server = PoolControlServer.__new__(PoolControlServer)
    server.pool, server.token = owned.pool, 'test-token'
    server.principal_limiter = PrincipalLimiter(rate=100, burst=100, concurrent=4)
    params = {'_token': 'test-token', 'workspace': 'a', 'principal': 'owner', 'run_id': 'run-a', 'artifact_id': artifact}
    assert server.dispatch('plan.artifact_files', params)['files']
    with pytest.raises(ControlError): server.dispatch_lifecycle('plan.artifact_files', params)
    with pytest.raises(ValueError): server.dispatch('plan.artifact_files', {**params, 'path': 'private'})
