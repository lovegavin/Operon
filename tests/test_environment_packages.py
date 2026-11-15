"""Package trust boundary and reuse; fixtures do not claim real runtime support."""
import json
import pytest
from operon.contracts.base import ContractError
from operon.environment_store import EnvironmentStore
from operon.environment_store.packages import descriptor, blob_path, copy_generation
from test_environment_generations import requirement, FixtureBuilder


class LayerBuilder(FixtureBuilder):
    def build(self, root, store, **kwargs):
        (root / 'runtime').mkdir()
        (root / 'runtime/python').write_bytes(b'fixed language runtime')
        package = root / 'runtime/Lib/site-packages/science'
        package.mkdir(parents=True)
        (package / '__init__.py').write_text(self.version)
        return {'builder': 'layer-test-only'}


def test_conflicting_dependency_layers_reuse_runtime_without_rescanning(tmp_path, monkeypatch):
    store = EnvironmentStore(tmp_path / 'source')
    first = store.prepare(requirement('1'), LayerBuilder())
    second = store.prepare(requirement('2'), LayerBuilder())
    a = {x['kind']: x['sha256'] for x in descriptor(store, first.generation_id)['layers']}
    b = {x['kind']: x['sha256'] for x in descriptor(store, second.generation_id)['layers']}
    assert a['runtime'] == b['runtime'] and a['dependencies'] != b['dependencies']
    assert len(list((store.root / 'packages/sha256').glob('*.tar'))) == 3
    def forbidden(*a, **k): raise AssertionError('Expanded files rescanned')
    monkeypatch.setattr('operon.environment_store.verification.inventory', forbidden)
    assert store.binding(first.generation_id) == first
    target = EnvironmentStore(tmp_path / 'target')
    copy_generation(store, target, first.generation_id)
    copy_generation(store, target, second.generation_id)
    assert target.binding(first.generation_id) == first
    assert target.binding(second.generation_id) == second
    assert len(list((target.root / 'packages/sha256').glob('*.tar'))) == 3
    for generation, version in [(first.generation_id, '1'), (second.generation_id, '2')]:
        assert (target.root / 'generations' / generation / 'payload/runtime/Lib/site-packages/science/__init__.py').read_text() == version


def test_archive_corruption_and_missing_cache_receipt_fail_closed(tmp_path):
    store = EnvironmentStore(tmp_path)
    binding = store.prepare(requirement(), LayerBuilder())
    value = descriptor(store, binding.generation_id)
    path = blob_path(store, value['layers'][0]['sha256'])
    with path.open('r+b') as stream: stream.write(b'broken')
    with pytest.raises(ContractError, match='corrupt'): store.binding(binding.generation_id)


def test_cancelled_copy_is_not_published(tmp_path):
    store = EnvironmentStore(tmp_path / 'source')
    binding = store.prepare(requirement(), LayerBuilder())
    target = EnvironmentStore(tmp_path / 'target')
    with pytest.raises(InterruptedError):
        copy_generation(store, target, binding.generation_id, cancel=lambda: True)
    assert not (target.root / 'generations' / binding.generation_id).exists()
    assert not list((target.root / 'staging').iterdir())


def test_package_manifest_cannot_omit_dependency_layer(tmp_path):
    store = EnvironmentStore(tmp_path)
    binding = store.prepare(requirement(), LayerBuilder())
    path = store.root / 'generations' / binding.generation_id / 'packages.json'
    value = json.loads(path.read_text()); value['layers'] = value['layers'][:1]
    path.write_text(json.dumps(value))
    with pytest.raises(ContractError): store.binding(binding.generation_id)


def test_recover_missing_cache_into_fresh_store_from_archives(tmp_path):
    import shutil
    source = EnvironmentStore(tmp_path / 'source')
    binding = source.prepare(requirement(), LayerBuilder())
    directory = source.root / 'generations' / binding.generation_id
    shutil.rmtree(directory / 'payload')
    with pytest.raises(ContractError, match='materialization'):
        source.binding(binding.generation_id)
    target = EnvironmentStore(tmp_path / 'recovered')
    copy_generation(source, target, binding.generation_id)
    assert target.binding(binding.generation_id, verify='deep') == binding
    assert not (directory / 'payload').exists()


def test_legacy_mutable_store_migrates_once_but_readonly_bundle_does_not(tmp_path, monkeypatch):
    store = EnvironmentStore(tmp_path)
    binding = store.prepare(requirement(), LayerBuilder())
    root = store.root / 'generations' / binding.generation_id
    (root / 'packages.json').unlink(); (root / 'materialized.json').unlink()
    assert EnvironmentStore(tmp_path, create=False).binding(binding.generation_id) == binding
    assert not (root / 'packages.json').exists()
    assert store.binding(binding.generation_id) == binding
    assert (root / 'packages.json').exists()
    def forbidden(*a, **kw): raise AssertionError('Repeated migration scan')
    monkeypatch.setattr('operon.environment_store.verification.inventory', forbidden)
    assert EnvironmentStore(tmp_path).binding(binding.generation_id) == binding
