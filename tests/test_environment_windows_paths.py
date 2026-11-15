"""Launch-alias safety, plus actual Windows junction/subprocess I/O.

The Windows test uses the test interpreter, not R. It qualifies junction path
access only; third-party runtime launch/relocation belongs to product E2E.
"""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
from pathlib import Path, PureWindowsPath
import stat
import struct
import subprocess
import sys
from types import SimpleNamespace

import pytest

from operon.bytecode import io_path
from operon.contracts.base import ContractError
from operon.environment_store import windows_paths as paths


GENERATION = hashlib.sha256(b'immutable environment fixture').hexdigest()
WINDOWS_ONLY = pytest.mark.skipif(os.name != 'nt', reason='Actual Windows junction API required')


def payload_at(root, generation=GENERATION):
    payload = root / 'generations' / generation / 'payload'
    io_path(payload).mkdir(parents=True)
    return payload


def alias_at(root, generation=GENERATION):
    return root / '.launch' / hashlib.sha256(generation.encode('ascii')).hexdigest()[:24]


def test_nonwindows_returns_canonical_payload_without_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, '_WINDOWS', False)
    payload = payload_at(tmp_path)
    assert paths.launch_root(tmp_path / '.', GENERATION) == payload.resolve()
    assert not paths.remove_launch_alias(tmp_path, GENERATION)
    assert not (tmp_path / '.launch').exists()
    assert not (tmp_path / 'locks').exists()


@pytest.mark.parametrize('generation', ['', '../outside', 'a' * 63, 'G' * 64, 'A' * 64, None])
def test_full_generation_digest_required_before_io(tmp_path, generation):
    for operation in (paths.launch_root, paths.remove_launch_alias):
        with pytest.raises(ContractError) as error:
            operation(tmp_path, generation)
        assert error.value.code == 'invalid_environment'
    assert not list(tmp_path.iterdir())


def test_mount_record_preserves_full_unicode_target():
    target = PureWindowsPath('C:/environments/科学') / 'generations' / GENERATION / 'payload'
    record = paths._mount_buffer(target)
    assert paths._mount_names(record) == ('\\??\\' + str(target), str(target))
    assert GENERATION in paths._mount_names(record)[0]


@pytest.mark.parametrize('corruption', ['symlink', 'other_tag', 'truncated', 'outside', 'odd', 'nul'])
def test_mount_record_rejects_foreign_or_malformed_reparse_data(corruption):
    data = bytearray(paths._mount_buffer(PureWindowsPath('C:/store/generations') / GENERATION / 'payload'))
    if corruption == 'symlink':
        struct.pack_into('<I', data, 0, 0xA000000C)
    elif corruption == 'other_tag':
        struct.pack_into('<I', data, 0, 0x80000021)
    elif corruption == 'truncated':
        data = data[:-1]
    elif corruption == 'outside':
        struct.pack_into('<H', data, 8, 65534)
    elif corruption == 'odd':
        struct.pack_into('<H', data, 10, 3)
    else:
        data[16:18] = b'\0\0'
    with pytest.raises(ContractError) as error:
        paths._mount_names(data)
    assert error.value.code == 'environment_launch_conflict'


def test_mount_record_size_bound_is_explicit():
    with pytest.raises(ContractError) as error:
        paths._mount_buffer('C:\\' + 'a' * 40000)
    assert error.value.code == 'environment_launch_unavailable'


@pytest.mark.parametrize('mode,attributes', [
    (stat.S_IFLNK, 0x400), (stat.S_IFREG, 0), (stat.S_IFDIR, 0),
])
def test_alias_verification_never_opens_symlink_or_foreign_entry(monkeypatch, mode, attributes):
    monkeypatch.setattr(paths, '_entry', lambda path: SimpleNamespace(
        st_mode=mode, st_file_attributes=attributes))
    api = paths._NativeJunctions.__new__(paths._NativeJunctions)
    monkeypatch.setattr(api, '_open', lambda *a, **k: pytest.fail('Foreign entry was opened'))
    with pytest.raises(ContractError) as error:
        api.verify(Path('alias'), Path('expected'))
    assert error.value.code == 'environment_launch_conflict'


def test_missing_native_capability_is_error_without_fallback(tmp_path, monkeypatch):
    payload_at(tmp_path)
    monkeypatch.setattr(paths, '_WINDOWS', True)

    def unavailable():
        raise OSError('Reparse points unavailable on this volume')

    monkeypatch.setattr(paths, '_NativeJunctions', unavailable)
    with pytest.raises(ContractError) as error:
        paths.launch_root(tmp_path, GENERATION)
    assert error.value.code == 'environment_launch_unavailable'
    assert not (tmp_path / '.launch').exists()


@WINDOWS_ONLY
def test_real_junction_shortens_long_payload_and_subprocess_opens_file(tmp_path):
    root = tmp_path / 'environment-store'
    while len(str(root)) < 180:
        root = root / 'physical-store-part'
    payload = payload_at(root)
    marker = payload / '科学-evidence.txt'
    io_path(marker).write_text('immutable payload bytes', encoding='utf-8')
    assert len(str(marker)) > 260
    alias = paths.launch_root(root, GENERATION)
    try:
        assert alias == alias_at(root.resolve())
        assert not str(alias).startswith('\\\\?\\')
        assert len(str(alias / marker.name)) < 260
        assert io_path(alias).samefile(io_path(payload))
        assert paths.launch_root(root, GENERATION) == alias
        probe = subprocess.run([sys.executable, '-I', '-c',
            'import pathlib,sys; print(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))',
            str(alias / marker.name)], cwd=str(alias), check=True,
            capture_output=True, text=True, encoding='utf-8', timeout=30)
        assert probe.stdout.strip() == 'immutable payload bytes'
    finally:
        assert paths.remove_launch_alias(root, GENERATION)
    assert io_path(marker).read_text(encoding='utf-8') == 'immutable payload bytes'
    assert not os.path.lexists(alias)
    assert not paths.remove_launch_alias(root, GENERATION)


@WINDOWS_ONLY
@pytest.mark.parametrize('entry_kind', ['file', 'directory'])
def test_foreign_alias_entry_is_preserved_for_launch_and_gc(tmp_path, entry_kind):
    payload_at(tmp_path)
    alias = alias_at(tmp_path.resolve())
    alias.parent.mkdir()
    if entry_kind == 'file':
        alias.write_text('foreign', encoding='utf-8')
        marker = alias
    else:
        alias.mkdir()
        marker = alias / 'foreign.txt'
        marker.write_text('foreign', encoding='utf-8')
    for operation in (paths.launch_root, paths.remove_launch_alias):
        with pytest.raises(ContractError) as error:
            operation(tmp_path, GENERATION)
        assert error.value.code == 'environment_launch_conflict'
        assert marker.read_text(encoding='utf-8') == 'foreign'


@WINDOWS_ONLY
def test_different_full_generation_target_is_never_replaced_or_removed(tmp_path):
    payload_at(tmp_path)
    other = payload_at(tmp_path, GENERATION[:-1] + ('0' if GENERATION[-1] != '0' else '1'))
    marker = other / 'keep.txt'
    marker.write_text('foreign generation', encoding='utf-8')
    alias = alias_at(tmp_path.resolve())
    alias.parent.mkdir()
    native = paths._NativeJunctions()
    native.create(alias, other.resolve())
    try:
        for operation in (paths.launch_root, paths.remove_launch_alias):
            with pytest.raises(ContractError) as error:
                operation(tmp_path, GENERATION)
            assert error.value.code == 'environment_launch_conflict'
            assert alias.resolve() == other.resolve()
            assert marker.read_text(encoding='utf-8') == 'foreign generation'
    finally:
        native.remove(alias)


@WINDOWS_ONLY
def test_redirected_metadata_parent_is_never_followed(tmp_path):
    root = tmp_path / 'store'
    payload_at(root)
    foreign = tmp_path / 'foreign'
    foreign.mkdir()
    marker = foreign / 'keep.txt'
    marker.write_text('keep', encoding='utf-8')
    native = paths._NativeJunctions()
    native.create(root / '.launch', foreign.resolve())
    try:
        for operation in (paths.launch_root, paths.remove_launch_alias):
            with pytest.raises(ContractError) as error:
                operation(root, GENERATION)
            assert error.value.code == 'environment_launch_conflict'
        assert list(foreign.iterdir()) == [marker]
    finally:
        native.remove(root / '.launch')


@WINDOWS_ONLY
def test_payload_junction_cannot_redirect_generation_identity(tmp_path):
    root = tmp_path / 'store'
    generation = root / 'generations' / GENERATION
    generation.mkdir(parents=True)
    other = tmp_path / 'other-payload'
    other.mkdir()
    native = paths._NativeJunctions()
    native.create(generation / 'payload', other.resolve())
    try:
        with pytest.raises(ContractError) as error:
            paths.launch_root(root, GENERATION)
        assert error.value.code == 'environment_launch_conflict'
        assert not (root / '.launch').exists()
    finally:
        native.remove(generation / 'payload')


@WINDOWS_ONLY
def test_concurrent_callers_share_one_verified_alias(tmp_path):
    payload_at(tmp_path)
    try:
        with ThreadPoolExecutor(max_workers=4) as workers:
            aliases = list(workers.map(lambda _: paths.launch_root(tmp_path, GENERATION), range(8)))
        assert len(set(aliases)) == 1
        assert list((tmp_path / '.launch').iterdir()) == [aliases[0]]
    finally:
        paths.remove_launch_alias(tmp_path, GENERATION)


@WINDOWS_ONLY
def test_gc_can_remove_matching_dangling_junction_without_target_walk(tmp_path):
    payload = payload_at(tmp_path)
    alias = paths.launch_root(tmp_path, GENERATION)
    payload.rmdir()
    assert paths.remove_launch_alias(tmp_path, GENERATION)
    assert not os.path.lexists(alias)
    assert payload.parent.is_dir()


@WINDOWS_ONLY
def test_overlong_store_root_fails_instead_of_extended_executable_fallback(tmp_path):
    root = tmp_path
    while len(str(alias_at(root))) < 248:
        root = root / 'long-root-partition'
    payload = payload_at(root)
    with pytest.raises(ContractError) as error:
        paths.launch_root(root, GENERATION)
    assert error.value.code == 'environment_launch_path_too_long'
    assert io_path(payload).is_dir()
    assert not io_path(root / '.launch').exists()
