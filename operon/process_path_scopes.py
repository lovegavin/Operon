"""Attempt-scoped cwd metadata recovery after confirmed process-tree exit.

Only the supervisor may call release_scope with confirmed=True. A dead PID is
not evidence. No global sweep, data copying or recursive target deletion occurs.
Old unscoped journals are deliberately retained as diagnostic evidence.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from operon.bytecode import io_path
from operon.engine.fs import atomic_json
from operon.environment_store.windows_paths import _logical_path, _plain_directory, _entry

SCOPE_ENV = 'OPERON_PROCESS_CWD_SCOPE'
RECEIPT = 'process-cwd-scope.json'


def _identity(attempt_root, attempt_id, fence):
    root = str(_logical_path(io_path(attempt_root).resolve(strict=True)))
    value = {'attempt_root': root, 'attempt_id': str(attempt_id), 'fence': int(fence)}
    scope_id = hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
    return {'format': 'operon.process-cwd-scope', 'version': 1, **value, 'scope_id': scope_id}


def _layout(value):
    from .process_paths import _alias_root
    from operon.environment_store.windows_paths import _NativeJunctions
    expected = _identity(value['attempt_root'], value['attempt_id'], value['fence'])
    if value != expected:
        raise ValueError('Process cwd scope identity differs')
    base = _alias_root(None, _NativeJunctions())
    return base, base / ('scope-' + value['scope_id'][:32])


def prepare_scope(attempt_root, *, attempt_id, fence):
    """Bind worker metadata to an attempt before any worker can be spawned."""
    if os.name != 'nt':
        return {}
    value = _identity(attempt_root, attempt_id, fence)
    root = io_path(attempt_root)
    receipt = root / RECEIPT
    if receipt.exists() and json.loads(receipt.read_text(encoding='utf-8')) != value:
        raise ValueError('Process cwd attempt receipt differs')
    atomic_json(receipt, value)
    return {SCOPE_ENV: json.dumps(value)}


def worker_scope(target):
    """Validate inherited attempt scope; never silently discard a bad binding."""
    raw = os.environ.get(SCOPE_ENV)
    if not raw:
        return None
    value = json.loads(raw)
    base, directory = _layout(value)
    root = _logical_path(io_path(value['attempt_root']).resolve(strict=True))
    # The metadata belongs to the attempt. A tool may legitimately use an
    # external input directory as cwd; cleanup never owns or deletes that data.
    receipt = io_path(root / RECEIPT)
    if json.loads(receipt.read_text(encoding='utf-8')) != value:
        raise ValueError('Process cwd scope receipt differs')
    from operon.engine.fs import FileLock
    with FileLock(io_path(root / 'process-cwd-scope.lock')):
        _plain_directory(directory, create=True)
        marker = directory / 'scope.json'
        if _entry(marker) is not None:
            _plain_file(marker)
            if json.loads(marker.read_text(encoding='utf-8')) != value:
                raise ValueError('Process cwd metadata scope differs')
        else:
            atomic_json(marker, value)
    return value, directory


def _plain_file(path):
    entry = _entry(path)
    import stat
    if (entry is None or not stat.S_ISREG(entry.st_mode)
            or getattr(entry, 'st_file_attributes', 0) & 0x400):
        raise ValueError('Process cwd metadata is not an ordinary file')


def release_scope(attempt_root, *, attempt_id, fence, confirmed):
    """Recover only exact registered metadata after durable tree-exit proof."""
    if os.name != 'nt':
        return None
    root = io_path(attempt_root)
    receipt = root / RECEIPT
    if not receipt.exists():
        return None  # Legacy attempt: do not guess ownership from dead PIDs.
    _plain_file(receipt)
    value = json.loads(receipt.read_text(encoding='utf-8'))
    if value != _identity(root, attempt_id, fence):
        raise ValueError('Process cwd recovery attempt/fence differs')
    _, directory = _layout(value)
    report = {'format': 'operon.process-cwd-cleanup', 'scope_id': value['scope_id'],
              'attempt_id': attempt_id, 'fence': fence, 'removed': [], 'errors': [],
              'state': 'cleaned' if confirmed else 'recovery_required',
              'tree_exited': bool(confirmed)}
    from operon.engine.fs import FileLock
    from operon.environment_store.windows_paths import _NativeJunctions
    with FileLock(root / 'process-cwd-scope.lock'):
        prior = root / 'process-cwd-cleanup.json'
        if confirmed and _entry(directory) is None and prior.is_file():
            previous = json.loads(prior.read_text(encoding='utf-8'))
            if previous.get('scope_id') == value['scope_id'] and previous.get('state') == 'cleaned':
                return previous
        if _entry(directory) is not None:
            _plain_directory(directory)
            marker = directory / 'scope.json'
            _plain_file(marker)
            if json.loads(marker.read_text(encoding='utf-8')) != value:
                raise ValueError('Process cwd recovery metadata differs')
            if confirmed:
                api = _NativeJunctions()
                for entry in directory.iterdir():
                    if entry.name == 'scope.json':
                        continue
                    try:
                        _plain_directory(entry)
                        if not entry.name.startswith('operon-cwd-'):
                            raise ValueError('Unknown scope metadata entry')
                        journal = entry / 'owner.json'
                        _plain_file(journal)
                        record = json.loads(journal.read_text(encoding='utf-8'))
                        alias = entry / 'cwd'
                        if (record.get('format') != 'operon.process-cwd'
                                or record.get('version') != 2 or record.get('scope') != value
                                or record.get('alias') != str(alias)):
                            raise ValueError('Cwd alias ownership differs')
                        target = _logical_path(Path(record['target']))
                        if not target.is_absolute() or '..' in target.parts:
                            raise ValueError('Cwd target spelling is not canonical')
                        if set(p.name for p in entry.iterdir()) - {'owner.json', 'cwd'}:
                            raise ValueError('Unknown contents in cwd metadata')
                        # Persist intent before deleting the junction, so interrupted
                        # cleanup is retryable; never traverse its target.
                        if _entry(alias) is not None:
                            api.verify(alias, target)
                        record['state'] = 'recovery_required'
                        atomic_json(journal, record)
                        if _entry(alias) is not None:
                            api.remove(alias)
                        journal.unlink()
                        entry.rmdir()
                        report['removed'].append(entry.name)
                    except (OSError, ValueError, KeyError, TypeError) as exc:
                        report['errors'].append({'entry': entry.name, 'error': str(exc)})
                if not report['errors']:
                    marker.unlink()
                    directory.rmdir()
                else:
                    report['state'] = 'recovery_required'
        atomic_json(root / 'process-cwd-cleanup.json', report)
    return report
