"""A queued install that still owns a worker must not be reaped by age."""
import json

from operon import environment_install


def _queue(root, name, stamp):
    path = environment_install.progress_path(name, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'phase': 'queued', 'updated_at': stamp}), encoding='utf-8')


def test_a_stale_queue_entry_is_reported_as_interrupted(tmp_path):
    _queue(tmp_path, 'queue', '2000-01-01T00:00:00Z')
    message = environment_install.reap_stale('queue', tmp_path)
    assert message == '上次安装已中断（安装进程已退出），请重新准备该环境。'
    assert environment_install.read_progress('queue', tmp_path)['phase'] == 'failed'


def test_a_queue_entry_with_a_live_job_survives_the_age_check(tmp_path):
    _queue(tmp_path, 'queue', '2000-01-01T00:00:00Z')
    assert environment_install.reap_stale('queue', tmp_path, alive=True) == ''
    assert environment_install.read_progress('queue', tmp_path)['phase'] == 'queued'
