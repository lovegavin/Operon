"""Build-queue/idempotency adapters with injected builders, not real bundle proof."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import threading
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from operon.bytecode import io_path
from operon.contracts.base import ContractError
from operon.contracts.plan_export import PlanExportRequest
from operon.engine.fs import atomic_json
from operon.plan_export_service import PlanExportService
from test_plan_service import sample_plan


def payload(key='build-one'):
    return {'plan': sample_plan().model_dump(mode='json'), 'request_id': key,
            'source_root': 'source', 'environment_store': 'environments', 'output': 'exports/' + key,
            'environments': {'runtime': {'generation_id': 'generation-fixture', 'executable': 'bin/tool'}}}


def create_service(tmp_path, build=None, **limits):
    io_path(tmp_path / 'source').mkdir(parents=True, exist_ok=True)
    io_path(tmp_path / 'environments').mkdir(exist_ok=True)
    calls = []
    def factory(source, environments, receipts):
        def invoke(plan, output, **kwargs):
            calls.append((source, environments, receipts, plan, output, kwargs))
            if build:
                return build(plan, output, **kwargs)
            return {'status': 'complete', 'phase': 'complete', 'bundle_identity': 'a' * 64,
                    'output': str(output), 'id': 'synthetic-builder'}
        return SimpleNamespace(build=invoke)
    return PlanExportService(tmp_path, tmp_path / '.studio/plan-exports', builder_factory=factory, **limits), calls


def settled(service):
    with service._condition:
        assert service._condition.wait_for(lambda: service._active is None and not service._pending, timeout=5)


def test_export_claim_replay_lookup_and_content_conflict_do_not_repeat_build(tmp_path):
    service, calls = create_service(tmp_path)
    request = payload()
    try:
        receipt = service.submit(request)
        settled(service)
        found = service.details(request_id=request['request_id'])
        assert found['id'] == receipt['id'] and found['status'] == 'complete'
        assert service.submit(request)['reused'] and len(calls) == 1
        changed = deepcopy(request)
        changed['output'] = 'exports/other'
        with pytest.raises(ContractError) as error:
            service.submit(changed)
        assert error.value.code == 'idempotency_conflict'
        assert len(calls) == 1
        assert calls[0][0] == tmp_path / 'source'
        assert calls[0][1] == tmp_path / 'environments'
        assert calls[0][4] == tmp_path / request['output']
    finally:
        service.close()


def test_deep_profile_claim_reads_and_recovery_keep_original_ids(tmp_path):
    workspace = tmp_path.joinpath(*(['deep-profile-' + 'x' * 32] * 6))
    service, calls = create_service(workspace)
    request = payload()
    try:
        receipt = service.submit(request)
        settled(service)
        assert len(str(service._path(receipt['id']))) > 260
        assert service.details(request_id=request['request_id'])['status'] == 'complete'
        assert service.submit(request)['reused'] and len(calls) == 1
    finally:
        service.close()
    restarted, calls = create_service(workspace)
    try:
        assert restarted.details(request_id=request['request_id'])['id'] == receipt['id']
        assert restarted.submit(request)['status'] == 'complete'
        assert calls == []
    finally:
        restarted.close()


def test_interrupted_receipt_publication_releases_owner_and_preserves_unknown_claim(tmp_path, monkeypatch):
    import operon.plan_export_service as module
    service, calls = create_service(tmp_path)
    request = payload()
    identifier = service._id(request['request_id'])
    original = module.atomic_json
    def fail_receipt(path, value):
        if Path(path) == service._path(identifier):
            raise OSError('injected receipt publication interruption')
        return original(path, value)
    monkeypatch.setattr(module, 'atomic_json', fail_receipt)
    try:
        with pytest.raises(OSError): service.submit(request)
        assert service._owner is None and calls == []
        monkeypatch.setattr(module, 'atomic_json', original)
        recovered = service.details(request_id=request['request_id'])
        assert recovered['status'] == 'unknown' and recovered['id'] == identifier
        assert service.submit(request)['status'] == 'unknown'
        changed = payload('another-key')
        changed['output'] = request['output']
        with pytest.raises(ContractError) as error: service.submit(changed)
        assert error.value.code == 'export_destination_busy'
        assert service._owner is None and calls == []
    finally:
        service.close()


def test_unrecoverable_indexed_claim_releases_new_owner_without_running(tmp_path):
    service, calls = create_service(tmp_path)
    identifier = service._id('missing-request')
    atomic_json(service.directory / 'index.json', [identifier])
    try:
        with pytest.raises(ContractError) as error: service.submit(payload())
        assert error.value.code == 'export_recovery_required'
        assert error.value.details['id'] == identifier
        assert service._owner is None and calls == []
        owner = service._acquire_owner()
        assert owner is not None
        owner.close()
    finally:
        service.close()


def test_single_build_and_four_waiting_admission_and_queued_cancel(tmp_path):
    entered, release = threading.Event(), threading.Event()
    def build(plan, output, **kwargs):
        entered.set()
        assert release.wait(5)
        if kwargs['cancel'](): raise InterruptedError('cancelled fixture')
        return {'status': 'complete', 'bundle_identity': 'a' * 64}
    service, calls = create_service(tmp_path, build)
    try:
        active = service.submit(payload('active'))
        assert entered.wait(5)
        waiting = [service.submit(payload('wait-' + str(index))) for index in range(4)]
        with pytest.raises(ContractError) as error:
            service.submit(payload('overflow'))
        assert error.value.code == 'export_queue_full'
        assert error.value.details['max_waiting'] == 4
        assert len(calls) == 1
        cancelled = service.cancel(waiting[0]['id'])
        assert cancelled['status'] == 'cancelled'
        service.submit(payload('new-slot'))
        assert service.cancel(active['id'])['status'] == 'cancelling'
    finally:
        release.set()
        service.close()
    assert service.details(active['id'])['status'] == 'cancelled'


def test_crash_claim_becomes_unknown_and_is_never_automatically_rebuilt(tmp_path):
    service, calls = create_service(tmp_path)
    request = payload()
    receipt = service.submit(request)
    settled(service)
    service.close()
    record = service.details(receipt['id'])
    record.update(status='building', phase='assemble')
    atomic_json(service._path(receipt['id']), record)
    restarted, new_calls = create_service(tmp_path)
    try:
        recovered = restarted.details(request_id=request['request_id'])
        assert recovered['status'] == 'unknown'
        assert recovered['next_actions'] == [{'action': 'inspect_export', 'id': receipt['id']}]
        assert restarted.submit(request)['status'] == 'unknown'
        assert new_calls == []
        another = payload('another-key')
        another['output'] = request['output']
        with pytest.raises(ContractError) as error:
            restarted.submit(another)
        assert error.value.code == 'export_destination_busy'
    finally:
        restarted.close()


def test_second_application_cannot_run_or_cancel_the_active_owner_build(tmp_path):
    entered, release = threading.Event(), threading.Event()
    def build(plan, output, **kwargs):
        entered.set()
        assert release.wait(5)
        if kwargs['cancel'](): raise InterruptedError('closed fixture')
        return {'status': 'complete', 'bundle_identity': 'a' * 64}
    first, calls = create_service(tmp_path, build)
    second, other_calls = create_service(tmp_path)
    try:
        receipt = first.submit(payload())
        assert entered.wait(5)
        assert second.details(receipt['id'])['status'] == 'building'
        with pytest.raises(ContractError) as error:
            second.submit(payload('other'))
        assert error.value.code == 'export_busy'
        with pytest.raises(ContractError) as error:
            second.cancel(receipt['id'])
        assert error.value.code == 'export_owner_required'
        assert other_calls == [] and len(calls) == 1
    finally:
        release.set()
        first.close()
        second.close()


def test_missing_verified_builder_receipt_is_failure_not_completion(tmp_path):
    service, _ = create_service(tmp_path, lambda *a, **k: {})
    try:
        receipt = service.submit(payload())
        settled(service)
        result = service.details(receipt['id'])
        assert result['status'] == 'failed'
        assert result['error']['code'] == 'export_receipt_invalid'
    finally:
        service.close()


def test_cancel_racing_published_completion_does_not_regress_receipt(tmp_path, monkeypatch):
    service, _ = create_service(tmp_path)
    published, release = threading.Event(), threading.Event()
    original = service._update
    def update(identifier, **changes):
        result = original(identifier, **changes)
        if changes.get('status') == 'complete':
            published.set()
            assert release.wait(5)
        return result
    monkeypatch.setattr(service, '_update', update)
    try:
        receipt = service.submit(payload())
        assert published.wait(5)
        assert service.cancel(receipt['id'])['status'] == 'complete'
    finally:
        release.set()
        service.close()
    assert service.details(receipt['id'])['status'] == 'complete'


@pytest.mark.parametrize('field,value', [('source_root', '../outside'), ('environment_store', '/global'),
                                         ('output', 'C:\\escape')])
def test_export_request_paths_and_unknown_fields_are_strict(field, value):
    request = payload()
    request[field] = value
    with pytest.raises(ValueError): PlanExportRequest.model_validate(request)
    request = payload()
    request['overwrite'] = True
    with pytest.raises(ValueError): PlanExportRequest.model_validate(request)


def test_export_refuses_destination_overlap_and_manifest_escape(tmp_path):
    service, calls = create_service(tmp_path)
    try:
        request = payload()
        request['output'] = 'environments/nested'
        with pytest.raises(ContractError) as error: service.submit(request)
        assert error.value.code == 'path_escape'
        request = payload()
        request['extra_files'] = {'resource': {'path': '../outside', 'sha256': 'a' * 64}}
        with pytest.raises(ValueError): service.submit(request)
        assert calls == []
    finally:
        service.close()


def test_export_http_permissions_and_lost_response_lookup(tmp_path):
    from operon.headless import create_headless_app
    from src.web.service import Settings
    root = Path(__file__).resolve().parents[1]
    app = create_headless_app(Settings(tmp_path, tmp_path / '.studio', tmp_path / 'no-ui', testing=True, code_root=root))
    service, calls = create_service(tmp_path)
    app.state.application.plan_exports.close()
    app.state.application.plan_exports = service
    with TestClient(app, base_url='http://127.0.0.1') as client:
        def auth(scopes):
            value = client.post('/api/agent/connect', headers={'X-Operon-Bridge': app.state.bridge.secret},
                                json={'name': 'Export test', 'scopes': scopes}).json()
            client.headers['Authorization'] = 'Bearer ' + value['token']
        auth(['context', 'edit'])
        assert client.post('/api/v1/plan-exports', json=payload()).status_code == 403
        auth(['context', 'run'])
        response = client.post('/api/v1/plan-exports', json=payload())
        assert response.status_code == 202
        settled(service)
        auth(['context'])
        found = client.get('/api/v1/plan-exports/lookup', params={'request_id': 'build-one'})
        assert found.status_code == 200 and found.json()['id'] == response.json()['id']
        assert found.json()['status'] == 'complete' and len(calls) == 1
        assert client.post('/api/v1/plan-exports/' + found.json()['id'] + '/cancel', json={}).status_code == 403


def test_export_cli_and_mcp_forward_to_explicit_new_endpoint(tmp_path, monkeypatch):
    from operon import cli
    plan = tmp_path / 'plan.json'
    plan.write_text(json.dumps(sample_plan().model_dump(mode='json')))
    request = payload()
    request.pop('plan')
    options = tmp_path / 'export.json'
    options.write_text(json.dumps(request))
    calls, clients = [], []
    class Client:
        def __init__(self, *args, **kwargs): clients.append(kwargs)
        def request(self, path, payload=None): calls.append((path, payload)); return {'id': 'receipt'}
        def close(self): pass
    monkeypatch.setattr(cli, 'Client', Client)
    cli.execute(cli.parser().parse_args(['--workspace', str(tmp_path), 'plan', 'export', str(plan), '--request', str(options)]))
    assert clients[0]['scopes'] == ['context', 'run']
    assert calls[0][0] == '/v1/plan-exports' and calls[0][1]['plan']['plan_id'] == sample_plan().plan_id
    pytest.importorskip('mcp')
    from operon.mcp_server import create_server
    server = create_server(SimpleNamespace(request=lambda path, payload=None: calls.append((path, payload)) or {'ok': True}))
    asyncio.run(server.call_tool('operon_plan_export_status', {'request_id': 'lost reply'}))
    assert calls[-1][0] == '/v1/plan-exports/lookup?request_id=lost+reply'
