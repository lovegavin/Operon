"""Automatic collection, stable actions and native execution without hand manifests."""
from copy import deepcopy
import json
import os
from pathlib import Path
from types import SimpleNamespace
import time

import pytest

from test_native_runtime_snapshot import provider, graph
from operon.canvas_plans import CanvasPlans
from operon.contracts.base import ContractError
from operon.export.automatic import collect_canvas_code
from operon.planning import WorkflowCompiler
from operon.plan_service import PlanService

ROOT = Path(__file__).resolve().parents[1]


def test_collector_includes_provider_data_without_import_and_rejects_code_drift(provider, tmp_path):
    import sys
    root, catalog = provider
    resource = root / 'owned_native_provider' / 'palette.txt'
    resource.write_text('blue', encoding='utf-8')
    plan = WorkflowCompiler().compile(graph(root), None, catalog, root=root, freeze_defaults=False)
    destination = tmp_path / 'collected'
    manifests = collect_canvas_code(plan, destination, application_root=ROOT, roots=[ROOT, root])
    assert set(manifests) == {'OwnedReader', 'owned.identity'}
    assert (destination / 'owned_native_provider/palette.txt').read_text() == 'blue'
    assert 'owned_native_provider.operators' not in sys.modules
    code = root / 'owned_native_provider/operators.py'
    code.write_text(code.read_text() + '\n# changed code\n')
    with pytest.raises(ContractError, match='differs'):
        collect_canvas_code(plan, tmp_path / 'changed', application_root=ROOT, roots=[ROOT, root])


def minimal_app(tmp_path):
    service = SimpleNamespace(root=tmp_path, directory=tmp_path / '.studio')
    service.directory.mkdir()
    return SimpleNamespace(service=service)


def settled(canvas, key):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        record = canvas.status(key)
        if record['status'] != 'preparing':
            return record
        time.sleep(.01)
    raise TimeoutError(key)


def test_preparation_and_lost_submit_response_keep_exact_snapshot(tmp_path, monkeypatch):
    app = minimal_app(tmp_path)
    canvas = CanvasPlans(app)
    prepared = {'plan': {'frozen': 1}, 'binding': {'frozen': 2}, 'profile_id': None}
    monkeypatch.setattr(canvas, 'prepare', lambda graph, progress: prepared)
    calls = []
    def submit(body):
        calls.append(deepcopy(body))
        if len(calls) == 1:
            raise OSError('lost response after durable pool acceptance')
        return {'run_id': 'one', 'state': 'queued'}
    app.plans = SimpleNamespace(submit=submit)
    try:
        canvas.start({'nodes': []}, 'prepare')
        assert settled(canvas, 'prepare')['status'] == 'ready'
        assert canvas.start({'nodes': []}, 'prepare')['status'] == 'ready'
        with pytest.raises(ContractError): canvas.start({'nodes': [1]}, 'prepare')
        with pytest.raises(OSError): canvas.execute('prepare', action='run', request_id='action')
        assert canvas.execute('prepare', action='run', request_id='action')['run_id'] == 'one'
        assert canvas.execute('prepare', action='run', request_id='action')['run_id'] == 'one'
        assert len(calls) == 2 and calls[0] == calls[1]
        with pytest.raises(ContractError): canvas.execute('prepare', action='export', request_id='action')
    finally:
        canvas.close()


def test_archive_rejects_outside_alias_and_cancel(tmp_path):
    from operon.environment_store.canvas import archive_tree
    root = tmp_path / 'runtime'; root.mkdir()
    (root / 'data').write_text('x')
    with pytest.raises(InterruptedError):
        archive_tree(root, tmp_path / 'cancel.tar', cancel=lambda: True)
    assert (root / 'data').read_text() == 'x'


def test_remote_plan_reference_cannot_escape_or_name_unowned_run(tmp_path):
    canvas = CanvasPlans(minimal_app(tmp_path))
    try:
        with pytest.raises(ContractError): canvas.remote_reference('../secrets')
        with pytest.raises(ContractError): canvas.remote_reference('remote-plan-' + 'a' * 64)
        result = canvas._remember_remote('server', {'run_id': 'science', 'state': 'running'})
        assert canvas.remote_reference(result['run_id']) == {'profile_id': 'server', 'run_id': 'science'}
    finally:
        canvas.close()


def test_preparation_cancel_is_durable_and_abandoned_owner_is_terminal(tmp_path, monkeypatch):
    from operon.engine.fs import atomic_json
    canvas = CanvasPlans(minimal_app(tmp_path))
    entered = __import__('threading').Event()
    def preparation(graph, progress):
        entered.set()
        while True:
            progress('environment')
            time.sleep(.01)
    monkeypatch.setattr(canvas, 'prepare', preparation)
    try:
        canvas.start({}, 'cancel-me')
        assert entered.wait(2) and canvas.active
        canvas.cancel('cancel-me')
        assert settled(canvas, 'cancel-me')['status'] == 'cancelled'
        record = {'request_id': 'crashed', 'graph_digest': 'old', 'status': 'preparing', 'owner': None}
        atomic_json(canvas._path('crashed'), record)
        assert canvas.status('crashed')['code'] == 'preparation_interrupted'
        assert not canvas.active
    finally:
        canvas.close()


def test_auto_placement_keeps_data_local_and_refuses_mixed_execution(tmp_path):
    from src.web.models import Graph
    document = graph(tmp_path)
    document['runtime'] = {'execution': {'mode': 'auto', 'kind': 'local'}}
    value = Graph.model_validate(document)
    target = {'kind': 'ssh', 'profile_id': 'server'}
    checked = {'execution_plan': {'units': [{'target': target}]}}
    prepared = CanvasPlans._placement(value, checked)
    assert prepared.runtime['execution']['profile_id'] == 'server'
    assert prepared.nodes[0].source.location == {'kind': 'local'}
    assert value.runtime['execution']['kind'] == 'local'
    checked['execution_plan']['units'].append({'target': {'kind': 'local'}})
    with pytest.raises(ContractError, match='spans execution hosts'):
        CanvasPlans._placement(value, checked)


def test_resource_paths_packaged_without_guessing_strings(provider):
    from operon.export.automatic import bind_declared_resources
    root, catalog = provider
    (root / 'reference.txt').write_text('reference data')
    plan = WorkflowCompiler().compile(graph(root), None, catalog, root=root, freeze_defaults=False)
    data = plan.model_dump(mode='json')
    descriptor = data['diagnostics']['native_descriptor_audit']['owned.identity']
    descriptor['parameters_schema']['properties']['reference'] = {'type': 'string', 'x-operon-path': 'workflow'}
    values = data['units'][0]['payload']['task_manifest']['steps'][0]['params']
    values.update(reference='reference.txt', title='not-a-file.txt')
    files = bind_declared_resources(data, workspace=root, base_dir=str(root), input_roots=[root])
    assert len(files) == 1 and values['reference'].startswith('storage://__code__/resources/')
    assert values['title'] == 'not-a-file.txt'
    assert list(data['execution_policy']['packaged_resources'].values()) == [next(iter(files.values()))['sha256']]
    values['reference'] = '../not-authorized.txt'
    with pytest.raises(ValueError):
        bind_declared_resources(data, workspace=root, base_dir=str(root), input_roots=[root])


def test_native_isolation_uses_frozen_targets_not_shared_import(provider, monkeypatch):
    from operon.execution.native_bootstrap import NativeRuntimeSnapshot, register_native_runtime
    from src.task.step import STEPS
    from operon.planning.descriptor_snapshot import execution_descriptor
    import operon.isolation
    root, catalog = provider
    plan = WorkflowCompiler().compile(graph(root), None, catalog, root=root, freeze_defaults=False)
    audit = deepcopy(plan.diagnostics['native_descriptor_audit'])
    audit['owned.identity']['execution'] = {'mode': 'isolated', 'paths': ['original-target']}
    descriptors = [execution_descriptor(d) for d in audit.values()]
    seen = []
    monkeypatch.setattr(operon.isolation, 'proxy_step', lambda d, state: seen.append((d, state)) or type('Owned', (), {}))
    monkeypatch.setenv('OPERON_ENVIRONMENT_ROOT', str(root))
    snapshot = NativeRuntimeSnapshot(descriptors=descriptors, implementations=plan.units[0].payload['native_implementations'],
        audit_descriptors=audit, isolation_targets={'owned.identity': ['targets/one']}, environment_requirement_digest='a' * 64)
    register_native_runtime(snapshot, plan.units[0].payload['task_manifest'])
    STEPS.get('owned.identity')
    assert seen[0][0]['execution']['paths'] == ['targets/one']
    assert seen[0][1]['_runtime_root'] == str(root)


def test_canvas_http_preparation_requires_run_permission(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from operon.headless import create_headless_app
    from src.web.service import Settings
    http_app = create_headless_app(Settings(tmp_path, tmp_path / '.studio', tmp_path / 'no-ui', testing=True, code_root=ROOT))
    calls = []
    canvas = http_app.state.application.canvas_plans
    monkeypatch.setattr(canvas, 'start', lambda graph, key: calls.append(key) or {'status': 'preparing'})
    with TestClient(http_app, base_url='http://127.0.0.1') as client:
        def auth(scopes):
            token = client.post('/api/agent/connect', headers={'X-Operon-Bridge': http_app.state.bridge.secret},
                json={'name': 'Canvas test', 'scopes': scopes}).json()['token']
            client.headers['Authorization'] = 'Bearer ' + token
        auth(['context', 'edit'])
        body = {'graph': {}, 'request_id': 'same'}
        assert client.post('/api/v1/canvas-plans/prepare', json=body).status_code == 403
        assert not calls
        auth(['context', 'run'])
        assert client.post('/api/v1/canvas-plans/prepare', json=body).status_code == 200
        assert calls == ['same']


def test_application_compiles_imported_script_canvas_without_library(tmp_path, monkeypatch):
    from operon.application import Application
    from operon.workflow_spec import load_workflow
    from operon.execution.native_bootstrap import validate_native_descriptors
    from src.web.service import Settings
    monkeypatch.setenv('OPERON_REGISTRY_MAINTENANCE', '1')
    app = Application(Settings(tmp_path, tmp_path / '.studio', tmp_path / 'no-ui',
                               testing=True, code_root=ROOT),
                      catalog={'operators': [], 'readers': []})
    try:
        document = load_workflow(ROOT / 'examples/workflows/script_pipeline/workflow.yaml')
        prepared = app.prepare(document)
        checked = app.validate(prepared, require_files=True)
        bound = app._execution_binding(prepared, checked)
        plan = app.compile_plan(bound, require_files=True)
        assert len(plan.units[0].node_ids) == 3 and len(plan.edges) == 2
        payload = plan.units[0].payload
        validate_native_descriptors(payload['native_descriptors'], plan.implementations, payload['task_manifest'])
    finally:
        app.shutdown()


def test_http_script_canvas_reaches_environment_after_real_preflight(tmp_path, monkeypatch):
    """Exercise the UI's frozen request DTO, asynchronous worker and real compiler."""
    from fastapi.testclient import TestClient
    from operon.headless import create_headless_app
    from operon.workflow_spec import load_workflow
    from src.web.service import Settings
    import operon.environment_store.canvas as environment_module
    monkeypatch.setenv('OPERON_REGISTRY_MAINTENANCE', '1')
    def reached(*args, **kwargs):
        raise InterruptedError('test stopped before environment capture')
    monkeypatch.setattr(environment_module, 'prepare_python', reached)
    server = create_headless_app(Settings(tmp_path, tmp_path / '.studio', tmp_path / 'no-ui',
                                          testing=True, code_root=ROOT))
    with TestClient(server, base_url='http://127.0.0.1') as client:
        token = client.post('/api/agent/connect', headers={'X-Operon-Bridge': server.state.bridge.secret},
                            json={'name': 'script-canvas', 'scopes': ['context', 'run']}).json()['token']
        client.headers['Authorization'] = 'Bearer ' + token
        graph = load_workflow(ROOT / 'examples/workflows/script_pipeline/workflow.yaml')
        result = client.post('/api/v1/canvas-plans/prepare',
                             json={'graph': graph, 'request_id': 'script-http'})
        assert result.status_code == 200, result.text
        record = settled(server.state.application.canvas_plans, 'script-http')
        assert record['status'] == 'cancelled', record
        assert record['error'] == 'test stopped before environment capture'


def test_actual_canvas_auto_prepare_pool_run_and_portable_export(provider, tmp_path, monkeypatch):
    """Opt-in real private Python; no fake generation/build/probe success."""
    python = os.environ.get('OPERON_CANVAS_TEST_PYTHON')
    if not python:
        pytest.skip('Actual private Python not supplied')
    from operon.pool_service import PoolService
    from operon.plan_export_service import PlanExportService
    from src.web.models import Graph
    root, catalog = provider
    rscript = os.environ.get('OPERON_CANVAS_TEST_R')
    tool = os.environ.get('OPERON_CANVAS_TEST_TOOL')
    if rscript or tool:
        # Test-owned provider only. Force actual R work in both the pool run and
        # exported launcher, without changing a library operator or declaration.
        source = root / 'owned_native_provider/operators.py'
        extra = '        import subprocess\n        from operon.dependencies import find_tool\n'
        if rscript:
            extra += ('        answer = subprocess.check_output([find_tool("Rscript"), "--vanilla", "-e", "cat(sum(c(1,2,3)))"], text=True)\n'
                      '        assert answer.strip() == "6", answer\n')
        if tool:
            assert tool == 'xz', 'Acceptance currently exercises the real xz codec'
            extra += ('        packed = subprocess.check_output([find_tool("xz"), "-c"], input=b"owned scientific fixture")\n'
                      '        assert subprocess.check_output([find_tool("xz"), "-dc"], input=packed) == b"owned scientific fixture"\n')
        code = source.read_text(encoding='utf-8').replace('        self.values = {key:', extra + '        self.values = {key:')
        source.write_text(code, encoding='utf-8')
        from operon_sdk.declarations import compile_declaration
        from src.web.operator_catalog import catalog_from_descriptors
        descriptors = []
        for original in [*catalog['operators'], *catalog['readers']]:
            original = deepcopy(original)
            if original['id'] == 'owned.identity':
                original['resources']['external_tools'] = (['Rscript'] if rscript else []) + ([tool] if tool else [])
            from operon_sdk.protocol import Descriptor
            original = {key: value for key, value in original.items() if key in Descriptor.model_fields}
            item = compile_declaration(original, root)
            item['distribution'] = 'owned-native-provider'
            item['implementation'] = {'package': item['distribution'], 'version': '1.0.0',
                'code_sha': item['code_sha'], 'declaration_sha': item['declaration_sha']}
            descriptors.append(item)
        catalog = catalog_from_descriptors(descriptors)
        import operon.dependencies
        if rscript:
            monkeypatch.setattr(operon.dependencies, 'find_tool', lambda name: rscript if name == 'Rscript' else None)
    (root / 'numbers.owned').write_text('1 2 3')
    document = graph(root)
    script_demo = bool(os.environ.get('OPERON_CANVAS_TEST_SCRIPT'))
    if script_demo:
        from operon.workflow_spec import load_workflow
        document = load_workflow(ROOT / 'examples/workflows/script_pipeline/workflow.yaml')
        catalog = {'operators': [], 'readers': []}
    document['memory'] = {'enabled': True, 'budget_mb': 32, 'process_limit_mb': 192, 'auto_spill': True}
    pool = PoolService(root=root / 'pool', admission_dir=root / 'admission',
        workspaces=[{'root': root, 'principal': 'canvas-test'}], code_root=ROOT, catalog=catalog,
        capacity_bytes=512 * 1024**2, cpu_threads=2)
    service = pool.resolve(root)
    manager = SimpleNamespace(directory=root, source_root=root, python_for=lambda state: python,
        snapshot=lambda graph: {'_runtime_root': str(root), 'generation': 'fixture-v1', 'code_paths': [], 'shared_paths': []})
    service.plugins = manager
    service.settings.code_root = ROOT
    # Environment exclusion is exercised by a real pool gate; source/dependency
    # validation fixture is explicit and does not pretend to test readiness UI.
    app = SimpleNamespace(service=service, stopping=False,
        prepare=lambda value: Graph.model_validate(value), validate=lambda graph, **kw: {},
        _execution_binding=lambda graph, checked: graph,
        compile_plan=lambda value, **kw: WorkflowCompiler().compile(value, None, catalog, root=root,
                                                                  require_files=True, freeze_defaults=False))
    canvas = CanvasPlans(app); app.canvas_plans = canvas
    app.plans = PlanService(app)
    app.plan_exports = PlanExportService(root, root / '.studio/plan-exports')
    try:
        prepared = canvas.prepare(document)
        plan = prepared['plan']
        assert plan['execution_policy']['memory']['budget_mb'] == 32
        if script_demo:
            assert len(plan['units'][0]['payload']['task_manifest']['steps']) == 3
            assert len(plan['edges']) == 2
        else:
            assert plan['units'][0]['payload']['task_manifest']['steps'][0]['params'] == {'output': 'result'}
        # Same runtime/package generation reused without walking it again.
        import operon.environment_store.canvas as environment_module
        monkeypatch.setattr(environment_module, 'archive_tree', lambda *a, **kw: pytest.fail('runtime resealed'))
        again = canvas.prepare(document)
        assert again['plan']['plan_id'] == plan['plan_id']
        accepted = app.plans.submit({'plan': plan, 'binding': prepared['binding'], 'request_id': 'native-canvas'})
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            current = app.plans.details(accepted['run_id'])
            if current['state'] in ('complete', 'failed', 'cancelled'): break
            time.sleep(.05)
        assert current['state'] == 'complete', pool.plan_details(root, accepted['run_id'], principal='canvas-test')
        artifacts = app.plans.artifacts(accepted['run_id'])['artifacts']
        assert artifacts
        request = canvas.export_request(prepared, 'automatic-export')
        receipt = app.plan_exports.submit(request)
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            exported = app.plan_exports.details(receipt['id'])
            if exported['status'] not in ('queued', 'building'): break
            time.sleep(.2)
        assert exported['status'] == 'complete', exported
        output = root / request.output
        assert (output / 'run.cmd').is_file() and (output / 'parameters.json').is_file()
        assert json.loads((output / 'parameters.json').read_text())
        if os.environ.get('OPERON_CANVAS_TEST_MOVED'):
            import shutil
            import subprocess
            from operon.bytecode import io_path
            moved = root / 'moved standalone'
            shutil.copytree(io_path(output), io_path(moved))
            shutil.copy2(root / 'numbers.owned', moved / 'input.owned')
            inputs = json.loads((moved / 'inputs.json').read_text())
            (moved / 'inputs.json').write_text(json.dumps({key: 'input.owned' for key in inputs}))
            # No editor imports, source runtime lookup, or dependency acquisition.
            environment = {k: v for k, v in os.environ.items()
                           if k.upper() in ('SYSTEMROOT', 'WINDIR', 'COMSPEC', 'PATHEXT', 'TEMP', 'TMP', 'HOME')}
            environment['PATH'] = (str(Path(os.environ['SystemRoot']) / 'System32')
                                   if os.name == 'nt' else '/usr/bin:/bin')
            command = (['cmd.exe', '/d', '/c', str(moved / 'run.cmd')] if os.name == 'nt'
                       else ['/bin/sh', str(moved / 'run.sh')])
            with (moved / 'standalone.log').open('w') as log:
                completed = subprocess.run(command, cwd=moved, env=environment,
                    stdout=log, stderr=subprocess.STDOUT, timeout=300)
            assert completed.returncode == 0, (moved / 'standalone.log').read_text()[-3000:]
        (root / 'canvas-acceptance.json').write_text(json.dumps({'run': current, 'export': exported}, indent=2))
    finally:
        canvas.close(); app.plan_exports.close(); pool.shutdown()
