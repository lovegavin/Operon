"""Dependency status must survive the remote snapshot hop."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402
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

def _dependency_studio(tmp_path, monkeypatch):
    """A desktop app whose manifest declares one installed requirement and one wheel."""
    from operon import environments as environments_module
    from src.web.api import create_app
    from src.web.service import Settings

    root_dir = Path(__file__).resolve().parents[1]
    entry = {
        'python': '3.11',
        'requirements': ['alpha==1.0'],
        'pip_wheels': ['torch-geometric==2.4.0'],
    }
    environments_root = tmp_path / 'environments'
    location = environments_root / 'toy'
    (location / 'bin').mkdir(parents=True, exist_ok=True)
    interpreter = location / 'bin' / 'python'
    interpreter.write_text('#!/bin/sh\nexit 0\n', encoding='utf-8')
    interpreter.chmod(0o755)
    site = location / 'Lib' / 'site-packages'
    site.mkdir(parents=True, exist_ok=True)
    (site / 'alpha-1.0.dist-info').mkdir(exist_ok=True)
    receipt = {'spec_sha256': environment_install.spec_sha256(entry)}
    (location / 'receipt.json').write_text(json.dumps(receipt), encoding='utf-8')
    monkeypatch.setenv('OPERON_ENVIRONMENTS_ROOT', str(environments_root))
    monkeypatch.setattr(environments_module, 'load', lambda root=None: {'toy': entry})
    # The panel caches dependency counts for 20 s; the assertions below must see
    # the metadata the fake pip install writes while the test is still running.
    monkeypatch.setattr(environment_install, '_DEPENDENCY_TTL', 0.0)
    return create_app(Settings(tmp_path, tmp_path / 'studio', root_dir / 'frontend/dist',
                               testing=True, code_root=root_dir, desktop=True))


def test_dependency_job_reaches_a_terminal_state_and_installs(tmp_path, monkeypatch):
    commands = []
    site = tmp_path / 'environments' / 'toy' / 'Lib' / 'site-packages'

    def fake_run(command, **kwargs):
        commands.append(list(command))
        (site / 'torch_geometric-2.4.0.dist-info').mkdir(parents=True, exist_ok=True)
        return 0

    monkeypatch.setattr(environment_install, '_run', fake_run)
    with TestClient(_dependency_studio(tmp_path, monkeypatch)) as client:
        client.headers['X-Studio-Token'] = client.get('/api/bootstrap').json()['token']
        before = client.get('/api/environments').json()['environments']['toy']
        assert before['dependency_total'] == 2
        assert before['dependency_installed'] == 1  # the wheel is still missing
        response = client.post('/api/environments/toy/dependencies/download',
                               json={'name': 'torch-geometric==2.4.0'})
        assert response.status_code == 200, response.text
        job_id = response.json()['job']
        # The desktop polls this route for environment jobs too; it used to 500.
        detail = client.get(f'/api/jobs/{job_id}')
        assert detail.status_code == 200, detail.text
        assert 'status' in detail.json()
        for _ in range(500):
            body = detail.json()
            if body['status'] in {'complete', 'failed', 'cancelled'}:
                break
            time.sleep(0.02)
            detail = client.get(f'/api/jobs/{job_id}')
        body = detail.json()
        assert body['status'] == 'complete', body
        assert not body.get('error')

    assert commands, 'the dependency worker never invoked pip'
    assert str(commands[-1][0]) == str(tmp_path / 'environments' / 'toy' / 'bin' / 'python')
    assert '--only-binary=:all:' in commands[-1]
    assert commands[-1][-1] == 'torch-geometric==2.4.0'

    # Counts are cached per app instance; a fresh app is what an operator sees
    # after reloading the window once the job has finished.
    environment_install._dependency_cache.clear()
    with TestClient(_dependency_studio(tmp_path, monkeypatch)) as client:
        client.headers['X-Studio-Token'] = client.get('/api/bootstrap').json()['token']
        items = client.get('/api/environments').json()['environments']
        assert items['toy']['dependency_total'] == 2
        assert items['toy']['dependency_installed'] == 2


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
