"""Immutable artifact staging, verification and fenced publication.

Filesystem rename and database registration are not one transaction.  A commit
receipt plus explicit reconciliation handles a crash between staging, rename,
receipt publication and database registration.  A stale attempt can never
publish over a newer one.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import time
import uuid

from .contracts import CorruptArtifactError, StaleAttemptError, canonical, digest
from .state import now_iso
from .telemetry import METRICS
from biopipe.bytecode import io_path

CHUNK = 1024 * 1024


class ArtifactError(CorruptArtifactError):
    code = 'corrupt_artifact'


class CommitInterrupted(Exception):
    """Injected crash used by tests; not a product failure path."""


def _sha256_file(path: Path) -> tuple[str, int]:
    hasher = hashlib.sha256()
    size = 0
    with io_path(path).open('rb') as stream:
        while True:
            block = stream.read(CHUNK)
            if not block:
                break
            size += len(block)
            hasher.update(block)
    return hasher.hexdigest(), size


def _normalize_relative(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise ArtifactError('Artifact paths must be nonempty strings')
    if '\x00' in value:
        raise ArtifactError('Artifact paths cannot contain NUL bytes')
    path = PurePosixPath(value.replace('\\', '/'))
    if path.is_absolute() or path.drive or '..' in path.parts or path.parts[:1] == ('',):
        raise ArtifactError(f'Artifact path escapes its owned staging directory: {value!r}')
    if not path.parts or any(part in ('', '.') for part in path.parts):
        raise ArtifactError(f'Invalid artifact path: {value!r}')
    return path.as_posix()


def _reject_symlinks(root: Path, relative: str) -> None:
    current = io_path(root)
    for part in PurePosixPath(relative).parts:
        current = current / part
        try:
            info = current.lstat()
        except FileNotFoundError as exc:
            raise ArtifactError(f'Artifact file is missing: {relative}') from exc
        if current.is_symlink() or (hasattr(current, 'is_junction') and current.is_junction()):
            raise ArtifactError(f'Artifact path contains a link: {relative}')
        if getattr(info, 'st_file_attributes', 0) & 0x400:  # FILE_ATTRIBUTE_REPARSE_POINT
            raise ArtifactError(f'Artifact path contains a reparse point: {relative}')


def _within(root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False


@dataclass(frozen=True)
class StagedOutput:
    directory: Path
    relative: str
    size: int
    sha256: str
    role: str = ''

    def to_json(self) -> dict:
        return {'path': self.relative, 'size': self.size, 'sha256': self.sha256,
                **({'role': self.role} if self.role else {})}


class ArtifactCommitter:
    """Stage, verify and publish immutable artifacts for one engine root."""

    def __init__(self, root, store=None, *, crash_point=None, retain_failed=True):
        self.root = Path(root)
        self.store = store
        self.crash_point = crash_point
        self.retain_failed = retain_failed
        self.artifacts = self.root / 'artifacts'
        self.artifacts.mkdir(parents=True, exist_ok=True)

    # -- attempt layout -------------------------------------------------
    def attempt_directory(self, run_id: str, unit_label: str, attempt_id: str) -> Path:
        safe = lambda value: str(value).replace('/', '_').replace('\\', '_')
        return self.root / 'runs' / safe(run_id) / 'nodes' / safe(unit_label) / 'attempts' / safe(attempt_id)

    def ensure_attempt(self, run_id: str, unit_label: str, attempt_id: str) -> Path:
        directory = self.attempt_directory(run_id, unit_label, attempt_id)
        for name in ('tmp', 'spill', 'ipc', 'output-staging', 'logs'):
            (directory / name).mkdir(parents=True, exist_ok=True)
        return directory

    def staging(self, run_id: str, unit_label: str, attempt_id: str) -> Path:
        return self.ensure_attempt(run_id, unit_label, attempt_id) / 'output-staging'

    # -- commit ---------------------------------------------------------
    def _validate(self, attempt: dict, unit: dict, staging: Path, manifest: dict,
                  fence: int) -> tuple[list[dict], dict]:
        if int(attempt['fence']) != int(fence):
            raise StaleAttemptError('The attempt fence is stale; publication is refused',
                                    details={'attempt_id': attempt.get('id'), 'fence': fence})
        if self.store is not None:
            stored = self.store.attempt(attempt['id'])
            if int(stored['fence']) != int(fence):
                raise StaleAttemptError('The stored attempt fence is stale',
                                        details={'attempt_id': attempt['id']})
            if stored['state'] in ('succeeded', 'failed', 'cancelled'):
                raise StaleAttemptError('A terminal attempt cannot publish an artifact')
            if stored['unit_id'] != unit['id']:
                raise StaleAttemptError('The attempt does not belong to this unit')
        entries = manifest.get('files', manifest.get('entries', []))
        if not isinstance(entries, list) or not entries:
            raise ArtifactError('An artifact manifest requires at least one file')
        files, total = [], 0
        seen = set()
        for item in entries:
            if not isinstance(item, dict):
                raise ArtifactError('Artifact manifest entries must be objects')
            relative = _normalize_relative(item.get('path') or item.get('name'))
            if relative in seen:
                raise ArtifactError(f'Duplicate artifact path: {relative}')
            seen.add(relative)
            _reject_symlinks(staging, relative)
            source = staging / relative
            if not source.is_file():
                raise ArtifactError(f'Staged artifact is not a regular file: {relative}')
            checksum, size = _sha256_file(source)
            declared = item.get('sha256')
            if declared is not None and str(declared).lower() != checksum:
                raise ArtifactError(f'Artifact digest mismatch for {relative}')
            declared_size = item.get('size')
            if declared_size is not None and int(declared_size) != size:
                raise ArtifactError(f'Artifact size mismatch for {relative}')
            files.append({'path': relative, 'size': size, 'sha256': checksum,
                          **({'role': str(item['role'])} if item.get('role') else {})})
            total += size
        normalized = {
            'schema_version': 1,
            'kind': str(manifest.get('kind', 'files')),
            'files': files,
            'form': manifest.get('form'),
            'metadata': manifest.get('metadata') or {},
            'info': manifest.get('info') or {},
            'axis_info': manifest.get('axis_info') or {},
            'labels': manifest.get('labels') or {},
            'total_bytes': total,
        }
        return files, normalized

    def commit(self, *, attempt: dict, unit: dict, fence: int, manifest: dict,
               run_id: str | None = None, unit_label: str | None = None) -> dict:
        run_id = run_id or unit.get('run_id') or ''
        unit_label = unit_label or unit.get('local_id') or unit['id']
        staging = self.staging(run_id, unit_label, attempt['id'])
        files, normalized = self._validate(attempt, unit, staging, manifest, fence)
        identity = digest({'files': files, 'kind': normalized['kind'], 'form': normalized['form'],
                           'metadata': normalized['metadata'], 'labels': normalized['labels'],
                           'axis_info': normalized['axis_info'], 'info': normalized['info']})
        artifact_id = 'art-' + identity[:32]
        final = self.artifacts / artifact_id
        receipt_path = final / 'receipt.json'
        manifest_path = final / 'manifest.json'
        if final.exists():
            receipt = self._read_json(receipt_path)
            if receipt and receipt.get('digest') == identity:
                if self.store is not None:
                    known = self.store.artifact(artifact_id)
                    if known is None:
                        self.store.record_artifact(artifact_id=artifact_id, attempt_id=attempt['id'],
                                                   fence=int(fence), manifest=normalized, digest=identity,
                                                   size_bytes=normalized['total_bytes'], state='renamed',
                                                   location=str(final))
                    self.store.update_artifact(artifact_id, state='committed', location=str(final))
                return self._publish(attempt, unit, run_id, artifact_id, identity, normalized, final,
                                     state='committed', reused=True)
            raise ArtifactError('An immutable artifact id already exists with different content',
                                details={'artifact_id': artifact_id})
        temporary = self.artifacts / ('.tmp-' + artifact_id + '-' + uuid.uuid4().hex[:8])
        temporary.mkdir(parents=True)
        try:
            for item in files:
                target = temporary / item['path']
                target.parent.mkdir(parents=True, exist_ok=True)
                source = staging / item['path']
                with source.open('rb') as reader, target.open('wb') as writer:
                    while True:
                        block = reader.read(CHUNK)
                        if not block:
                            break
                        writer.write(block)
                    writer.flush()
                    os.fsync(writer.fileno())
                checksum, size = _sha256_file(target)
                if checksum != item['sha256'] or size != item['size']:
                    raise ArtifactError(f'Copy verification failed for {item["path"]}')
            (temporary / 'manifest.json').write_text(
                json.dumps(normalized, indent=2, sort_keys=True, ensure_ascii=False), encoding='utf-8')
            receipt = {'schema_version': 1, 'artifact_id': artifact_id, 'digest': identity,
                       'attempt_id': attempt['id'], 'fence': int(fence), 'run_id': run_id,
                       'unit_id': unit['id'], 'state': 'staged', 'location': str(final),
                       'created_at': now_iso(), 'total_bytes': normalized['total_bytes']}
            (temporary / 'receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
        except BaseException:
            shutil.rmtree(temporary, ignore_errors=True)
            raise
        self._crash('staged')
        try:
            os.replace(temporary, final)
        except OSError:
            # Windows cannot replace an existing non-empty directory; only a
            # verified identical final directory is an acceptable replay.
            existing = self._read_json(final / 'receipt.json')
            if not existing or existing.get('digest') != identity:
                shutil.rmtree(temporary, ignore_errors=True)
                raise
            shutil.rmtree(temporary, ignore_errors=True)
        self._crash('renamed')
        receipt['state'] = 'renamed'
        (final / 'receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
        self._crash('receipt')
        if self.store is not None:
            known = self.store.artifact(artifact_id)
            if known is None:
                self.store.record_artifact(artifact_id=artifact_id, attempt_id=attempt['id'],
                                           fence=int(fence), manifest=normalized, digest=identity,
                                           size_bytes=normalized['total_bytes'], state='renamed',
                                           location=str(final))
            self.store.update_artifact(artifact_id, state='committed', location=str(final))
        self._crash('database')
        METRICS.increment('artifacts.committed')
        return self._publish(attempt, unit, run_id, artifact_id, identity, normalized, final,
                             state='committed', reused=False)

    def commit_existing(self, *, attempt: dict, unit: dict, fence: int, source_root,
                        files: list[str], run_id: str | None = None,
                        kind: str = 'job-output', metadata: dict | None = None) -> dict:
        """Register an already-final directory as an immutable artifact.

        The scientific worker writes its output directory directly; this
        records a verified manifest without copying or moving the payload.  It
        is used only after the worker tree has exited, so the bytes are final.
        """
        if int(attempt['fence']) != int(fence):
            raise StaleAttemptError('The attempt fence is stale; publication is refused')
        source_root = Path(source_root)
        entries = []
        for relative in files:
            relative = _normalize_relative(relative)
            _reject_symlinks(source_root, relative)
            path = io_path(source_root / relative)
            if not path.is_file():
                continue
            checksum, size = _sha256_file(path)
            entries.append({'path': relative, 'size': size, 'sha256': checksum})
        if not entries:
            raise ArtifactError('The job output directory has no publishable regular files')
        normalized = {'schema_version': 1, 'kind': kind, 'files': entries,
                      'metadata': metadata or {}, 'total_bytes': sum(item['size'] for item in entries)}
        identity = digest(normalized)
        artifact_id = 'art-' + identity[:32]
        final = self.artifacts / artifact_id
        final.mkdir(parents=True, exist_ok=True)
        (final / 'manifest.json').write_text(
            json.dumps(normalized, indent=2, sort_keys=True, ensure_ascii=False), encoding='utf-8')
        receipt = {'schema_version': 1, 'artifact_id': artifact_id, 'digest': identity,
                   'attempt_id': attempt['id'], 'fence': int(fence), 'run_id': run_id,
                   'unit_id': unit['id'], 'state': 'committed', 'location': str(source_root),
                   'created_at': now_iso(), 'committed_at': now_iso(),
                   'total_bytes': normalized['total_bytes'], 'kind': kind}
        (final / 'receipt.json').write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding='utf-8')
        if self.store is not None:
            known = self.store.artifact(artifact_id)
            if known is None:
                self.store.record_artifact(artifact_id=artifact_id, attempt_id=attempt['id'],
                                           fence=int(fence), manifest=normalized, digest=identity,
                                           size_bytes=normalized['total_bytes'], state='committed',
                                           location=str(source_root))
            else:
                self.store.update_artifact(artifact_id, state='committed', location=str(source_root))
            self.store.add_reference(artifact_id, owner=f'run:{run_id or attempt["id"]}',
                                     reason='job-output')
        METRICS.increment('artifacts.existing_committed')
        return receipt

    def verify_existing(self, receipt: dict, *, manifest: dict | None = None) -> dict:
        """Re-hash an existing-payload receipt before any cache reuse.

        Recording a manifest is not an immutable-content guarantee: the source
        directory belongs to the scientific job.  This check detects changed,
        missing or newly added files and returns a machine-readable result.
        """
        artifact_id = receipt.get('artifact_id')
        location = io_path(Path(receipt.get('location') or ''))
        if manifest is None and self.store is not None and artifact_id:
            try:
                record = self.store.artifact(artifact_id)
                manifest = record.get('manifest') if record else None
            except Exception:  # noqa: BLE001 - fall through to the receipt copy
                manifest = None
        if manifest is None and artifact_id:
            try:
                manifest = self._read_json(self.artifacts / artifact_id / 'manifest.json')
            except OSError:
                manifest = None
        if not manifest or not location.is_dir():
            return {'valid': False, 'artifact_id': artifact_id,
                    'errors': ['artifact manifest or payload location is unavailable'],
                    'checked_at': now_iso()}
        expected = {item['path']: item for item in manifest.get('files', [])}
        errors = []
        seen = set()
        if location.is_symlink() or (hasattr(location, 'is_junction') and location.is_junction()):
            errors.append('payload location is a link')
        for base, directories, names in os.walk(location):
            directories[:] = [name for name in directories
                              if not (Path(base) / name).is_symlink()]
            for name in names:
                path = Path(base) / name
                relative = path.relative_to(location).as_posix()
                if path.is_symlink():
                    errors.append(f'linked file is not allowed: {relative}')
                    continue
                if relative not in expected:
                    errors.append(f'unexpected file was added to the payload: {relative}')
                    continue
                seen.add(relative)
                try:
                    checksum, size = _sha256_file(path)
                except OSError as exc:
                    errors.append(f'cannot read {relative}: {exc}')
                    continue
                item = expected[relative]
                if size != int(item['size']) or checksum != item['sha256']:
                    errors.append(f'content changed: {relative}')
        for relative in sorted(set(expected) - seen):
            errors.append(f'file is missing: {relative}')
        return {'valid': not errors, 'artifact_id': artifact_id,
                'digest': receipt.get('digest'), 'checked_at': now_iso(),
                'files_checked': len(seen), 'errors': errors[:100]}

    def _publish(self, attempt, unit, run_id, artifact_id, identity, manifest, final, *, state, reused):
        receipt = self._read_json(final / 'receipt.json') or {}
        receipt.update({'artifact_id': artifact_id, 'digest': identity, 'state': state,
                        'attempt_id': attempt['id'], 'fence': int(attempt['fence']),
                        'run_id': run_id, 'unit_id': unit['id'], 'location': str(final),
                        'total_bytes': manifest['total_bytes'], 'reused': reused,
                        'committed_at': now_iso()})
        (final / 'receipt.json').write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding='utf-8')
        if run_id:
            self._update_results(run_id, receipt, manifest)
        return receipt

        receipt = self._read_json(final / 'receipt.json') or {}
        receipt.update({'artifact_id': artifact_id, 'digest': identity, 'state': state,
                        'attempt_id': attempt['id'], 'fence': int(attempt['fence']),
                        'run_id': run_id, 'unit_id': unit['id'], 'location': str(final),
                        'total_bytes': manifest['total_bytes'], 'reused': reused,
                        'committed_at': now_iso()})
        (final / 'receipt.json').write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding='utf-8')
        if run_id:
            self._update_results(run_id, receipt, manifest)
        return receipt

    def _update_results(self, run_id, receipt, manifest):
        from .fs import FileLock, atomic_json
        directory = self.root / 'runs' / str(run_id).replace('/', '_') / 'results'
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / 'manifest.json'
        with FileLock(directory / '.lock'):
            values = self._read_json(path) or {'schema_version': 1, 'run_id': run_id, 'artifacts': []}
            values.setdefault('artifacts', [])
            values['artifacts'] = [item for item in values['artifacts']
                                   if item.get('artifact_id') != receipt['artifact_id']]
            values['artifacts'].append({'artifact_id': receipt['artifact_id'], 'digest': receipt['digest'],
                                        'unit_id': receipt['unit_id'], 'attempt_id': receipt['attempt_id'],
                                        'fence': receipt['fence'], 'state': receipt['state'],
                                        'total_bytes': receipt['total_bytes'], 'files': manifest['files'],
                                        'committed_at': receipt.get('committed_at')})
            values['updated_at'] = now_iso()
            atomic_json(path, values)
        return path

    def _crash(self, phase: str):
        if self.crash_point is not None:
            self.crash_point(phase)

    @staticmethod
    def _read_json(path):
        try:
            return json.loads(Path(path).read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return None

    # -- reconciliation ------------------------------------------------
    def reconcile(self, *, run_id: str | None = None) -> dict:
        """Resolve artifacts whose rename/receipt/DB phases were interrupted."""
        report = {'committed': 0, 'quarantined': 0, 'failed': 0, 'orphans': 0, 'repaired': 0}
        for folder in sorted(self.artifacts.iterdir()) if self.artifacts.exists() else []:
            if not folder.is_dir():
                continue
            if folder.name.startswith('.tmp-'):
                # Only remove a temporary directory that cannot belong to a
                # live commit in this process.  Old temp dirs are garbage.
                if time.time() - folder.stat().st_mtime > 300:
                    shutil.rmtree(folder, ignore_errors=True)
                continue
            receipt = self._read_json(folder / 'receipt.json')
            if not receipt:
                continue
            if run_id and receipt.get('run_id') != run_id:
                continue
            artifact_id = receipt.get('artifact_id') or folder.name
            known = self.store.artifact(artifact_id) if self.store is not None else None
            manifest = self._read_json(folder / 'manifest.json')
            if manifest is None or receipt.get('state') != 'committed' and not manifest:
                report['failed'] += 1
                continue
            if known is None:
                report['orphans'] += 1
                if self.store is None:
                    continue
                try:
                    self.store.record_artifact(artifact_id=artifact_id,
                                               attempt_id=receipt['attempt_id'], fence=int(receipt['fence']),
                                               manifest=manifest, digest=receipt['digest'],
                                               size_bytes=int(receipt.get('total_bytes', 0)),
                                               state='committed', location=str(folder))
                    report['repaired'] += 1
                except Exception:  # noqa: BLE001 - quarantine, never delete evidence
                    report['quarantined'] += 1
                continue
            if known['state'] != 'committed':
                self.store.update_artifact(artifact_id, state='committed', location=str(folder))
                report['committed'] += 1
            if run_id:
                receipt['state'] = 'committed'
                self._update_results(run_id, receipt, manifest)
        return report
