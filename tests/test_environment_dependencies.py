"""Dependency status must survive the remote snapshot hop."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from operon import environment_install  # noqa: E402
from operon.remote import server as agent  # noqa: E402


def _environment(tmp_path: Path) -> Path:
    location = tmp_path / 'env'
    site = location / 'Lib' / 'site-packages'
    site.mkdir(parents=True)
    (site / 'pandas-2.2.3.dist-info').mkdir()
    (site / 'numpy-2.2.6.dist-info').mkdir()
    (site / 'numpy').mkdir()
    (site / 'numpy' / '__init__.py').write_text('', encoding='utf-8')
    scripts = location / 'Scripts'
    scripts.mkdir()
    (scripts / 'samtools.exe').write_bytes(b'')
    meta = location / 'conda-meta'
    meta.mkdir()
    (meta / 'blast-2.16.0-h1234.json').write_text('{}', encoding='utf-8')
    return location


def test_dependency_status_counts_every_kind(tmp_path: Path) -> None:
    location = _environment(tmp_path)
    entry = {
        'requirements': ['pandas==2.2.3', 'scipy>=1.14'],
        'conda_packages': ['blast=2.16.0'],
        'imports': ['numpy'],
        'binaries': ['samtools'],
    }
    installed, total, rows = environment_install.dependency_status(entry, str(location))
    flags = {row['name']: row['installed'] for row in rows}
    assert total == len(rows) == 5
    assert installed == 4
    assert flags['pandas==2.2.3'] is True
    assert flags['scipy>=1.14'] is False
    assert flags['blast=2.16.0'] is True
    assert flags['numpy'] is True
    assert flags['samtools'] is True


def test_dependency_status_without_a_location_reports_zero(tmp_path: Path) -> None:
    entry = {'requirements': ['pandas==2.2.3']}
    installed, total, rows = environment_install.dependency_status(entry, '')
    assert (installed, total) == (0, 1)
    assert rows[0]['installed'] is False


def test_remote_snapshot_carries_dependency_counts(tmp_path: Path, monkeypatch) -> None:
    location = _environment(tmp_path)

    class Plugins:
        source_root = None

    class Service:
        plugins = Plugins()
        catalog = {}
        directory = str(tmp_path)

    plan = {
        'core': {'name': 'core', 'status': 'ready', 'location': str(location)},
        'esm2': {'name': 'esm2', 'status': 'missing', 'location': ''},
    }
    from operon import environments as environments_module

    monkeypatch.setattr(agent, '_environment_plan', lambda service: (tmp_path, None, plan))
    monkeypatch.setattr(
        environments_module,
        'load',
        lambda root=None: {
            'core': {'requirements': ['pandas==2.2.3']},
            'esm2': {'requirements': ['torch==2.9']},
        },
    )
    snapshot = agent.environment_snapshot(Service())
    core = snapshot['environments']['core']
    esm2 = snapshot['environments']['esm2']
    assert (core['dependency_installed'], core['dependency_total']) == (1, 1)
    assert core['dependencies'][0]['installed'] is True
    assert (esm2['dependency_installed'], esm2['dependency_total']) == (0, 1)

def test_snapshot_reports_a_failure_instead_of_raising(tmp_path: Path, monkeypatch) -> None:
    class Plugins:
        source_root = None

    class Service:
        plugins = Plugins()
        catalog = {}
        directory = str(tmp_path)

    def boom(service):
        raise RuntimeError('index is unreadable')

    monkeypatch.setattr(agent, '_environment_plan', boom)
    snapshot = agent.environment_snapshot(Service())
    assert snapshot['environments'] == {}
    assert 'index is unreadable' in snapshot['error']
