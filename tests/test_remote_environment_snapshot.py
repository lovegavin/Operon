"""The remote snapshot must report required dependencies apart from optional ones."""

from operon import environment_install
from operon.remote import server


def test_a_ready_environment_does_not_count_an_optional_gap_as_missing(monkeypatch):
    rows = [
        {'kind': 'requirements', 'name': 'numpy>=1.26', 'installed': True},
        {'kind': 'best_effort', 'name': 'vina==1.2.5', 'optional': True, 'installed': False},
    ]

    monkeypatch.setattr(server, '_environment_plan',
                        lambda service: ('/tmp/envs', {}, {'core': {'name': 'core', 'status': 'ready',
                                                                    'location': '/tmp/envs/core'}}))
    monkeypatch.setattr(server, 'resource_readiness', lambda declared, name: (0, 0, []))
    monkeypatch.setattr(environment_install, 'dependency_status', lambda entry, location: (1, 2, rows))

    snapshot = server.environment_snapshot(object())
    core = snapshot['environments']['core']
    assert core['dependency_total'] == 1
    assert core['dependency_installed'] == 1
    assert core['optional_total'] == 1
    assert core['optional_installed'] == 0
    assert core['optional_missing'] == ['vina==1.2.5']
    assert core['status'] == 'ready'
