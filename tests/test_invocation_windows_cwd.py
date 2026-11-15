"""Actual Windows attempt cwd junctions and child-process relative I/O."""
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from operon.bytecode import io_path
from operon.contracts.base import ContractError
from operon.execution import windows_paths as paths
from operon.execution.unit_executor import RunPlanExecutor


RUN = 'run-' + 'a' * 32
ATTEMPT = 'attempt-' + 'b' * 32
SCOPE = dict(run_id=RUN, attempt_id=ATTEMPT)
WINDOWS_ONLY = pytest.mark.skipif(os.name != 'nt', reason='Actual Windows junction and CreateProcess APIs')


def attempt_at(root, *, legacy=False):
    parent = root / 'runs' / RUN
    if legacy:
        parent = parent / 'nodes' / ('node-' + 'n' * 80)
    target = parent / 'attempts' / ATTEMPT
    io_path(target).mkdir(parents=True)
    io_path(target / 'evidence.txt').write_text('exact attempt contents', encoding='utf-8')
    return target


def test_nonwindows_preserves_exact_attempt_without_alias_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, '_WINDOWS', False)
    target = attempt_at(tmp_path)
    assert paths.attempt_launch_cwd(tmp_path, target, **SCOPE) == target
    assert not paths.remove_attempt_alias(tmp_path, target, **SCOPE)
    assert not (tmp_path / '.work').exists()


@pytest.mark.parametrize('incorrect', ['parent', 'another-run', 'another-attempt', 'outside'])
def test_alias_cannot_redirect_to_parent_or_different_attempt(tmp_path, incorrect):
    target = attempt_at(tmp_path)
    if incorrect == 'parent': target = target.parent
    elif incorrect == 'another-run': target = tmp_path / 'runs/other/attempts' / ATTEMPT
    elif incorrect == 'another-attempt': target = target.parent / 'other'
    else: target = tmp_path.parent / 'runs' / RUN / 'attempts' / ATTEMPT
    with pytest.raises(ContractError) as caught: paths.attempt_launch_cwd(tmp_path, target, **SCOPE)
    assert caught.value.code == 'attempt_launch_conflict'
    assert not (tmp_path / '.work').exists()


@WINDOWS_ONLY
@pytest.mark.parametrize('legacy', [False, True])
def test_actual_command_launch_uses_short_cwd_and_writes_only_its_attempt(tmp_path, monkeypatch, legacy):
    root = tmp_path
    while len(str(root)) < 180:
        root /= 'executor-part'
    target = attempt_at(root, legacy=legacy)
    assert len(str(target)) > 260
    executor = RunPlanExecutor(root, environment_store=None, package_root=root, bindings={})
    context = SimpleNamespace(run={'id': RUN}, attempt_id=ATTEMPT)
    command = (sys.executable, '-I', '-c',
        'from pathlib import Path; print(Path("evidence.txt").read_text()); '
        'Path("child-created.txt").write_text("owned relative output")')
    prepared = SimpleNamespace(command=command, context=SimpleNamespace(attempt_root=io_path(target)),
                               environment={})
    monkeypatch.setattr(executor, '_prepare', lambda _: ('generation-fixture', prepared))
    spec = executor._command(context)
    alias = Path(spec.cwd)
    try:
        assert alias.parent == root / '.work'
        assert not str(alias).startswith('\\\\?\\')
        assert len(str(alias).encode('utf-16-le')) // 2 < 248
        assert io_path(alias).samefile(io_path(target))
        assert paths.attempt_launch_cwd(root, io_path(target), **SCOPE) == alias
        child = subprocess.run(spec.argv, cwd=spec.cwd, capture_output=True,
                               text=True, encoding='utf-8', timeout=30, check=True)
        assert child.stdout.strip() == 'exact attempt contents'
        assert io_path(target / 'child-created.txt').read_text() == 'owned relative output'
        assert not io_path(target.parent / 'child-created.txt').exists()
        assert spec.stdout_path == str(io_path(target) / 'logs/worker.log')
    finally:
        assert paths.remove_attempt_alias(root, target, **SCOPE)
    assert io_path(target / 'evidence.txt').read_text() == 'exact attempt contents'
    assert io_path(target / 'child-created.txt').read_text() == 'owned relative output'
    assert not os.path.lexists(alias)
    assert not paths.remove_attempt_alias(root, target, **SCOPE)


@WINDOWS_ONLY
def test_different_target_junction_is_never_replaced_or_removed(tmp_path):
    target = attempt_at(tmp_path)
    other = tmp_path / 'other'
    other.mkdir()
    (other / 'keep.txt').write_text('keep')
    _, _, alias = paths._layout(tmp_path, target, **SCOPE)
    alias.parent.mkdir()
    native = paths._NativeJunctions()
    native.create(alias, other)
    try:
        for operation in (paths.attempt_launch_cwd, paths.remove_attempt_alias):
            with pytest.raises(ContractError) as caught: operation(tmp_path, target, **SCOPE)
            assert caught.value.code == 'attempt_launch_conflict'
            assert (other / 'keep.txt').read_text() == 'keep'
            assert alias.resolve() == other
    finally:
        native.remove(alias)


@WINDOWS_ONLY
@pytest.mark.parametrize('kind', ['file', 'directory', 'metadata-junction', 'target-junction'])
def test_foreign_entries_and_redirected_parents_fail_closed(tmp_path, kind):
    target = attempt_at(tmp_path)
    _, _, alias = paths._layout(tmp_path, target, **SCOPE)
    other = tmp_path / 'other'
    other.mkdir()
    (other / 'keep.txt').write_text('keep')
    native = paths._NativeJunctions()
    cleanup = None
    if kind == 'metadata-junction':
        native.create(alias.parent, other)
        cleanup = alias.parent
    elif kind == 'target-junction':
        io_path(target / 'evidence.txt').unlink()
        io_path(target).rmdir()
        native.create(target, other)
        cleanup = target
    else:
        alias.parent.mkdir()
        if kind == 'file': alias.write_text('foreign entry')
        else:
            alias.mkdir()
            (alias / 'keep.txt').write_text('foreign entry')
    try:
        with pytest.raises(ContractError) as caught: paths.attempt_launch_cwd(tmp_path, target, **SCOPE)
        assert caught.value.code == 'attempt_launch_conflict'
        assert (other / 'keep.txt').read_text() == 'keep'
        if kind in ('file', 'directory'):
            with pytest.raises(ContractError): paths.remove_attempt_alias(tmp_path, target, **SCOPE)
            assert (alias if kind == 'file' else alias / 'keep.txt').read_text() == 'foreign entry'
    finally:
        if cleanup is not None: native.remove(cleanup)


@WINDOWS_ONLY
def test_matching_dangling_alias_removal_never_walks_target(tmp_path):
    target = attempt_at(tmp_path)
    alias = paths.attempt_launch_cwd(tmp_path, target, **SCOPE)
    io_path(target / 'evidence.txt').unlink()
    io_path(target).rmdir()
    assert paths.remove_attempt_alias(tmp_path, target, **SCOPE)
    assert not os.path.lexists(alias)
    assert io_path(target.parent).is_dir()


@WINDOWS_ONLY
def test_overlong_alias_is_explicit_failure_without_mutation(tmp_path):
    root = tmp_path
    while len(str(root)) < 230:
        root /= 'long-executor-root'
    target = attempt_at(root)
    with pytest.raises(ContractError) as caught: paths.attempt_launch_cwd(root, target, **SCOPE)
    assert caught.value.code == 'attempt_launch_path_too_long'
    assert not io_path(root / '.work').exists()
    assert not io_path(root / '.work-locks').exists()
    assert io_path(target / 'evidence.txt').read_text() == 'exact attempt contents'


def test_missing_junction_capability_never_falls_back_to_parent_or_extended_cwd(tmp_path, monkeypatch):
    target = attempt_at(tmp_path)
    monkeypatch.setattr(paths, '_WINDOWS', True)
    def unavailable(): raise OSError('fixture unavailable junction capability')
    monkeypatch.setattr(paths, '_NativeJunctions', unavailable)
    with pytest.raises(ContractError) as caught: paths.attempt_launch_cwd(tmp_path, target, **SCOPE)
    assert caught.value.code == 'attempt_launch_unavailable'
    assert not (tmp_path / '.work').exists()
    assert io_path(target / 'evidence.txt').read_text() == 'exact attempt contents'
