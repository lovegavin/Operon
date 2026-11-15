"""K03 store fault matrix; fake builders are explicitly module tests only."""
import json
from pathlib import Path

import pytest

from operon.contracts.base import ContractError, sha256_hex
from operon.contracts.run_plan import EnvironmentRequirement, TargetSpec
from operon.environment_store import EnvironmentStore
from operon.environment_store.locks import resolve_groups


def requirement(version='1'):
    return EnvironmentRequirement(target=TargetSpec(os='test', arch='test'), runtime='test-fixture',
                                  dependency_lock={'fixture_version': version})


class FixtureBuilder:
    def resolve(self, requirement):
        self.version = requirement.dependency_lock['fixture_version']

    def build(self, root, store, **kwargs):
        (root / 'runtime').mkdir()
        (root / 'runtime' / 'fixture').write_text(self.version, encoding='utf-8')
        return {'builder': 'test-only'}

    def verify(self, root, **kwargs):
        return {'status': 'passed', 'relocation': 'passed', 'test_fixture': True}


def test_defaults_changes_make_new_generation_and_keep_old_lease(tmp_path):
    store = EnvironmentStore(tmp_path)
    old = store.prepare(requirement(), FixtureBuilder())
    store.acquire(old.generation_id, attempt_id='live', fence=1)
    new = store.prepare(requirement('2'), FixtureBuilder())
    assert new.generation_id != old.generation_id
    assert store.binding(old.generation_id) == old
    (store.root / 'references' / (sha256_hex(requirement()) + '.json')).unlink()
    assert not store.collect(old.generation_id)
    store.release_unstarted('live', 1)
    assert store.collect(old.generation_id)


@pytest.mark.parametrize('phase', ['requested', 'resolving', 'building', 'verifying', 'verified', 'published', 'ready'])
def test_crash_publication_recovery(tmp_path, phase):
    store = EnvironmentStore(tmp_path)
    def crash(current):
        if current == phase:
            raise KeyboardInterrupt('simulated crash')
    with pytest.raises(KeyboardInterrupt):
        store.prepare(requirement(), FixtureBuilder(), checkpoint=crash)
    store = EnvironmentStore(tmp_path)
    store.recover()
    binding = store.resolve(requirement())
    assert bool(binding) == (phase in ('published', 'ready'))
    assert store.prepare(requirement(), FixtureBuilder()).generation_id


def test_orphan_and_unknown_spawn_never_expires(tmp_path):
    store = EnvironmentStore(tmp_path)
    binding = store.prepare(requirement(), FixtureBuilder())
    store.acquire(binding.generation_id, attempt_id='orphan', fence=4)
    store.spawning('orphan', 4, tmp_path / 'supervisor')
    (store.root / 'references' / (sha256_hex(requirement()) + '.json')).unlink()
    assert not EnvironmentStore(tmp_path).collect(binding.generation_id)
    with pytest.raises(ContractError):
        store.release_unstarted('orphan', 4)
    with pytest.raises(OSError):
        store.release('orphan', 4)


def test_explicit_deep_audit_detects_cache_mutation_and_missing_manifest_never_ready(tmp_path):
    store = EnvironmentStore(tmp_path)
    binding = store.prepare(requirement(), FixtureBuilder())
    root = store.root / 'generations' / binding.generation_id
    (root / 'payload' / 'runtime' / 'fixture').write_text('changed')
    with pytest.raises(ContractError, match='changed'):
        store.binding(binding.generation_id, verify='deep')
    (root / 'verification.json').unlink()
    with pytest.raises(ContractError, match='generation manifest'):
        store.binding(binding.generation_id)


def test_archive_recipe_lock_is_not_assumed(tmp_path):
    from operon.environment_store.builders import LockedArchiveBuilder
    with pytest.raises(ContractError):
        LockedArchiveBuilder([], []).resolve(requirement())


def test_inventory_preserves_bytes_modes_and_detects_changes(tmp_path):
    import hashlib
    from operon.environment_store.verification import inventory, verify_inventory
    folder = tmp_path / 'nested'; folder.mkdir()
    file = folder / 'content.bin'; file.write_bytes(b'\x00synthetic\xff')
    expected = {'nested/content.bin': {'kind': 'file', 'size': 11,
        'sha256': hashlib.sha256(file.read_bytes()).hexdigest(),
        'executable': bool(file.stat().st_mode & 0o111)}}
    assert inventory(tmp_path) == expected
    file.write_bytes(b'\x00different\xff')
    with pytest.raises(ContractError, match='changed'):
        verify_inventory(tmp_path, expected)


def test_inventory_still_rejects_external_symlink(tmp_path):
    from operon.environment_store.verification import inventory
    root = tmp_path / 'root'; root.mkdir()
    outside = tmp_path / 'outside'; outside.write_text('outside')
    try:
        (root / 'link').symlink_to(outside)
    except OSError:
        pytest.skip('Symlink privilege unavailable')
    with pytest.raises(ContractError, match='escapes'):
        inventory(root)


@pytest.mark.skipif(__import__('os').name != 'nt', reason='Windows handle boundary')
def test_windows_inventory_checks_opened_handle_before_reading(tmp_path):
    from operon.bytecode import io_path
    from operon.environment_store.verification import _windows_inventory_digest
    root = tmp_path / 'root'; root.mkdir()
    outside = tmp_path / 'outside.bin'; outside.write_bytes(b'outside')
    with pytest.raises(ContractError, match='escapes'):
        _windows_inventory_digest(io_path(outside), io_path(root), outside.stat())


@pytest.mark.skipif(__import__('os').name != 'nt', reason='Windows long handle paths')
def test_windows_inventory_long_unicode_paths_keep_exact_manifest(tmp_path):
    import hashlib
    from operon.bytecode import io_path
    from operon.environment_store.verification import inventory
    nested = tmp_path
    while len(str(nested)) < 600:
        nested /= 'unicode-\u6570\u636e-' + 'x' * 30
    io_path(nested).mkdir(parents=True)
    file = io_path(nested / 'sample.bin'); file.write_bytes(b'content')
    result = inventory(tmp_path)
    assert result == {(nested / 'sample.bin').relative_to(tmp_path).as_posix(): {
        'kind': 'file', 'size': 7, 'sha256': hashlib.sha256(b'content').hexdigest(),
        'executable': bool(file.stat().st_mode & 0o111)}}


def test_probe_timeout_keeps_phase_and_command_diagnostics():
    import sys
    from operon.environment_store.builders import probe
    runtime = Path(sys.executable)
    with pytest.raises(TimeoutError) as error:
        probe(runtime.parent, (runtime.name, '-I', '-c',
              "import time; print('verify_destination_environment', flush=True); time.sleep(60)"),
              timeout=2)
    assert 'last output: verify_destination_environment' in str(error.value)
    assert runtime.name in str(error.value)
    assert 'after 2s' in str(error.value)


def test_grouping_only_merges_verified_compatible_runtime():
    calls = []
    req = {name: {'runtime': runtime, 'target': 'test', 'version': version}
           for name, runtime, version in [('a', 'py311', '1'), ('b', 'py311', '2'), ('c', 'R', '1')]}
    def resolver(values, timeout):
        calls.append(values)
        if len({v['version'] for v in values}) > 1:
            raise ValueError('conflict')
        return {'lock': values}
    groups = resolve_groups(req, resolver)
    assert len(groups) == 3
    assert len(calls) == 4  # no cross-language resolver attempt
