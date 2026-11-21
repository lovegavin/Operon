"""A job left in 'preparing' by a restart must not reserve its slot forever."""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.web.service import JobService, Settings

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def service(tmp_path, monkeypatch):
    from src.task import STEPS
    from src.task.operator_catalog import build_catalog
    from src.web.admission import HostAdmission
    import src.web.service as module

    monkeypatch.setattr(module, 'HostAdmission', lambda path: HostAdmission(
        path, available_bytes=2048 * 1024 * 1024, cpu_threads=2))
    code = tmp_path / 'code'
    (code / 'scripts').mkdir(parents=True)
    (code / 'scripts/run.py').write_text('', encoding='utf-8')
    settings = Settings(tmp_path, tmp_path / 's', ROOT / 'frontend/dist', testing=True, code_root=code)
    result = JobService(settings, build_catalog(STEPS))
    yield result
    result.shutdown()


def _record(service, key, status, owner):
    directory = service.jobs_dir / key
    directory.mkdir(parents=True, exist_ok=True)
    record = directory / 'job.json'
    value = {
        'id': key,
        'name': 'p6 demo',
        'status': status,
        'owner': owner,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'finished_at': None,
        'logs_complete': False,
        'progress': {'phase': status, 'completed': 0, 'total': 1, 'percent': 0},
    }
    record.write_text(json.dumps(value), encoding='utf-8')
    service.jobs[key] = dict(value)
    return record


def test_a_preparing_job_of_a_dead_launcher_is_finished_as_interrupted(service):
    record = _record(service, 'exec-abc', 'preparing', {'pid': 99999999, 'created': 1.0})

    service._refresh_jobs()

    refreshed = json.loads(record.read_text(encoding='utf-8'))
    assert refreshed['status'] == 'interrupted'
    assert refreshed['finished_at'] is not None
    assert refreshed['logs_complete'] is True
    assert '未完成' in refreshed['error']


def test_a_preparing_job_of_a_live_launcher_is_left_alone(service):
    record = _record(service, 'exec-live', 'preparing', dict(service.owner))

    service._refresh_jobs()

    refreshed = json.loads(record.read_text(encoding='utf-8'))
    assert refreshed['status'] == 'preparing'
