"""Reference-aware artifact and scratch cleanup.

Cleanup is conservative: active attempts, downstream references, retained
checkpoints and recently published results pin their artifacts.  Candidates are
verified to live beneath the engine artifact root before deletion, partial
failures are recorded, and unknown ownership stays quarantined.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import time

from .contracts import EngineError, RunState
from .telemetry import METRICS


class QuotaExceeded(EngineError):
    code = 'quota_exceeded'
    status = 422


@dataclass(frozen=True)
class CleanupCandidate:
    kind: str
    path: str
    reason: str
    size_bytes: int = 0
    artifact_id: str | None = None

    def to_json(self) -> dict:
        return {'kind': self.kind, 'path': self.path, 'reason': self.reason,
                'size_bytes': self.size_bytes, 'artifact_id': self.artifact_id}


class RetentionManager:
    def __init__(self, store, root, *, result_days=30.0, failed_days=7.0,
                 quota_bytes=None):
        self.store = store
        self.root = Path(root)
        self.artifacts = self.root / 'artifacts'
        self.runs = self.root / 'runs'
        self.result_seconds = max(0.0, float(result_days) * 86400)
        self.failed_seconds = max(0.0, float(failed_days) * 86400)
        self.quota_bytes = quota_bytes

    # -- accounting ----------------------------------------------------
    @staticmethod
    def _size(path: Path) -> int:
        total = 0
        for base, directories, files in os.walk(path):
            directories[:] = [name for name in directories
                              if not Path(base, name).is_symlink()]
            for name in files:
                item = Path(base, name)
                if item.is_symlink():
                    continue
                try:
                    total += item.stat().st_size
                except OSError:
                    continue
        return total

    def usage(self) -> dict:
        return {'artifacts_bytes': self._size(self.artifacts) if self.artifacts.exists() else 0,
                'runs_bytes': self._size(self.runs) if self.runs.exists() else 0,
                'quota_bytes': self.quota_bytes}

    # -- references ----------------------------------------------------
    def _pinned_attempts(self) -> set[str]:
        states = ['admitted', 'starting', 'running', 'committing', 'recovery_required']
        pool_id = self._pool_id()
        if not pool_id:
            return set()
        return {attempt['id'] for attempt in self.store.attempts_for_pool(pool_id, states=states)}

    def _pool_id(self):
        with self.store.lock:
            row = self.store.connection.execute('SELECT pool_id FROM pools ORDER BY created_at LIMIT 1').fetchone()
            return row['pool_id'] if row else ''

    def _published(self) -> set[str]:
        published = set()
        for path in self.runs.glob('*/results/manifest.json'):
            try:
                import json
                value = json.loads(path.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                continue
            for item in value.get('artifacts', []):
                if item.get('artifact_id'):
                    published.add(item['artifact_id'])
        return published

    def plan(self, *, now=None) -> dict:
        now = time.time() if now is None else now
        active = self._pinned_attempts()
        published = self._published()
        candidates, pinned, quarantine = [], [], []
        folders = sorted(self.artifacts.iterdir()) if self.artifacts.exists() else []
        for folder in folders:
            if not folder.is_dir():
                continue
            receipt_path = folder / 'receipt.json'
            receipt = None
            try:
                import json
                receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                pass
            artifact_id = (receipt or {}).get('artifact_id') or folder.name
            record = self.store.artifact(artifact_id) if not artifact_id.startswith('.') else None
            if record is None:
                quarantine.append(CleanupCandidate('artifact', str(folder), 'unknown-ownership',
                                                   self._size(folder), artifact_id).to_json())
                continue
            reason = self._pin_reason(record, receipt, active, published, now)
            if reason:
                pinned.append({'artifact_id': artifact_id, 'reason': reason,
                               'state': record['state']})
                continue
            if record['state'] not in ('committed', 'renamed', 'failed'):
                pinned.append({'artifact_id': artifact_id, 'reason': 'publication-pending',
                               'state': record['state']})
                continue
            candidates.append(CleanupCandidate('artifact', str(folder), 'retention-expired',
                                               self._size(folder), artifact_id).to_json())
        scratch = []
        for path in self.runs.glob('*/nodes/*/attempts/*') if self.runs.exists() else []:
            if not path.is_dir():
                continue
            attempt_id = path.name
            if attempt_id in active:
                continue
            try:
                age = now - path.stat().st_mtime
            except OSError:
                continue
            cutoff = self.failed_seconds if (path / 'checkpoint.json').exists() else self.failed_seconds
            if age >= cutoff:
                scratch.append(CleanupCandidate('attempt-scratch', str(path), 'retained-retry-window',
                                                self._size(path)).to_json())
        return {'candidates': candidates, 'scratch': scratch, 'pinned': pinned,
                'quarantine': quarantine, 'usage': self.usage()}

    def _pin_reason(self, record, receipt, active, published, now):
        if record['attempt_id'] in active:
            return 'active-attempt'
        try:
            if not Path(record['location']).resolve().is_relative_to(self.artifacts.resolve()):
                # JobService publishes a verified manifest over its existing
                # output directory; the payload is not ours to delete.
                return 'external-payload'
        except (OSError, ValueError):
            return 'unverifiable-location'
        references = self.store.references(record['id'])
        if references:
            return 'referenced'
        if record['id'] in published:
            try:
                committed = time.time() - _parse_iso(record.get('created_at')) if record.get('created_at') else 0
            except (TypeError, ValueError):
                committed = 0
            if committed < self.result_seconds:
                return 'published-result-retention'
        if (receipt or {}).get('kind') == 'checkpoint':
            return 'checkpoint'
        return None

    # -- apply ---------------------------------------------------------
    def apply(self, *, dry_run=False, now=None) -> dict:
        report = self.plan(now=now)
        deleted, errors = [], []
        for item in report['candidates'] + report['scratch']:
            path = Path(item['path'])
            if not self._safe(path, item['kind']):
                errors.append({**item, 'error': 'path-outside-owned-root'})
                continue
            if dry_run:
                deleted.append(item)
                continue
            try:
                if path.is_symlink():
                    raise OSError('refusing to delete a symbolic link')
                if path.is_dir():
                    shutil.rmtree(path)
                elif path.exists():
                    path.unlink()
                deleted.append(item)
                if item.get('artifact_id'):
                    self.store.update_artifact(item['artifact_id'], state='deleted', location=str(path))
            except OSError as exc:
                errors.append({**item, 'error': f'{type(exc).__name__}: {exc}'})
        METRICS.increment('retention.deleted', len(deleted))
        METRICS.increment('retention.errors', len(errors))
        return {**report, 'deleted': deleted, 'errors': errors, 'dry_run': dry_run,
                'usage_after': self.usage()}

    def _safe(self, path: Path, kind: str) -> bool:
        root = (self.artifacts if kind == 'artifact' else self.runs).resolve()
        try:
            resolved = path.resolve(strict=False)
            if not resolved.is_relative_to(root):
                return False
            if kind == 'artifact':
                return path.parent.resolve() == self.artifacts.resolve()
            return True
        except (OSError, ValueError):
            return False

    # -- quotas --------------------------------------------------------
    def enforce_quota(self, *, quota_bytes=None, dry_run=False) -> dict:
        quota = self.quota_bytes if quota_bytes is None else int(quota_bytes)
        if quota is None:
            return {'usage': self.usage(), 'evicted': [], 'over_quota': False}
        result = self.apply(dry_run=dry_run)
        usage = self.usage()['artifacts_bytes']
        evicted = []
        if usage > quota and not dry_run:
            # Prefer cache-like artifacts over published results; the plan
            # already excluded pinned and published artifacts.
            candidates = sorted((item for item in result['candidates']
                                 if item.get('artifact_id')),
                                key=lambda item: item['path'])
            for item in candidates:
                if usage <= quota:
                    break
                path = Path(item['path'])
                if not self._safe(path, 'artifact'):
                    continue
                try:
                    size = self._size(path) if path.is_dir() else path.stat().st_size
                    shutil.rmtree(path) if path.is_dir() else path.unlink()
                    self.store.update_artifact(item['artifact_id'], state='deleted', location=str(path))
                    usage -= size
                    evicted.append(item)
                except OSError:
                    continue
        over = usage > quota
        if over and not dry_run:
            raise QuotaExceeded('Artifact storage remains over quota after evicting unpinned cache',
                                details={'quota_bytes': quota, 'used_bytes': usage})
        return {'usage': self.usage(), 'evicted': evicted, 'over_quota': over, 'quota_bytes': quota}


def _parse_iso(value):
    from datetime import datetime
    return datetime.fromisoformat(value).timestamp()
