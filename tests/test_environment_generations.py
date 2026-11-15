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


def test_mutated_or_missing_manifest_never_ready(tmp_path):
    store = EnvironmentStore(tmp_path)
    binding = store.prepare(requirement(), FixtureBuilder())
    root = store.root / 'generations' / binding.generation_id
    (root / 'payload' / 'runtime' / 'fixture').write_text('changed')
    with pytest.raises(ContractError, match='changed'):
        store.binding(binding.generation_id)
    (root / 'verification.json').unlink()
    with pytest.raises(ContractError, match='generation manifest'):
        store.binding(binding.generation_id)


def test_archive_recipe_lock_is_not_assumed(tmp_path):
    from operon.environment_store.builders import LockedArchiveBuilder
    with pytest.raises(ContractError):
        LockedArchiveBuilder([], []).resolve(requirement())


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
