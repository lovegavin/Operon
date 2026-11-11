"""Shared application submission: engine journal first, compatibility files retained."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import threading
import types

import pytest

from operon.application import Application
from operon.documents import CommandError
from operon.engine.contracts import CommitOutcomeUnknown
from src.web.service import Settings

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def application(tmp_path, monkeypatch):
    monkeypatch.setenv('OPERON_ADMISSION_DIR', str(tmp_path / 'admission'))
    monkeypatch.setenv('OPERON_ENGINE_DIR', str(tmp_path / 'engine'))
    app = Application(Settings(tmp_path, tmp_path / '.studio', tmp_path / 'ui', testing=True,
                                code_root=ROOT))
    launched = []
    lock = threading.Lock()
    fake = {'id': 'job-fixture', 'status': 'queued', 'name': 'fixture'}
    monkeypatch.setattr(app.jobs, '_prepare_submission',
                        lambda graph: types.SimpleNamespace(runtime={}))
    monkeypatch.setattr(app.jobs, 'details', lambda key: {**fake, 'id': key})

    def launch(prepared, *, validated=False):
        with lock:
            launched.append(prepared)
        return dict(fake)

    monkeypatch.setattr(app.jobs, '_launch', launch)
    yield app, launched
    app.shutdown()


def test_concurrent_identical_submissions_have_one_durable_identity(application):
    app, launched = application
    payload = {'graph': {'schema_version': 2, 'name': 'fixture', 'nodes': [], 'edges': []},
               'request_id': 'shared-request'}
    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(lambda _: app.jobs._submit(deepcopy(payload)), range(24)))
    assert len(launched) == 1
    assert len({item['id'] for item in results}) == 1
    assert len({item['request_id'] for item in results}) == 1
    assert sum(1 for item in results if not item.get('reused')) == 1
    record = app.service.engine.journal.request(
        __import__('hashlib').sha256(b'shared-request').hexdigest())
    assert record['state'] == 'submitted' and record['run_id'] == 'job-fixture'
    receipts = list((app.requests).glob('*.json'))
    assert len(receipts) == 1
    assert json.loads(receipts[0].read_text(encoding='utf-8'))['job_id'] == 'job-fixture'


def test_commit_outcome_unknown_queries_but_never_relaunches(application, monkeypatch):
    app, launched = application
    journal = app.service.engine.journal
    original = journal.claim

    def lost_after_commit(*args, **kwargs):
        original(*args, **kwargs)
        raise CommitOutcomeUnknown('commit acknowledgement lost')

    monkeypatch.setattr(journal, 'claim', lost_after_commit)
    payload = {'graph': {'schema_version': 2, 'name': 'unknown-commit', 'nodes': [], 'edges': []},
               'request_id': 'unknown-commit'}
    with pytest.raises(CommandError) as error:
        app.jobs._submit(payload)
    assert error.value.code == 'submission_uncertain'
    assert launched == []
    record = journal.request(__import__('hashlib').sha256(b'unknown-commit').hexdigest())
    assert record is not None and record['state'] == 'claimed'


def test_definite_claim_failure_returns_engine_unavailable_without_launch(application, monkeypatch):
    app, launched = application
    journal = app.service.engine.journal
    original = journal.claim

    def unavailable(*args, **kwargs):
        raise sqlite3.OperationalError('database is temporarily locked')

    monkeypatch.setattr(journal, 'claim', unavailable)
    payload = {'graph': {'schema_version': 2, 'name': 'unavailable', 'nodes': [], 'edges': []},
               'request_id': 'definite-failure'}
    with pytest.raises(CommandError) as error:
        app.jobs._submit(payload)
    assert error.value.code == 'engine_unavailable'
    assert launched == []
    monkeypatch.setattr(journal, 'claim', original)
    result = app.jobs._submit(payload)
    assert result['id'] == 'job-fixture'
    assert len(launched) == 1


def test_request_index_unavailable_without_durable_evidence_refuses_to_launch(application, monkeypatch):
    app, launched = application
    journal = app.service.engine.journal
    monkeypatch.setattr(journal, 'request', lambda key: (_ for _ in ()).throw(
        sqlite3.OperationalError('index unavailable')))
    payload = {'graph': {'schema_version': 2, 'name': 'no-index', 'nodes': [], 'edges': []},
               'request_id': 'no-index'}
    with pytest.raises(CommandError) as error:
        app.jobs._submit(payload)
    assert error.value.code == 'submission_uncertain'
    assert launched == []


def test_request_index_unavailable_with_existing_receipt_returns_the_job(application, monkeypatch):
    app, launched = application
    payload = {'graph': {'schema_version': 2, 'name': 'existing', 'nodes': [], 'edges': []},
               'request_id': 'existing-receipt'}
    first = app.jobs._submit(payload)
    assert first['id'] == 'job-fixture' and len(launched) == 1
    journal = app.service.engine.journal
    monkeypatch.setattr(journal, 'request', lambda key: (_ for _ in ()).throw(
        sqlite3.OperationalError('index unavailable')))
    retried = app.jobs._submit(payload)
    assert retried['id'] == first['id'] and retried['reused']
    assert len(launched) == 1


def test_different_graph_for_the_same_request_is_a_conflict(application):
    app, launched = application
    first = {'graph': {'schema_version': 2, 'name': 'one', 'nodes': [], 'edges': []},
             'request_id': 'conflict'}
    app.jobs._submit(first)
    second = deepcopy(first)
    second['graph']['name'] = 'two'
    with pytest.raises(CommandError) as error:
        app.jobs._submit(second)
    assert error.value.code == 'idempotency_conflict'
    assert len(launched) == 1


def test_unknown_launch_result_is_never_relaunched(application, monkeypatch):
    app, launched = application

    def lost(prepared, *, validated=False):
        launched.append(prepared)
        raise OSError('transport vanished after acceptance')

    monkeypatch.setattr(app.jobs, '_launch', lost)
    payload = {'graph': {'schema_version': 2, 'name': 'lost', 'nodes': [], 'edges': []},
               'request_id': 'lost-result'}
    with pytest.raises(OSError):
        app.jobs._submit(payload)
    with pytest.raises(CommandError) as error:
        app.jobs._submit(payload)
    assert error.value.code == 'submission_uncertain'
    assert len(launched) == 1


def test_recovered_job_evidence_binds_the_durable_request(application, monkeypatch):
    app, launched = application
    original = app.jobs._launch

    def accepted_then_lost(prepared, *, validated=False):
        result = original(prepared, validated=validated)
        raise OSError('response lost after launch')

    record = {'id': 'job-recovered', 'name': 'fixture', 'status': 'queued', 'created_at': 'now',
              'finished_at': None, 'error': None, 'order': [], 'allocation': {},
              'progress': {'completed': 0, 'total': 0, 'percent': 0},
              'graph': {'runtime': {'submission_key': 'placeholder'}}}
    folder = app.service.jobs_dir / 'job-recovered'
    folder.mkdir(parents=True)
    monkeypatch.setattr(app.jobs, '_launch', accepted_then_lost)
    payload = {'graph': {'schema_version': 2, 'name': 'recovered', 'nodes': [], 'edges': []},
               'request_id': 'recover-me'}
    import hashlib
    key = hashlib.sha256(b'recover-me').hexdigest()
    record['graph']['runtime']['submission_key'] = key
    (folder / 'job.json').write_text(json.dumps(record), encoding='utf-8')
    monkeypatch.setattr(app.jobs, 'details', lambda value: {'id': value, 'status': 'queued'})
    result = app.jobs._submit(payload)
    assert result['id'] == 'job-recovered' and result['reused']
    assert app.service.engine.journal.request(key)['run_id'] == 'job-recovered'
