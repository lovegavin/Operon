"""K07 module behavior; fake SFTP/jumps are not real transport acceptance."""
from __future__ import annotations

import os
from pathlib import Path
import stat
import threading
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from operon.storage import (BrowseLimits, BrowseRequest, LocalStorage, MountMap,
                            PreviewRequest, SFTPStorage, StorageError, StorageService, reference)
from operon.storage.ssh import SFTPConnection
from operon.remote.client import HostKeyRequired


def service_for(root, **kwargs):
    mounts = MountMap()
    mounts.register('data', LocalStorage(root), principals=('alice', 'bob'))
    return StorageService(mounts, **kwargs)


def test_stable_reference_normalizes_paths_and_legacy_import_is_explicit(tmp_path):
    file = tmp_path / 'table.txt'
    file.write_text('synthetic', encoding='utf-8')
    backend = LocalStorage(tmp_path)
    assert backend.import_absolute('data', file) == reference('data', 'table.txt')
    assert reference('data', './nested\\table.txt').relative_path == 'nested/table.txt'
    assert reference('data').relative_path == '.'
    assert str(tmp_path) not in reference('data', 'table.txt').model_dump_json()
    with pytest.raises(StorageError, match='outside'):
        backend.import_absolute('data', tmp_path.parent)


@pytest.mark.parametrize('path', ['../secret', 'a/../b', '/absolute', 'C:\\secret',
                                  '\\\\server\\share', 'table.txt:stream', 'a\x00b'])
def test_traversal_and_platform_aliases_are_rejected(path):
    with pytest.raises((ValueError, ValidationError)):
        BrowseRequest(storage_id='data', relative_path=path)


@pytest.mark.parametrize('extra', [{'page_size': True}, {'page_size': 1001}, {'hidden': 'false'},
                                   {'order': 'alphabetical'}, {'recursive': True}])
def test_browse_requests_reject_coercions_unknown_features_and_oversize(extra):
    with pytest.raises(ValidationError):
        BrowseRequest(storage_id='data', **extra)


def test_local_listing_pages_without_duplicates_and_reports_metadata(tmp_path):
    for index in range(211):
        (tmp_path / f'item-{index}.txt').write_bytes(b'row\n')
    (tmp_path / '.hidden').write_text('secret', encoding='utf-8')
    service = service_for(tmp_path)
    try:
        page = service.list({'storage_id': 'data'}, principal='alice')
        assert len(page.entries) == 200
        assert not page.complete and page.order == 'filesystem'
        assert all(item.size_bytes == 4 and item.kind == 'file' for item in page.entries)
        all_names = [item.name for item in page.entries]
        revision = page.listing_revision
        while not page.complete:
            page = service.list({'storage_id': 'data', 'cursor': page.next_cursor}, principal='alice')
            assert page.listing_revision == revision
            all_names.extend(item.name for item in page.entries)
        assert len(all_names) == len(set(all_names)) == 211
        assert '.hidden' not in all_names
        assert service.status()['browse_handles'] == 0
    finally:
        service.close()


def test_cursor_is_principal_session_directory_and_filter_scoped(tmp_path):
    (tmp_path / 'one').write_text('a')
    (tmp_path / 'two').write_text('b')
    service = service_for(tmp_path)
    try:
        page = service.list({'storage_id': 'data', 'page_size': 1}, principal='alice', session_id='tab-a')
        for principal, session_id, extra in [('bob', 'tab-a', {}), ('alice', 'tab-b', {}),
                                            ('alice', 'tab-a', {'hidden': True}),
                                            ('alice', 'tab-a', {'relative_path': 'subdir'})]:
            with pytest.raises(StorageError) as error:
                service.list({'storage_id': 'data', 'cursor': page.next_cursor, **extra},
                             principal=principal, session_id=session_id)
            assert error.value.code == 'browse_cursor_scope'
        assert service.status()['browse_handles'] == 1
        with pytest.raises(StorageError) as error:
            service.cancel(page.next_cursor, principal='bob', session_id='tab-a')
        assert error.value.code == 'browse_cursor_scope'
        assert service.cancel_session(principal='alice', session_id='tab-b') == 0
        assert service.cancel_session(principal='alice', session_id='tab-a') == 1
    finally:
        service.close()


def test_expired_cursor_releases_handle_and_requires_restart(tmp_path):
    (tmp_path / 'file').touch()
    now = [0.0]
    service = service_for(tmp_path, clock=lambda: now[0])
    page = service.list({'storage_id': 'data', 'page_size': 1}, principal='alice')
    now[0] = 30
    with pytest.raises(StorageError) as error:
        service.list({'storage_id': 'data', 'cursor': page.next_cursor}, principal='alice')
    assert error.value.code == 'browse_cursor_expired'
    assert error.value.next_actions == ({'action': 'restart_browse', 'cursor': None},)
    assert service.status()['browse_handles'] == 0
    service.close()


def test_directory_change_and_mount_rebind_invalidate_cursor(tmp_path):
    (tmp_path / 'one').touch()
    service = service_for(tmp_path)
    page = service.list({'storage_id': 'data', 'page_size': 1}, principal='alice')
    before = tmp_path.stat()
    (tmp_path / 'two').touch()
    os.utime(tmp_path, ns=(before.st_atime_ns, before.st_mtime_ns + 2_000_000_000))
    with pytest.raises(StorageError) as error:
        service.list({'storage_id': 'data', 'cursor': page.next_cursor}, principal='alice')
    assert error.value.code == 'browse_changed'
    assert service.status()['browse_handles'] == 0
    page = service.list({'storage_id': 'data', 'page_size': 1}, principal='alice')
    service.mounts.register('data', LocalStorage(tmp_path), principals=('alice',))
    with pytest.raises(StorageError) as error:
        service.list({'storage_id': 'data', 'cursor': page.next_cursor}, principal='alice')
    assert error.value.code == 'browse_changed'
    assert service.status()['browse_handles'] == 0
    service.close()


def test_handle_admission_is_bounded_and_cancel_reclaims_capacity(tmp_path):
    (tmp_path / 'item').touch()
    service = service_for(tmp_path, limits=BrowseLimits(max_handles=2, handles_per_principal=1))
    page = service.list({'storage_id': 'data', 'page_size': 1}, principal='alice')
    with pytest.raises(StorageError) as error:
        service.list({'storage_id': 'data', 'page_size': 1}, principal='alice')
    assert error.value.code == 'storage_busy'
    other = service.list({'storage_id': 'data', 'page_size': 1}, principal='bob')
    assert service.status()['browse_handles'] == 2
    assert service.cancel(page.next_cursor, principal='alice')
    assert service.cancel(other.next_cursor, principal='bob')
    assert service.status()['browse_handles'] == 0
    service.close()


def test_preview_limits_rows_bytes_and_reports_decoding_loss(tmp_path):
    (tmp_path / 'many.txt').write_bytes(b'abcdef\n' * 20000)
    (tmp_path / 'binary').write_bytes(b'\xff\x00')
    service = service_for(tmp_path)
    preview = service.preview({'storage_id': 'data', 'relative_path': 'many.txt'}, principal='alice')
    assert preview.bytes_read == 64 * 1024
    assert preview.rows == 100 and preview.text == 'abcdef\n' * 100
    assert preview.truncated and not preview.decoding_errors
    bounded = service.preview({'storage_id': 'data', 'relative_path': 'many.txt',
                               'byte_limit': 3}, principal='alice')
    assert bounded.text == 'abc' and bounded.bytes_read == 3
    binary = service.preview({'storage_id': 'data', 'relative_path': 'binary'}, principal='alice')
    assert binary.decoding_errors
    with pytest.raises(ValidationError):
        PreviewRequest(storage_id='data', relative_path='many.txt', byte_limit=1024 * 1024 + 1)
    with pytest.raises(StorageError) as error:
        service.preview({'storage_id': 'data', 'relative_path': '.'}, principal='alice')
    assert error.value.code == 'storage_not_file'
    service.close()


def test_stat_checks_authorization_and_supplied_metadata_version(tmp_path):
    (tmp_path / 'file').write_bytes(b'old')
    service = service_for(tmp_path)
    entry = service.stat(reference('data', 'file'), principal='alice')
    assert entry.size_bytes == 3 and entry.ref.digest is None
    (tmp_path / 'file').write_bytes(b'replacement')
    with pytest.raises(StorageError) as error:
        service.stat(entry.ref, principal='alice')
    assert error.value.code == 'storage_changed'
    with pytest.raises(StorageError) as error:
        service.stat(reference('data', 'file'), principal='stranger')
    assert error.value.code == 'storage_forbidden'
    service.close()


def test_local_symlinks_are_confined_and_escaping_links_are_not_previewed(tmp_path):
    root = tmp_path / 'root'
    root.mkdir()
    (root / 'inside').write_text('permitted')
    (tmp_path / 'secret').write_text('forbidden')
    try:
        (root / 'allowed').symlink_to(root / 'inside')
        (root / 'escape').symlink_to(tmp_path / 'secret')
    except OSError as exc:
        pytest.skip(f'Local symlink creation unavailable: {exc}')
    service = service_for(root)
    assert service.preview({'storage_id': 'data', 'relative_path': 'allowed'}, principal='alice').text == 'permitted'
    with pytest.raises(StorageError) as error:
        service.preview({'storage_id': 'data', 'relative_path': 'escape'}, principal='alice')
    assert error.value.code == 'storage_path_forbidden'
    page = service.list({'storage_id': 'data'}, principal='alice')
    escaped = next(item for item in page.entries if item.name == 'escape')
    assert escaped.is_symlink and not escaped.accessible and escaped.kind == 'symlink'
    service.close()


class FakeSFTP:
    """Synthetic storage-only protocol adapter backed by a private temp root."""
    def __init__(self, root):
        self.root = root
        self.closed = False
        self.read_aheads = []
        self.yielded = 0
        self.reads = []
        self.stat_calls = []
        self.lstat_calls = []
        self.forced_names = None

    def path(self, value):
        return self.root / value.lstrip('/')

    def normalize(self, value):
        return '/' + self.path(value).resolve().relative_to(self.root.resolve()).as_posix()

    @staticmethod
    def attrs(value, **extra):
        return SimpleNamespace(st_mode=value.st_mode, st_size=value.st_size,
                               st_mtime=int(value.st_mtime), **extra)

    def stat(self, value):
        self.stat_calls.append(value)
        return self.attrs(self.path(value).stat())

    def lstat(self, value):
        self.lstat_calls.append(value)
        return self.attrs(self.path(value).lstat())

    def listdir_iter(self, value, *, read_aheads):
        self.read_aheads.append(read_aheads)
        names = self.forced_names
        if names is None:
            names = (entry.name for entry in self.path(value).iterdir())
        for name in names:
            if self.closed:
                raise OSError('closed')
            self.yielded += 1
            if self.forced_names is None:
                yield self.attrs((self.path(value) / name).stat(), filename=name)
            else:
                # Forced hidden names deliberately need no filesystem stat.
                yield SimpleNamespace(filename=name, st_mode=stat.S_IFREG | 0o600,
                                      st_size=0, st_mtime=0)

    def open(self, value, mode):
        handle = self.path(value).open(mode)
        owner = self
        class File:
            def stat(self): return owner.attrs(os.fstat(handle.fileno()))
            def read(self, limit):
                owner.reads.append(limit)
                return handle.read(limit)
            def __enter__(self): return self
            def __exit__(self, *_): handle.close()
        return File()

    def get_channel(self): return self
    def close(self): self.closed = True


def sftp_service(tmp_path, *, limits=None, configure=None):
    (tmp_path / 'store').mkdir(exist_ok=True)
    opened = []
    def connector():
        sftp = FakeSFTP(tmp_path)
        if configure:
            configure(sftp)
        opened.append(sftp)
        return SimpleNamespace(sftp=sftp, close=sftp.close)
    mounts = MountMap()
    mounts.register('remote', SFTPStorage('/store', connector), principals=('alice',))
    return StorageService(mounts, limits=limits), opened


def test_hidden_heavy_sftp_listing_stops_after_raw_scan_budget(tmp_path):
    service, opened = sftp_service(tmp_path, limits=BrowseLimits(max_scan_entries=7),
                                  configure=lambda sftp: setattr(sftp, 'forced_names', iter('.hidden' for _ in range(10000))))
    page = service.list({'storage_id': 'remote'}, principal='alice')
    assert not page.complete and not page.entries and page.scanned == 7
    assert opened[0].yielded == 7 and opened[0].read_aheads == [1]
    assert service.cancel(page.next_cursor, principal='alice')
    assert opened[0].closed
    service.close()


def test_sftp_preview_and_stat_need_only_storage_subsystem(tmp_path):
    service, opened = sftp_service(tmp_path)
    (tmp_path / 'store' / 'file').write_bytes(b'line\n' * 20000)
    entry = service.stat(reference('remote', 'file'), principal='alice')
    assert entry.size_bytes == 100000 and opened[-1].closed
    preview = service.preview({'storage_id': 'remote', 'relative_path': 'file'}, principal='alice')
    assert preview.rows == 100 and opened[-1].reads == [65536] and opened[-1].closed
    service.close()


def test_sftp_page_reuses_readdir_metadata_without_per_file_round_trips(tmp_path):
    service, opened = sftp_service(tmp_path)
    for index in range(12):
        (tmp_path / 'store' / f'item-{index}').write_bytes(b'payload')
    page = service.list({'storage_id': 'remote', 'page_size': 5}, principal='alice')
    assert len(page.entries) == 5 and all(entry.size_bytes == 7 for entry in page.entries)
    assert opened[0].yielded == 5
    assert opened[0].lstat_calls == []
    assert opened[0].stat_calls == ['/store'] * 3
    service.close()


def test_sftp_canonical_escape_is_rejected_without_read(tmp_path):
    def configure(sftp):
        original = sftp.normalize
        sftp.normalize = lambda value: '/outside/file' if value.endswith('/escape') else original(value)
    service, opened = sftp_service(tmp_path, configure=configure)
    (tmp_path / 'store' / 'escape').write_text('never read')
    with pytest.raises(StorageError) as error:
        service.preview({'storage_id': 'remote', 'relative_path': 'escape'}, principal='alice')
    assert error.value.code == 'storage_path_forbidden'
    assert opened[-1].reads == [] and opened[-1].closed
    service.close()


def test_cancel_during_enumeration_closes_owned_handle(tmp_path):
    event = threading.Event()
    def configure(sftp):
        def names():
            yield '.one'
            event.set()
            yield '.two'
            pytest.fail('Enumeration continued after cancellation')
        sftp.forced_names = names()
    service, opened = sftp_service(tmp_path, configure=configure)
    with pytest.raises(StorageError) as error:
        service.list({'storage_id': 'remote'}, principal='alice', cancel=event)
    assert error.value.code == 'storage_cancelled'
    assert opened[0].yielded == 2 and opened[0].closed
    assert service.status()['browse_handles'] == 0
    service.close()


def test_cancel_session_interrupts_blocked_sftp_listing_and_releases_slot(tmp_path):
    started, released = threading.Event(), threading.Event()
    outcomes = []
    def configure(sftp):
        def names():
            started.set()
            assert released.wait(5), 'Cancellation did not close the owned channel'
            raise OSError('channel closed')
            yield  # Make this a lazy generator.
        sftp.forced_names = names()
        original_close = sftp.close
        def close():
            original_close()
            released.set()
        sftp.close = close
    service, opened = sftp_service(tmp_path, configure=configure)
    def browse():
        try:
            service.list({'storage_id': 'remote'}, principal='alice', session_id='tab')
        except StorageError as exc:
            outcomes.append(exc.code)
    worker = threading.Thread(target=browse)
    worker.start()
    try:
        assert started.wait(5)
        assert service.cancel_session(principal='alice', session_id='tab') == 1
    finally:
        released.set()
        worker.join(5)
        service.close()
    assert not worker.is_alive()
    assert outcomes == ['storage_cancelled'] and opened[0].closed
    assert service.status()['active_io'] == 0


class Key:
    def __init__(self, text): self.text = text
    def get_name(self): return 'ssh-test'
    def get_base64(self): return self.text
    def asbytes(self): return self.text.encode()


def install_fake_ssh(monkeypatch, *, changed=None):
    paramiko = pytest.importorskip('paramiko')
    clients, calls = [], []
    class Channel:
        closed = False
        def close(self): self.closed = True
        def settimeout(self, value): calls.append(('timeout', value))
    tunnel = Channel()
    class Client:
        def __init__(self): self.closed = False; clients.append(self)
        def set_missing_host_key_policy(self, policy): self.policy = policy
        def connect(self, host, **kwargs):
            self.host = host
            calls.append(('connect', host, kwargs))
            self.policy.missing_host_key(self, host, Key('changed' if host == changed else host))
        def get_transport(self): return self
        def set_keepalive(self, value): pass
        def open_channel(self, kind, destination, origin, timeout):
            calls.append(('channel', kind, destination, origin, timeout))
            return tunnel
        def open_sftp(self):
            calls.append(('sftp', self.host))
            channel = Channel()
            return SimpleNamespace(close=channel.close, get_channel=lambda: channel)
        def close(self): self.closed = True
    monkeypatch.setattr(paramiko, 'SSHClient', Client)
    return clients, calls, tunnel


def profile(host):
    return {'host': host, 'port': 22, 'username': 'synthetic', 'auth': 'agent', 'key_path': '',
            'host_key': {'type': 'ssh-test', 'base64': host}}


def test_jump_uses_direct_tcpip_and_separately_checks_both_host_keys(monkeypatch):
    clients, calls, tunnel = install_fake_ssh(monkeypatch)
    connection = SFTPConnection(profile('destination'), {}, jump_profile=profile('bastion'), jump_credentials={})
    assert [call[1] for call in calls if call[0] == 'connect'] == ['bastion', 'destination']
    channel = next(call for call in calls if call[0] == 'channel')
    assert channel[1:4] == ('direct-tcpip', ('destination', 22), ('127.0.0.1', 0))
    destination = next(call for call in calls if call[:2] == ('connect', 'destination'))
    assert destination[2]['sock'] is tunnel
    assert [call for call in calls if call[0] == 'sftp'] == [('sftp', 'destination')]
    connection.close()
    assert all(client.closed for client in clients) and tunnel.closed


@pytest.mark.parametrize('changed', ['bastion', 'destination'])
def test_changed_jump_or_target_key_stops_connection_and_closes_owned_resources(monkeypatch, changed):
    clients, calls, tunnel = install_fake_ssh(monkeypatch, changed=changed)
    with pytest.raises(HostKeyRequired) as error:
        SFTPConnection(profile('destination'), {}, jump_profile=profile('bastion'))
    assert error.value.changed
    assert all(client.closed for client in clients)
    assert not [call for call in calls if call[0] == 'sftp']
    if changed == 'destination':
        assert tunnel.closed


def test_unknown_key_and_shell_proxy_command_are_never_accepted(monkeypatch):
    clients, calls, _ = install_fake_ssh(monkeypatch)
    target = profile('destination')
    target.pop('host_key')
    with pytest.raises(HostKeyRequired) as error:
        SFTPConnection(target, {})
    assert not error.value.changed and clients[-1].closed
    target = {**profile('destination'), 'ProxyCommand': 'never execute this'}
    with pytest.raises(StorageError) as error:
        SFTPConnection(target, {})
    assert error.value.code == 'storage_route_unsupported'
