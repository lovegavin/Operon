"""The daemon must stay alive while a job of this workspace is still running."""
import threading
from types import SimpleNamespace

from operon.remote.server import RemoteService


def service(jobs):
    return SimpleNamespace(processes=[], threads=[], jobs=jobs, remotes=SimpleNamespace(state={'jobs': {}}))


def daemon(jobs):
    value = RemoteService.__new__(RemoteService)
    value.service = service(jobs)
    value.application = SimpleNamespace(canvas_plans=None, plan_exports=None, service=value.service)
    value.handshake = None
    value.transfers = None
    value.transport_leases = {}
    value.transport_active = {}
    value.lease_lock = threading.RLock()
    return value


def test_idle_daemon_has_no_durable_work():
    assert daemon({}).alive() is False


def test_running_job_keeps_the_daemon_alive():
    value = daemon({'job-1': {'id': 'job-1', 'status': 'running'}})
    assert value.alive() is True


def test_finished_jobs_do_not_keep_the_daemon_alive():
    value = daemon({'job-1': {'id': 'job-1', 'status': 'complete'},
                    'job-2': {'id': 'job-2', 'status': 'failed'}})
    assert value.alive() is False


def test_every_queued_state_keeps_the_daemon_alive():
    for status in ('queued', 'preparing', 'uploading', 'running', 'waiting_connection'):
        assert daemon({'job-1': {'status': status}}).alive() is True, status
