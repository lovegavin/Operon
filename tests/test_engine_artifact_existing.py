"""Existing-payload artifacts are references plus verifiable content."""
from pathlib import Path

from biopipe.engine.artifacts import ArtifactCommitter


def attempt():
    return {'id': 'attempt-existing', 'fence': 7}


def test_existing_payload_verification_detects_changes(tmp_path):
    source = tmp_path / 'output'
    source.mkdir()
    (source / 'run_summary.json').write_text('{"status":"complete"}', encoding='utf-8')
    (source / 'table.csv').write_text('a,b\n1,2\n', encoding='utf-8')
    committer = ArtifactCommitter(tmp_path / 'artifacts')
    receipt = committer.commit_existing(
        attempt=attempt(), unit={'id': 'main', 'run_id': 'run-1'}, fence=7,
        source_root=source, files=['run_summary.json', 'table.csv'], run_id='run-1')
    assert receipt['location'] == str(source)
    assert committer.verify_existing(receipt)['valid'] is True

    (source / 'table.csv').write_text('a,b\n1,3\n', encoding='utf-8')
    changed = committer.verify_existing(receipt)
    assert changed['valid'] is False
    assert any('content changed' in item for item in changed['errors'])

    (source / 'table.csv').write_text('a,b\n1,2\n', encoding='utf-8')
    (source / 'extra.txt').write_text('not part of the manifest', encoding='utf-8')
    assert committer.verify_existing(receipt)['valid'] is False

    (source / 'extra.txt').unlink()
    (source / 'table.csv').unlink()
    missing = committer.verify_existing(receipt)
    assert missing['valid'] is False
    assert any('missing' in item for item in missing['errors'])


def test_commit_existing_refuses_links_and_empty_payload(tmp_path):
    source = tmp_path / 'output'; source.mkdir()
    committer = ArtifactCommitter(tmp_path / 'artifacts')
    try:
        committer.commit_existing(attempt=attempt(), unit={'id': 'main'}, fence=7,
                                  source_root=source, files=[], run_id='run-2')
    except Exception as exc:  # noqa: BLE001 - stable artifact error
        assert getattr(exc, 'code', '') == 'corrupt_artifact'
    else:
        raise AssertionError('empty output was published')

def test_executor_never_acknowledges_completion_while_tree_is_alive(tmp_path):
    from biopipe.engine.executor import ExecutionContext, JobServiceExecutor
    class FakeService:
        def details(self, key):
            return {'status': 'complete', 'logs_complete': True, 'tree_exited': False}
        def require(self, key):
            return {'worker': {'pid': 1, 'created': 1.0}}
    context = ExecutionContext(run={'id': 'run-tree'}, unit={'id': 'u'},
                               attempt={'id': 'a', 'fence': 1}, directory=tmp_path,
                               environment={}, plan={})
    result = JobServiceExecutor(FakeService()).poll(context)
    assert result.state == 'running'
    assert result.tree_alive is True
