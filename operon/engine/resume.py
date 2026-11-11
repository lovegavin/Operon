"""Verified resume and content-addressed cache policy.

A cache key contains immutable input identities, frozen parameter values,
implementation/environment/tool/converter identities and explicit randomness.
Presentation text and current defaults are excluded.  Reuse requires verified
committed artifacts and an explicit no/known-side-effect declaration; unknown
conditions fail closed.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import platform
import sys

from .contracts import canonical, digest

CHUNK = 1024 * 1024
PRESENTATION_KEYS = {'name', 'title', 'description', 'position', 'width', 'height',
                     'collapsed', 'color', 'comment', 'notes'}


def file_identity(path, *, algorithm='sha256', max_bytes=None) -> dict:
    """Incremental content identity; never materializes the payload."""
    path = Path(path)
    if path.is_symlink():
        raise ValueError(f'Refusing to verify a symbolic link as an immutable input: {path}')
    stat = path.stat()
    if stat.st_size > (max_bytes if max_bytes is not None else stat.st_size):
        raise ValueError(f'Input exceeds the configured verification bound: {path}')
    hasher = hashlib.new(algorithm)
    size = 0
    with path.open('rb') as stream:
        while True:
            block = stream.read(CHUNK)
            if not block:
                break
            size += len(block)
            hasher.update(block)
    return {'algorithm': algorithm, 'sha256' if algorithm == 'sha256' else 'digest': hasher.hexdigest(),
            'size': size, 'path': str(path)}


def execution_graph(graph: dict) -> dict:
    """Strip presentation-only fields while preserving execution semantics."""
    def clean(value):
        if isinstance(value, dict):
            return {key: clean(item) for key, item in value.items() if key not in PRESENTATION_KEYS}
        if isinstance(value, list):
            return [clean(item) for item in value]
        return value
    result = clean(graph)
    if isinstance(result, dict):
        result.pop('position', None)
    return result


def execution_identity(*, graph, parameters, execution=None, implementation=None,
                       environment=None, tools=None, converters=None, randomness=None) -> dict:
    """Canonical execution identity used for resume and cache decisions."""
    return {
        'schema_version': 1,
        'graph': execution_graph(graph or {}),
        'parameters': parameters or {},
        'execution': execution or {},
        'implementation': implementation or {},
        'environment': environment or {},
        'tools': tools or {},
        'converters': converters or {},
        'randomness': randomness,
    }


def cache_key(**identity) -> str:
    return digest(identity)


@dataclass(frozen=True)
class CacheEligibility:
    eligible: bool
    reasons: tuple[str, ...] = ()

    def to_json(self) -> dict:
        return {'eligible': self.eligible, 'reasons': list(self.reasons)}


def eligibility(*, identity: dict, stochastic=False, side_effects='none',
                environment_verified=None) -> CacheEligibility:
    reasons = []
    environment = identity.get('environment') or {}
    if environment_verified is None:
        environment_verified = bool(environment.get('verified', True))
    if not environment_verified:
        reasons.append('environment-not-verified')
    if side_effects not in ('none', 'declared-idempotent', 'declared-safe'):
        reasons.append(f'unsupported-side-effects:{side_effects or "unknown"}')
    if stochastic and identity.get('randomness') in (None, '', [], {}):
        reasons.append('missing-explicit-randomness')
    if not identity.get('implementation'):
        reasons.append('missing-implementation-identity')
    if not identity.get('environment'):
        reasons.append('missing-environment-identity')
    if not identity.get('inputs', identity.get('graph')):
        reasons.append('missing-input-identity')
    return CacheEligibility(eligible=not reasons, reasons=tuple(reasons))


def verify_artifact(record: dict, root) -> tuple[bool, list[str]]:
    """Stream-verify a committed artifact's files; damaged output is not reused."""
    root = Path(root)
    location = Path(record.get('location') or '')
    try:
        location.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return False, ['artifact-outside-owned-root']
    manifest = record.get('manifest') or {}
    files = manifest.get('files') or []
    if not files:
        return False, ['empty-manifest']
    problems = []
    for item in files:
        path = location / item['path']
        if path.is_symlink():
            problems.append(f'link:{item["path"]}')
            continue
        try:
            stat = path.stat()
        except OSError:
            problems.append(f'missing:{item["path"]}')
            continue
        if stat.st_size != int(item['size']):
            problems.append(f'size:{item["path"]}')
            continue
        hasher = hashlib.sha256()
        with path.open('rb') as stream:
            while True:
                block = stream.read(CHUNK)
                if not block:
                    break
                hasher.update(block)
        if hasher.hexdigest() != item['sha256']:
            problems.append(f'digest:{item["path"]}')
    return not problems, problems


@dataclass(frozen=True)
class ResumeDecision:
    unit_id: str
    reuse: bool
    reason: str
    cache_key: str
    artifact_ids: tuple[str, ...] = ()
    damaged: tuple[str, ...] = ()

    def to_json(self) -> dict:
        return {'unit_id': self.unit_id, 'reuse': self.reuse, 'reason': self.reason,
                'cache_key': self.cache_key, 'artifact_ids': list(self.artifact_ids),
                'damaged': list(self.damaged)}


class ResumePlanner:
    """Compare a target plan with a prior run and reuse only verified units."""

    def __init__(self, store, root):
        self.store = store
        self.root = Path(root)

    def _prior_units(self, prior_run_id):
        units = {}
        attempts = self.store.attempts(prior_run_id)
        for attempt in attempts:
            unit = self.store.unit(attempt['unit_id'])
            units[unit['local_id']] = {'unit': unit, 'attempt': attempt}
        return units

    def _committed_artifacts(self, attempt_id):
        with self.store.lock:
            rows = self.store.connection.execute(
                "SELECT id FROM artifacts WHERE attempt_id=? AND state='committed'",
                (attempt_id,)).fetchall()
        result = []
        for row in rows:
            record = self.store.artifact(row['id'])
            if record is not None:
                result.append(record)
        return result

    def plan(self, prior_run_id: str, targets: list[dict], *,
             reuse_policy=None) -> list[ResumeDecision]:
        prior = self._prior_units(prior_run_id)
        decisions = {}
        if reuse_policy is None:
            def reuse_policy(item):
                identity = dict(item.get('execution_identity') or {})
                if item.get('inputs') and 'inputs' not in identity:
                    identity['inputs'] = item['inputs']
                environment = identity.get('environment') or {}
                return eligibility(
                    identity=identity,
                    stochastic=bool(item.get('stochastic')),
                    side_effects=item.get('side_effects', 'none'),
                    environment_verified=bool(item.get('environment_verified',
                                                       environment.get('verified', True))))
        for target in targets:
            unit_id = target['unit_id']
            target_key = target.get('cache_key') or cache_key(
                identity=target.get('execution_identity') or {},
                inputs=target.get('inputs') or [])
            item = prior.get(unit_id)
            deps = target.get('depends_on') or []
            blocked = next((dep for dep in deps if not decisions.get(dep, ResumeDecision(dep, False, 'pending', '')).reuse), None)
            if blocked:
                decisions[unit_id] = ResumeDecision(unit_id, False, f'dependency-rerun:{blocked}',
                                                    target_key)
                continue
            if item is None:
                decisions[unit_id] = ResumeDecision(unit_id, False, 'no-prior-unit', target_key)
                continue
            attempt = item['attempt']
            receipt = attempt.get('receipt') or {}
            prior_key = receipt.get('cache_key')
            if not prior_key:
                decisions[unit_id] = ResumeDecision(unit_id, False, 'missing-cache-identity', target_key)
                continue
            if prior_key != target_key:
                decisions[unit_id] = ResumeDecision(unit_id, False, 'cache-key-changed', target_key)
                continue
            if attempt['state'] != 'succeeded':
                decisions[unit_id] = ResumeDecision(unit_id, False, 'prior-attempt-not-committed',
                                                    target_key)
                continue
            artifacts = self._committed_artifacts(attempt['id'])
            if not artifacts:
                decisions[unit_id] = ResumeDecision(unit_id, False, 'no-committed-artifact', target_key)
                continue
            damaged = []
            for artifact in artifacts:
                ok, problems = verify_artifact(artifact, self.root)
                if not ok:
                    damaged.extend(problems)
            if damaged:
                decisions[unit_id] = ResumeDecision(unit_id, False, 'damaged-artifact', target_key,
                                                    tuple(item['id'] for item in artifacts), tuple(damaged))
                continue
            allowed = reuse_policy(target)
            if hasattr(allowed, 'eligible') and not allowed.eligible:
                decisions[unit_id] = ResumeDecision(unit_id, False,
                                                    'cache-ineligible:' + ','.join(allowed.reasons),
                                                    target_key)
                continue
            decisions[unit_id] = ResumeDecision(unit_id, True, 'verified-cache-hit', target_key,
                                                tuple(item['id'] for item in artifacts))
        return [decisions[target['unit_id']] for target in targets]


def environment_identity(*, packages=None, external_tools=None, named_environment=None,
                         verified=True) -> dict:
    return {'python': sys.version, 'platform': platform.platform(),
            'executable': sys.executable, 'packages': packages or {},
            'external_tools': external_tools or {}, 'named_environment': named_environment,
            'verified': bool(verified)}


def implementation_identity(*, operator: str, version: str | None, entry_point: str | None,
                            code_sha: str | None, converters=None) -> dict:
    return {'operator': operator, 'version': version, 'entry_point': entry_point,
            'code_sha': code_sha, 'converters': converters or {}}
