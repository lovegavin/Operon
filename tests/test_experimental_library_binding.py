import json
from pathlib import Path

import pytest

from operon.installation import library_root


def fixture(root):
    version = root / 'versions/rc4'
    version.mkdir(parents=True)
    (root / 'library').mkdir()
    (root / 'install-state.json').write_text(json.dumps({
        'schema': 1, 'product': 'operon-studio-experimental', 'channel': 'experimental',
        'installation_id': 'test-id'}))
    (version / 'host.json').write_text(json.dumps({'installation_id': 'test-id'}))
    (version / 'experimental-library-binding.json').write_text(json.dumps({
        'schema': 1, 'installation_id': 'test-id', 'location': '../../library'}))
    return version


def test_stable_binding_keeps_same_library_across_versions(tmp_path):
    version = fixture(tmp_path)
    second = tmp_path / 'versions/rc5'
    second.mkdir()
    for name in ('host.json', 'experimental-library-binding.json'):
        (second / name).write_bytes((version / name).read_bytes())
    assert library_root(version).samefile(tmp_path / 'library')
    assert library_root(second).samefile(tmp_path / 'library')


@pytest.mark.parametrize('field,value', [('installation_id', 'foreign'),
    ('location', '../../../other'), ('schema', 2)])
def test_invalid_binding_fails_closed(tmp_path, field, value):
    version = fixture(tmp_path)
    path = version / 'experimental-library-binding.json'
    document = json.loads(path.read_text())
    document[field] = value
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError, match='binding'):
        library_root(version)


def test_unchanged_nonexperimental_layout(tmp_path):
    version = tmp_path / 'versions/normal'
    version.mkdir(parents=True)
    assert library_root(version) == version / 'library'


def test_copied_imported_library_keeps_pins_and_resolves_new_runtime_root(tmp_path, monkeypatch):
    import shutil
    from operon.plugins import PluginManager
    from operon.library_install import install_library
    from test_library_install_500 import _library_zip, OPERATOR
    monkeypatch.setattr(PluginManager, 'bundled_state', lambda self: {'packages': [], 'descriptors': []})
    old = tmp_path / 'versions/rc3/library'
    manager = PluginManager(tmp_path / 'profile', library_root=old)
    install_library(manager, _library_zip(tmp_path))
    previous = manager.state()
    pin = next(item['implementation'] for item in previous['descriptors'] if item['id'] == OPERATOR)
    shutil.copytree(old, tmp_path / 'library')
    # Fixture creates only control documents; the copied registry is untouched.
    version = tmp_path / 'versions/rc4'
    version.mkdir(parents=True)
    (tmp_path / 'install-state.json').write_text(json.dumps({'schema': 1,
        'product': 'operon-studio-experimental', 'channel': 'experimental', 'installation_id': 'test-id'}))
    (version / 'host.json').write_text(json.dumps({'installation_id': 'test-id'}))
    (version / 'experimental-library-binding.json').write_text(json.dumps({
        'schema': 1, 'installation_id': 'test-id', 'location': '../../library'}))
    current = PluginManager(tmp_path / 'profile', library_root=library_root(version))
    state = current.state()
    assert next(item['implementation'] for item in state['descriptors'] if item['id'] == OPERATOR) == pin
    assert Path(state['_runtime_root']).samefile(tmp_path / 'library')
    assert (old / 'registry.json').read_bytes() == (tmp_path / 'library/registry.json').read_bytes()
    required = {OPERATOR: pin}
    from src.web.models import Graph
    snapshot = current.snapshot(Graph(nodes=[], edges=[], plugin_lock=required))
    assert snapshot is not None
