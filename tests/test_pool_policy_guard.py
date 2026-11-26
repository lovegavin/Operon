"""The shared pool must not treat crashed jobs as active work."""
from __future__ import annotations

from types import SimpleNamespace

from operon import pool_service


def _service(jobs):
    return SimpleNamespace(jobs=jobs)


def test_recovery_required_jobs_do_not_block_a_new_build():
    service = _service({"old": {"status": "recovery_required"}})
    assert pool_service._active_jobs(service) == []


def test_queued_jobs_still_count_as_active(monkeypatch):
    service = _service({"waiting": {"status": "queued"}})
    assert len(pool_service._active_jobs(service)) == 1


def test_running_job_without_a_live_tree_is_ignored(monkeypatch):
    monkeypatch.setattr("operon.engine.executor.identity_for_job", lambda service, job_id: {"pid": 1})
    monkeypatch.setattr("operon.engine.executor.identity_alive", lambda identity: False)
    service = _service({"crashed": {"status": "running"}})
    assert pool_service._active_jobs(service) == []


def test_running_job_with_a_live_tree_blocks_the_change(monkeypatch):
    monkeypatch.setattr("operon.engine.executor.identity_for_job", lambda service, job_id: {"pid": 1})
    monkeypatch.setattr("operon.engine.executor.identity_alive", lambda identity: True)
    service = _service({"running": {"status": "running"}})
    assert len(pool_service._active_jobs(service)) == 1


def test_unreadable_identity_keeps_the_job_active(monkeypatch):
    def boom(service, job_id):
        raise RuntimeError("unreadable")

    monkeypatch.setattr("operon.engine.executor.identity_for_job", boom)
    service = _service({"running": {"status": "running"}})
    assert len(pool_service._active_jobs(service)) == 1


def test_unfinished_logs_keep_a_completed_job_active():
    service = _service({"done": {"status": "complete", "logs_complete": False}})
    assert len(pool_service._active_jobs(service)) == 1
