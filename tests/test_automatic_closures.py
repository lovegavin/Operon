"""Portable closure safety, selection and reuse; real runtime gates are separate."""
import json
import shutil
import sys
from pathlib import Path

import pytest

from operon.contracts.base import ContractError
from operon.environment_store import closures


def tree_payload(tmp_path):
    source = tmp_path / 'source'; source.mkdir()
    (source / 'bin').mkdir()
    (source / 'bin/tool').write_text('native-data')
    value = {'roots': {'one': {'source': str(source), 'kind': 'tree'}},
             'python': None, 'external': {}, 'tools': {'tool': {'closure': 'one', 'path': 'bin/tool'}}, 'r': {}}
    payload = tmp_path / 'payload'
    closures.capture(value, payload / 'closures', tmp_path / 'store')
    return payload


def test_tree_closure_moves_and_reuses_without_source_or_reextract(tmp_path, monkeypatch):
    payload = tree_payload(tmp_path)
    shutil.rmtree(tmp_path / 'source')
    first = closures.materialize(payload, tmp_path / 'cache', python=sys.executable)
    assert Path(first['tools']['tool']).read_text() == 'native-data'
    import operon.environment_store.builders as builders
    extract = builders.extract_locked
    monkeypatch.setattr(builders, 'extract_locked', lambda *a, **kw: pytest.fail('re-extracted immutable package'))
    assert closures.materialize(payload, tmp_path / 'cache', python=sys.executable) == first
    monkeypatch.setattr(builders, 'extract_locked', extract)
    moved = tmp_path / 'moved payload'; shutil.move(payload, moved)
    second = closures.materialize(moved, tmp_path / 'new cache', python=sys.executable)
    assert second['tools']['tool'] != first['tools']['tool']
    assert Path(second['tools']['tool']).read_text() == 'native-data'


def test_changed_packed_archive_is_rejected_before_new_deployment(tmp_path):
    payload = tree_payload(tmp_path)
    archive = next((payload / 'closures').glob('*.tar'))
    archive.write_bytes(archive.read_bytes() + b'changed')
    with pytest.raises(ContractError, match='receipt'):
        closures.materialize(payload, tmp_path / 'cache', python=sys.executable)


def test_conda_fixup_runs_at_final_path_once_and_restarts_from_original_after_move(tmp_path, monkeypatch):
    # This is a relocation-state test, not a real Conda acceptance claim.
    payload = tree_payload(tmp_path)
    path = payload / 'closures/manifest.json'
    value = json.loads(path.read_text()); value['roots']['one']['kind'] = 'conda'
    from operon.environment_store.canvas import archive_tree
    source = tmp_path / 'source'
    (source / 'bin/conda-unpack').write_text('placeholder')
    (payload / 'closures/one.tar').unlink()
    archive_tree(source, payload / 'closures/one.tar')
    from operon.environment_store.verification import file_digest
    value['roots']['one']['sha256'] = file_digest(payload / 'closures/one.tar')
    value['roots']['one']['max_unpacked_bytes'] = 10000
    path.write_text(json.dumps(value))
    calls = []
    def unpack(argv, **kwargs):
        script = Path(argv[-1]); calls.append(script)
        assert script.read_text() == 'placeholder'
        script.write_text('fixed at ' + str(script.parent.parent))
    monkeypatch.setattr(closures, 'run_process', unpack)
    closures.materialize(payload, tmp_path / 'cache', python=sys.executable)
    closures.materialize(payload, tmp_path / 'cache', python=sys.executable)
    assert len(calls) == 1 and '.partial' not in str(calls[0])
    shutil.move(tmp_path / 'cache', tmp_path / 'cache moved')
    closures.materialize(payload, tmp_path / 'cache moved', python=sys.executable)
    assert len(calls) == 2


def test_portable_r_and_tool_bindings_never_fall_back_to_host_or_install(tmp_path, monkeypatch):
    from operon.r_runtime import RRuntime
    from operon.dependencies import find_tool
    monkeypatch.setenv('OPERON_PACKED_TOOLS', '{}')
    monkeypatch.setenv('OPERON_PACKED_R', '{}')
    monkeypatch.setattr(shutil, 'which', lambda *a: pytest.fail('host tool lookup'))
    monkeypatch.setattr(RRuntime, '_bootstrap', lambda *a: pytest.fail('network installation'))
    assert find_tool('Rscript') is None
    with pytest.raises(ValueError, match='not bound'):
        RRuntime(tmp_path / 'never-create').ensure({'version': '>=4', 'packages': []})
    assert not (tmp_path / 'never-create').exists()


def test_discovery_deduplicates_conda_prefix_and_preserves_named_environment(tmp_path, monkeypatch):
    prefix = tmp_path / 'conda'; (prefix / 'conda-meta').mkdir(parents=True)
    (prefix / 'bin').mkdir(); (prefix / 'bin/python').write_text('exe')
    (prefix / 'bin/samtools').write_text('tool')
    (prefix / 'packages').mkdir()
    (prefix / 'conda-meta/python.json').write_text('{"version":"3.11"}')
    info = {'prefix': str(prefix), 'executable': str(prefix / 'bin/python'), 'purelib': str(prefix / 'packages')}
    import operon.dependencies as dependencies
    monkeypatch.setattr(dependencies, 'find_tool', lambda name: str(prefix / 'bin' / name))
    result = closures.discover(info, [{'resources': {'external_tools': ['samtools']}}], {'other': info})
    assert len(result['roots']) == 1
    assert result['python'] == result['external']['other']
    assert result['python_packages']


def test_acquisition_never_selects_unmanaged_or_different_python(tmp_path, monkeypatch):
    from operon.environment_store import acquisition
    monkeypatch.setattr(acquisition.shutil, 'which', lambda name: 'uv')
    monkeypatch.setattr(acquisition, 'run_process', lambda argv, **kw: sys.executable if 'find' in argv else '')
    with pytest.raises(ContractError, match='escaped'):
        acquisition.standalone_python(tmp_path, {'version': [3, 11, 14], 'os': 'windows', 'arch': 'amd64'})


def test_named_environments_cannot_silently_overwrite_tool_binding(tmp_path):
    import os
    infos = []
    for name in ('one', 'two'):
        prefix = tmp_path / name
        (prefix / 'conda-meta').mkdir(parents=True)
        (prefix / 'bin').mkdir()
        (prefix / 'bin/python').write_text('python')
        (prefix / ('bin/tool.exe' if os.name == 'nt' else 'bin/tool')).write_text(name)
        (prefix / 'packages').mkdir()
        infos.append({'prefix': str(prefix), 'executable': str(prefix / 'bin/python'),
                      'purelib': str(prefix / 'packages')})
    descriptors = [{'resources': {'external_tools': ['tool'], 'environment': name}}
                   for name in ('one', 'two')]
    with pytest.raises(ContractError, match='Conflicting portable tool'):
        closures.discover(infos[0], descriptors, dict(zip(('one', 'two'), infos)))


def test_acquisition_does_not_reuse_partial_tool_installation(tmp_path, monkeypatch):
    from operon.environment_store import acquisition
    directory = tmp_path / 'export-tools/demo-1.0'
    (directory / 'demo').mkdir(parents=True)
    (directory / 'partial').write_text('interrupted')
    calls = []
    def install(argv, **kw):
        calls.append(argv)
        if 'install' in argv:
            assert not (directory / 'partial').exists()
            (directory / 'demo').mkdir()
        return ''
    monkeypatch.setattr(acquisition, 'run_process', install)
    assert acquisition.tooling(tmp_path, 'demo', '1.0') == directory
    acquisition.tooling(tmp_path, 'demo', '1.0')
    assert len(calls) == 2
