"""Quarantined attempts whose worker is gone must release their lease."""
from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone

import psutil

from operon.engine.coordinator import Coordinator


class _Recorder:
    def __init__(self):
        self.failures = []
        self.diagnostics = []

    def _fail_attempt(self, attempt_id, **kwargs):
        self.failures.append((attempt_id, kwargs))

    def _diagnose(self, event, **kwargs):
        self.diagnostics.append((event, kwargs))


def _attempt(process, started_at):
    return {'id': 'attempt-1', 'process': process, 'started_at': started_at.isoformat()}


def test_dead_quarantined_worker_is_abandoned():
    recorder = _Recorder()
    attempt = _attempt({'pid': 999_999_999, 'created': time.time() - 5, 'boot_id': None},
                       datetime.now(timezone.utc) - timedelta(minutes=10))
    assert Coordinator._abandon_quarantined(recorder, attempt) is True
    assert recorder.failures and recorder.failures[0][1]['error_code'] == 'recovery_abandoned'
    assert recorder.failures[0][1]['release'] is True
    assert recorder.failures[0][1]['retry'] is False


def test_live_quarantined_worker_is_kept():
    recorder = _Recorder()
    created = psutil.Process(os.getpid()).create_time()
    attempt = _attempt({'pid': os.getpid(), 'created': created, 'boot_id': None},
                       datetime.now(timezone.utc) - timedelta(minutes=10))
    assert Coordinator._abandon_quarantined(recorder, attempt) is False
    assert recorder.failures == []


def test_fresh_quarantine_is_not_abandoned():
    recorder = _Recorder()
    attempt = _attempt({'pid': 999_999_999, 'created': time.time() - 5, 'boot_id': None},
                       datetime.now(timezone.utc))
    assert Coordinator._abandon_quarantined(recorder, attempt) is False
    assert recorder.failures == []


def test_quarantine_without_process_identity_is_kept():
    recorder = _Recorder()
    attempt = _attempt({}, datetime.now(timezone.utc) - timedelta(minutes=10))
    assert Coordinator._abandon_quarantined(recorder, attempt) is False
    assert recorder.failures == []
