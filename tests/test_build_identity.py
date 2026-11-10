import copy
import io
from pathlib import Path
import tarfile

from operon.build_identity import build_identity, matches
from operon.remote.library import changes
from operon.remote.provision import source_archive


ROOT = Path(__file__).resolve().parents[1]


def archive_identity():
    identity = build_identity(ROOT)
    data = source_archive(ROOT)
    import tempfile
    with tempfile.TemporaryDirectory() as temporary:
        with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
            archive.extractall(temporary, filter='data')
        remote = build_identity(Path(temporary), source_sha256=identity['application']['source_sha256'])
    return identity, remote


def test_identity_is_reproducible_after_archive_transport():
    local, remote = archive_identity()
    assert local['build_id'] == remote['build_id']
    assert local['library']['bundle_sha256'] == remote['library']['bundle_sha256']
    assert matches(local, remote)
    broken = copy.deepcopy(remote)
    broken['library']['bundle_sha256'] = '0' * 64
    assert not matches(local, broken)


def test_changes_reports_same_identity_with_new_implementation():
    def entry(sha):
        return {'id': 'operon.alpha', 'kind': 'operator', 'title': 'Alpha', 'version': '1',
                'code_sha': 'code', 'declaration_sha': 'decl',
                'implementation': {'version': '1', 'sha256': sha}}
    local = {'packages': [{'name': 'operon-core', 'version': '1', 'entries': [entry('a')]}]}
    remote = {'packages': [{'name': 'operon-core', 'version': '1', 'entries': [entry('b')]}]}
    found = changes(local, remote)
    assert [item['id'] for item in found] == ['operon.alpha']
    assert found[0]['previous']['sha256'] == 'a'
    assert found[0]['current']['sha256'] == 'b'
    assert changes(local, local) == []
