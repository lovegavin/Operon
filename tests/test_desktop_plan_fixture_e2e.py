"""Opt-in actual companion fixture execution; no desktop/browser claim.

OPERON_DESKTOP_PLAN_FIXTURE points to prepare_desktop_plan.py's output folder.
Runtime preparation and permission to execute it are explicit prior actions.
"""
import json
import os
from pathlib import Path
from types import SimpleNamespace
import time
import uuid

import pytest

from operon.bytecode import io_path
from operon.cluster.host import stopped_attempt_proof
from operon.environment_store import EnvironmentStore
from operon.plan_service import PlanService
from operon.pool_service import PoolService


def test_actual_desktop_fixture_shared_service_committed_result(tmp_path):
    value = os.environ.get('OPERON_DESKTOP_PLAN_FIXTURE')
    if not value:
        pytest.skip('Explicitly prepared desktop fixture not supplied')
    fixture = Path(value).resolve(strict=True)
    preparation = json.loads((fixture / 'preparation.json').read_text(encoding='utf-8'))
    assert preparation['status'] == 'prepared'
    binding = json.loads((fixture / 'binding.json').read_text(encoding='utf-8'))
    # The helper allows a nested fixture folder; derive the actual workspace
    # from the authoritative workspace-relative binding, not a guessed parent.
    workspace = fixture
    for _ in Path(binding['package_root']).parent.parts:
        workspace = workspace.parent
    store = EnvironmentStore(workspace / binding['environment_store'], create=False)
    generation = binding['environments']['python']['generation_id']
    before = store.binding(generation)
    pool = PoolService(root=tmp_path / 'pool', admission_dir=tmp_path / 'admission',
        workspaces=[{'root': workspace, 'principal': 'fixture-owner'}],
        code_root=Path(__file__).resolve().parents[1], catalog={'operators': [], 'readers': []},
        capacity_bytes=512 * 1024**2, cpu_threads=1)
    result = {'kind': 'real-local-pool', 'fixture': str(fixture), 'source': 'actual prepared runtime'}
    try:
        plans = PlanService(SimpleNamespace(service=pool.resolve(workspace), stopping=False))
        compiled = plans.compile(json.loads((fixture / 'compile-request.json').read_text(encoding='utf-8')))
        assert compiled.plan_id == preparation['plan_id']
        request = {'plan': compiled.model_dump(mode='json'), 'binding': binding,
                   'request_id': 'desktop-fixture-' + uuid.uuid4().hex}
        accepted = plans.submit(request)
        assert plans.submit(request)['run_id'] == accepted['run_id']
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            current = plans.details(accepted['run_id'])
            if current['state'] in ('complete', 'failed', 'cancelled'):
                break
            time.sleep(.05)
        assert current['state'] == 'complete', pool.plan_details(workspace, accepted['run_id'], principal='fixture-owner')
        attempts = pool.engine.store.attempts(accepted['run_id'])
        assert len(attempts) == 2
        for attempt in attempts:
            assert attempt['state'] == 'succeeded'
            assert pool.engine.store.lease(attempt['id'])['state'] == 'released'
            assert stopped_attempt_proof(pool.resolve(workspace).directory / 'invocations', attempt)
        artifacts = plans.artifacts(accepted['run_id'])['artifacts']
        values = {}
        for artifact in artifacts:
            files = plans.artifact_files(accepted['run_id'], artifact_id=artifact['artifact_id'])['files']
            assert len(files) == 1
            selected = dict(artifact_id=artifact['artifact_id'], file_id=files[0]['file_id'])
            preview = plans.artifact_preview(accepted['run_id'], **selected)
            assert preview['digest_verified'] is True and preview['truncated'] is False
            opened = plans.open_artifact(accepted['run_id'], **selected)
            contents = b''.join(opened.chunks())
            assert opened.closed
            assert contents.decode('utf-8') == preview['content']
            values[artifact['unit_id']] = json.loads(contents)
        assert values == {'first': {'value': 14}, 'second': {'value': 42}}
        assert store.binding(generation) == before
        leases = [json.loads(io_path(path).read_text(encoding='utf-8')) for path in (store.root / 'leases').glob('*.json')]
        assert leases and all(lease['state'] == 'released' for lease in leases)
        result.update(run_id=accepted['run_id'], values=values, attempt_count=len(attempts),
                      all_resource_and_environment_leases_released=True, tree_exit_proof=True)
        (tmp_path / 'evidence.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    finally:
        pool.shutdown()
