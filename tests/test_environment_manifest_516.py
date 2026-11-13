import json
from pathlib import Path
from unittest import mock

import pytest

from operon import environments, library_install
from operon.plugins import PluginManager

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / 'build/lib512/operon-library-main-v0.1.0.operon-library.zip'
FORK = ROOT / 'build/lib512/operon-library-fork1-v0.0.0.operon-library.zip'


def manager(tmp_path):
    return PluginManager(tmp_path / 'data', library_root=tmp_path / 'library')


def test_install_persists_and_composes_environments(tmp_path):
    plugins = manager(tmp_path)
    result = library_install.install_library(plugins, MAIN)
    assert result['library'] == 'main-v0.1.0'
    root_manifest = tmp_path / 'library/environments.json'
    assert root_manifest.is_file()
    declared = json.loads(root_manifest.read_text(encoding='utf-8'))['environments']
    assert set(declared) == {'antifold', 'boltz', 'esm3', 'openmm81'}
    branch = tmp_path / 'library/libraries/main-v0.1.0/environments.json'
    assert branch.is_file()


def test_fork_union_and_uninstall_recompose(tmp_path):
    plugins = manager(tmp_path)
    library_install.install_library(plugins, MAIN)
    library_install.install_library(plugins, FORK)
    declared = json.loads((tmp_path / 'library/environments.json').read_text())['environments']
    assert set(declared) == {'antifold', 'boltz', 'esm3', 'openmm81'}
    library_install.uninstall_library(plugins, 'main-v0.1.0')
    assert json.loads((tmp_path / 'library/environments.json').read_text())['environments'] == {}


def test_manifest_path_prefers_installed_library(tmp_path):
    plugins = manager(tmp_path)
    library_install.install_library(plugins, MAIN)
    with mock.patch('operon.installation.library_root', return_value=tmp_path / 'library'):
        assert environments.manifest_path(None) == tmp_path / 'library/environments.json'
        assert environments.manifest_path('None') == tmp_path / 'library/environments.json'
        assert environments.manifest_path('') == tmp_path / 'library/environments.json'
        assert len(environments.load('None')) == 4


def test_ensure_environments_backfills_archives(tmp_path):
    libraries = tmp_path / 'library/libraries/main-v0.1.0'
    libraries.mkdir(parents=True)
    (libraries / 'archive.zip').write_bytes(MAIN.read_bytes())
    plugins = manager(tmp_path)
    library_install.ensure_environments(plugins)
    assert (libraries / 'environments.json').is_file()
    declared = json.loads((tmp_path / 'library/environments.json').read_text())['environments']
    assert set(declared) == {'antifold', 'boltz', 'esm3', 'openmm81'}