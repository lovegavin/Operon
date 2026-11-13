"""Per-job operator provenance and portable run skeletons."""
from copy import deepcopy
import json
from pathlib import Path
import time

import pytest

from src.task import STEPS
from src.task.operator_catalog import build_catalog
from src.web.admission import HostAdmission, MIB
from src.web.models import Graph
from src.web.service import JobService, Settings

ROOT = Path(__file__).resolve().parents[1]
FAKE_WORKER = '''import json,os,sys,time
from pathlib import Path
task=Path(sys.argv[1]); output=task/'output'; output.mkdir()
(output/'started.json').write_text(json.dumps({'pid':os.getpid()}))
while not (task/'finish').exists():
    if (task/'cancel.requested').exists(): sys.exit(1)
    time.sleep(.03)
(output/'run_summary.json').write_text(json.dumps({'status':'complete'}))
'''


def wait_until(check, timeout=20):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = check()
        if result:
            return result
        time.sleep(.05)
    pytest.fail('Timed out waiting for the worker')


@pytest.fixture
def service(tmp_path, monkeypatch):
    import src.web.service as module
    monkeypatch.setattr(module, 'HostAdmission',
                        lambda path: HostAdmission(path, available_bytes=2048 * MIB, cpu_threads=2))
    code = tmp_path / 'code'
    (code / 'scripts').mkdir(parents=True)
    (code / 'scripts/run.py').write_text(FAKE_WORKER, encoding='utf-8')
    settings = Settings(tmp_path, tmp_path / 's', ROOT / 'frontend/dist', testing=True, code_root=code)
    result = JobService(settings, build_catalog(STEPS))
    yield result
    result.shutdown()


def graph_for(service):
    return Graph.model_validate(deepcopy(service.demo))


def read_run(service, job):
    path = service._run_skeleton_dir(job['graph'], job['id']) / 'run.json'
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return None


def finish(service, job):
    (service.jobs_dir / job['id'] / 'finish').touch()
    wait_until(lambda: service.details(job['id'])['logs_complete'])
    return service.details(job['id'])


def test_provenance_contains_only_used_operators_with_library(service):
    state = service.plugins.state()
    for descriptor in state['descriptors']:
        descriptor['library'] = 'v0.1.0'
    service.plugins.snapshot = lambda graph: state

    job = service.launch(graph_for(service))
    finish(service, job)

    stored = json.loads((service.jobs_dir / job['id'] / 'job.json').read_text(encoding='utf-8'))
    plugins = stored['plugins']
    used = {'missing', 'pca', 'describe'}
    assert set(plugins['operators']) == used
    assert plugins['libraries'] == ['v0.1.0']
    for entry in plugins['operators'].values():
        assert entry['library'] == 'v0.1.0'
        assert entry['package'] in {'operon-core', 'operon-genetics'}
        assert entry['version'] == '1.0.0'
        assert entry['code_sha']
    unused = next(item['id'] for item in state['descriptors'] if item['id'] not in used)
    assert unused not in plugins['operators']


def test_provenance_walks_route_subgraphs(service):
    state = service.plugins.state()
    for descriptor in state['descriptors']:
        descriptor['library'] = 'fork-v0.0.0'
    inner = Graph.model_validate({
        'schema_version': 2, 'name': 'inner', 'base_dir': '.',
        'nodes': [{'id': 'pca', 'kind': 'operator', 'operator': 'pca',
                   'position': {'x': 0, 'y': 0}}],
        'edges': [],
    })
    outer = Graph.model_validate({
        'schema_version': 2, 'name': 'outer', 'base_dir': '.',
        'nodes': [
            {'id': 'route_1', 'kind': 'route', 'position': {'x': 0, 'y': 0},
             'route': {'id': 'route_0123456789ab', 'version': 1, 'name': 'inner',
                       'graph': inner.model_dump(mode='json')}},
            {'id': 'describe', 'kind': 'operator', 'operator': 'describe',
             'position': {'x': 1, 'y': 1}},
        ],
        'edges': [],
    })
    libraries, operators = service._operator_provenance(outer, state)
    assert set(operators) == {'pca', 'describe'}
    assert libraries == ['fork-v0.0.0']


def test_completed_job_has_a_run_skeleton(service):
    job = service.launch(graph_for(service))
    detail = finish(service, job)
    assert detail['status'] == 'complete'
    wait_until(lambda: (read_run(service, job) or {}).get('status') == 'complete')

    run_dir = service.root / 'runs' / job['id']
    for name in ('run.json', 'job.json', 'graph.json', 'parameters.json',
                 'plugins.lock.json', 'logs/README.txt'):
        assert (run_dir / name).is_file(), name

    run = json.loads((run_dir / 'run.json').read_text(encoding='utf-8'))
    assert run['job_id'] == job['id']
    assert run['task'] == detail['name']
    assert run['status'] == 'complete'
    assert run['started_at'] and run['finished_at']
    assert run['library'] == []
    assert set(run['operators']) == {'missing', 'pca', 'describe'}
    assert 'missing' not in run
    assert (service.root / run['results']).resolve() == Path(detail['output_dir']).resolve()
    assert (service.root / run['metadata']).resolve() == (service.jobs_dir / job['id']).resolve()
    readme = (run_dir / 'logs' / 'README.txt').read_text(encoding='utf-8')
    assert 'console.log' in readme and 'Full logs remain' in readme


def test_relative_and_absolute_base_dirs_resolve_under_base(service, tmp_path):
    relative = graph_for(service)
    relative.base_dir = 'tasks'
    relative.nodes[0].source.path = str(service.assets_dir / 'expression-demo.csv')
    relative_job = service.launch(relative)
    finish(service, relative_job)
    wait_until(lambda: read_run(service, relative_job) is not None)
    relative_run = tmp_path / 'tasks' / 'runs' / relative_job['id']
    assert service._run_skeleton_dir(relative, relative_job['id']) == relative_run.resolve()
    assert (relative_run / 'run.json').is_file()

    absolute_base = tmp_path / 'elsewhere'
    absolute = graph_for(service)
    absolute.base_dir = str(absolute_base)
    absolute.nodes[0].source.path = str(service.assets_dir / 'expression-demo.csv')
    absolute_job = service.launch(absolute)
    absolute_run = absolute_base / 'runs' / absolute_job['id']
    assert service._run_skeleton_dir(absolute, absolute_job['id']) == absolute_run.resolve()
    wait_until(lambda: (absolute_run / 'run.json').is_file())
    finish(service, absolute_job)

    original = service.settings.code_root
    service.settings.code_root = ROOT
    try:
        assert Path(service._job_output_dir(relative, 'probe')) == (tmp_path / 'tasks' / 'results' / 'probe').resolve()
        assert Path(service._job_output_dir(absolute, 'probe')) == (absolute_base / 'results' / 'probe').resolve()
    finally:
        service.settings.code_root = original


def test_unwritable_skeleton_does_not_fail_submission(service, tmp_path):
    blocker = tmp_path / 'runs'
    blocker.write_text('not a directory', encoding='utf-8')

    job = service.launch(graph_for(service))
    assert job['status'] in {'queued', 'running', 'preparing'}
    assert (service.jobs_dir / job['id'] / 'job.json').is_file()
    assert job['error'] is None
    wait_until(lambda: service.run_skeleton_error)
    assert 'Error' in service.run_skeleton_error or 'error' in service.run_skeleton_error
    assert blocker.is_file()

    assert finish(service, job)['status'] == 'complete'
