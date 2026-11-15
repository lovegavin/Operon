"""Desktop request receipt storage, not scientific run evidence."""
from copy import deepcopy

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from types import SimpleNamespace
import pytest

from operon.contracts.base import ContractError
from operon.plan_ui_state import PlanUiStore, PlanUiState, mount_plan_ui_state
from test_plan_service import sample_binding, sample_plan


def record(key='request-1'):
    return {'title': 'Frozen workflow', 'created_at': '2026-11-15T00:00:00Z', 'status': 'pending',
            'submission': {'plan': sample_plan().model_dump(mode='json'), 'binding': sample_binding(), 'request_id': key}}


def state(records=()):
    return {'version': 1, 'revision': 0, 'records': list(records), 'exports': []}


def test_pending_request_survives_reopen_and_workspace_isolation(tmp_path):
    store = PlanUiStore(tmp_path / 'profile', tmp_path / 'first')
    saved = store.write(state([record()]))
    assert saved.revision == 1
    assert PlanUiStore(tmp_path / 'profile', tmp_path / 'first').read() == saved
    assert not PlanUiStore(tmp_path / 'profile', tmp_path / 'other').read().records
    assert saved.records[0].submission.binding.environments['runtime'].generation_id == 'generation-fixture'


def test_revision_and_immutable_request_conflicts_do_not_change_disk(tmp_path):
    store = PlanUiStore(tmp_path, tmp_path / 'workspace')
    saved = store.write(state([record()]))
    with pytest.raises(ContractError, match='another client'):
        store.write(state([record('different')]))
    changed = saved.model_dump(mode='json')
    changed['records'][0]['submission']['binding']['package_root'] = 'different'
    with pytest.raises(ContractError, match='cannot change'):
        store.write(changed)
    deleted = saved.model_dump(mode='json'); deleted['records'] = []
    with pytest.raises(ContractError, match='Unresolved'):
        store.write(deleted)
    assert store.read() == saved


def test_confirmed_receipt_can_be_archived_without_touching_the_run(tmp_path):
    store = PlanUiStore(tmp_path, tmp_path / 'workspace')
    saved = store.write(state([record()])).model_dump(mode='json')
    saved['records'][0].update(status='accepted', run_id='owned-run')
    confirmed = store.write(saved).model_dump(mode='json')
    confirmed['records'] = []
    assert not store.write(confirmed).records


def test_strict_limits_and_byte_budget_fail_before_overwriting(tmp_path):
    store = PlanUiStore(tmp_path, tmp_path / 'workspace')
    saved = store.write(state([record()]))
    with pytest.raises(ValueError):
        PlanUiState.model_validate(state([record(str(index)) for index in range(21)]))
    bad = state(); bad['workspace'] = '/other'
    with pytest.raises(ValueError):
        store.write(bad)
    with pytest.raises(ValueError, match='Duplicate'):
        store.write(state([record(), record()]))
    changed = saved.model_dump(mode='json'); changed['records'].append(record('new'))
    store.max_bytes = store.path.stat().st_size + 10
    with pytest.raises(ContractError, match='full'):
        store.write(changed)
    assert store.read() == saved


def test_history_uses_context_read_and_edit_write_not_run_permission(tmp_path):
    app = FastAPI()
    calls = []
    class Bridge:
        def actor(self, request, capability):
            calls.append(capability)
            if capability not in request.headers.get('permissions', '').split(','):
                raise HTTPException(403)
    mount_plan_ui_state(app, SimpleNamespace(service=SimpleNamespace(directory=tmp_path, root=tmp_path / 'w')), Bridge())
    with TestClient(app) as client:
        assert client.get('/api/v1/plan-ui-state', headers={'permissions': 'context'}).status_code == 200
        assert client.post('/api/v1/plan-ui-state', json=state(), headers={'permissions': 'context,run'}).status_code == 403
        assert client.post('/api/v1/plan-ui-state', json=state([record()]), headers={'permissions': 'edit'}).status_code == 200
    assert calls == ['context', 'edit', 'edit']
