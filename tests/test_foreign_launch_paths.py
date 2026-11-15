"""Windows R restrictions are explicit, with no hidden copies or redirects."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from operon.contracts.base import ContractError
from operon.execution.foreign_paths import r_path, validate_r_generation


def test_r_accepts_short_physical_paths_and_spaces_in_regular_files(tmp_path):
    target = tmp_path / 'input data.tsv'
    assert r_path(target) == target.resolve()


def test_r_scratch_requires_space_free_physical_directory(tmp_path):
    with pytest.raises(ContractError, match='--work-dir') as caught:
        r_path(tmp_path / 'temporary directory', role='temporary', allow_spaces=False)
    assert caught.value.code == 'foreign_runtime_path_unsupported'
    assert caught.value.details == {'role': 'temporary'}


@pytest.mark.parametrize('role', ['input', 'output', 'script', 'environment'])
def test_r_rejects_long_physical_paths_before_launch(tmp_path, role):
    with pytest.raises(ContractError, match='environment-store') as caught:
        r_path(tmp_path / ('long-' * 60), role=role)
    assert caught.value.details['role'] == role


def test_r_temporary_bound_reserves_space_for_runtime_generated_files(tmp_path):
    size = len(str(tmp_path.resolve()).encode('utf-16-le')) // 2
    path = tmp_path / ('x' * (250 - size - 1))
    assert r_path(path)
    with pytest.raises(ContractError):
        r_path(path, role='temporary', reserve=32)


def test_r_generation_checks_all_declared_resources_without_reading_data(tmp_path):
    generation = tmp_path / 'g'
    calls = []
    store = SimpleNamespace(_manifest=lambda key: (generation, {'files': {
        'runtime/base.r': {}, 'runtime/' + 'nested/' * 45 + 'file': {},
    }}, None))
    with pytest.raises(ContractError) as caught:
        validate_r_generation(store, 'known-generation')
    assert caught.value.details['role'] == 'environment'
    assert not generation.exists()


def test_r_scratch_uses_owned_temporary_area_and_releases_only_matching_owner(tmp_path, monkeypatch):
    import json
    import tempfile
    from operon.execution.foreign_paths import r_scratch, release_r_scratch
    root = tmp_path / 'workspace with spaces' / 'attempt'
    root.mkdir(parents=True)
    base = tmp_path / 'os-temp'; base.mkdir()
    monkeypatch.setattr(tempfile, 'gettempdir', lambda: str(base))
    selected = r_scratch(root)
    assert selected.parent == base and selected != root / 'scratch'
    assert r_scratch(root) == selected
    marker = selected / '.operon-owner.json'
    original = marker.read_text()
    marker.write_text(json.dumps({'attempt': 'another-owner'}))
    release_r_scratch(root)
    assert selected.exists()
    marker.write_text(original)
    release_r_scratch(root)
    assert not selected.exists() and not (root / 'r-scratch.json').exists()
