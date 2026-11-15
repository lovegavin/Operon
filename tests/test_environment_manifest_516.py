import json
from pathlib import Path
from unittest import mock

import pytest

from operon import environments, library_install
from operon.plugins import PluginManager

ROOT = Path(__file__).resolve().parents[1]
@pytest.fixture(autouse=True)
def archives(tmp_path, monkeypatch):
    """Build independent synthetic archives; no untracked release ZIP is required."""
    import hashlib
    import base64
    import io
    import zipfile
    import test_library_install_500 as fixture
    def bundle(label, version, suffix, envs):
        with zipfile.ZipFile(io.BytesIO(fixture._wheel_bytes())) as wheel:
            files = {name.replace('operon_synthetic', 'operon_synthetic' + suffix):
                     wheel.read(name).replace(b'operon_synthetic', ('operon_synthetic' + suffix).encode())
                     .replace(b'operon-synthetic', ('operon-synthetic' + suffix.replace('_', '-')).encode())
                     .replace(b'synthetic_scale', ('synthetic_scale' + suffix).encode())
                     for name in wheel.namelist() if not name.endswith('/RECORD')}
        module = 'operon_synthetic' + suffix + '_step'
        digest = hashlib.sha256((module + '.py').encode() + b'\0' + files[module + '.py']).hexdigest()
        manifest_name = next(name for name in files if name.endswith('/operon.json'))
        manifest = json.loads(files[manifest_name]); manifest['descriptors'][0]['code_sha'] = digest
        from operon_sdk.declarations import declaration_hash
        manifest['descriptors'][0]['declaration_sha'] = declaration_hash(manifest['descriptors'][0])
        files[manifest_name] = json.dumps(manifest).encode()
        info = manifest_name.rsplit('/', 1)[0]
        files[info + '/RECORD'] = ('\n'.join(f'{name},sha256={base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode("ascii")},{len(data)}'
                                          for name, data in files.items()) + f'\n{info}/RECORD,,\n').encode()
        wheel_data = fixture._zip_bytes(files)
        wheel_name = f'wheels/operon_synthetic{suffix}-0.1.0-py3-none-any.whl'
        document = {'format': 'operon.library', 'bundle_format': 1, 'library_name': label,
                    'library_version': version, 'operator_protocol': {'version': 3, 'revision': '3.7'},
                    'minimum_application': '5.0.0', 'packages': [{'name': manifest['name'],
                    'version': '0.1.0', 'wheel': wheel_name,
                    'wheel_sha256': hashlib.sha256(wheel_data).hexdigest(), 'code_sha': digest,
                    'entry_points': {manifest['descriptors'][0]['id']: module + ':SyntheticScale'}}]}
        entries = {'library.json': json.dumps(document).encode(), wheel_name: wheel_data,
                   'environments.json': json.dumps({'version': 1, 'environments': envs}).encode()}
        entries['SHA256SUMS'] = ''.join(f'{hashlib.sha256(data).hexdigest()}  {name}\n'
                                      for name, data in entries.items()).encode()
        path = tmp_path / f'operon-library-{label}-{version}.operon-library.zip'
        path.write_bytes(fixture._zip_bytes(entries))
        return path
    import sys
    module = sys.modules[__name__]
    envs = {name: {'python': '3.11'} for name in ('antifold', 'boltz', 'esm3', 'openmm81')}
    monkeypatch.setattr(module, 'MAIN', bundle('main', '0.1.0', '', envs), raising=False)
    monkeypatch.setattr(module, 'FORK', bundle('fork1', '0.0.0', '_fork', {}), raising=False)


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
