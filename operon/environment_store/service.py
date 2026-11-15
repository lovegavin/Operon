"""Crash-recoverable publish, binding and non-expiring generation leases.

The durable JSON journal deliberately lives outside the engine database. All
publication/ref/lease mutations share the store lock. Hashing, building and probes
hold only a per-requirement lock. This cannot create a second resource allocator.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import uuid

from operon.contracts.base import ContractError, sha256_hex
from operon.contracts.run_plan import EnvironmentRequirement, EnvironmentBinding
from operon.engine.fs import FileLock, atomic_json
from .verification import inventory, verify_inventory, file_digest
from operon.bytecode import io_path


def safe_name(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,159}', value):
        raise ContractError('Invalid environment identifier', code='invalid_environment')
    return value


def read(path):
    return json.loads(io_path(path).read_text(encoding='utf-8'))


class EnvironmentStore:
    def __init__(self, root, *, create=True):
        self.root = Path(root).resolve()
        if create:
            for folder in ('blobs/sha256', 'staging', 'generations', 'references', 'journal', 'leases', 'locks', 'trash'):
                (self.root / folder).mkdir(parents=True, exist_ok=True)
        self.lock = FileLock(self.root / 'locks' / 'store.lock')

    def ingest(self, path, digest):
        if not re.fullmatch(r'[a-f0-9]{64}', digest):
            raise ContractError('An exact artifact SHA256 is required', code='unlocked_artifact')
        target = self.root / 'blobs' / 'sha256' / digest
        with FileLock(self.root / 'locks' / (digest + '.blob.lock')):
            if target.exists():
                if file_digest(target) != digest:
                    raise ContractError('Stored artifact is corrupt', code='environment_corrupt')
                return target
            temporary = target.with_name(digest + '.' + uuid.uuid4().hex + '.tmp')
            try:
                shutil.copyfile(path, temporary)
                if file_digest(temporary) != digest:
                    raise ContractError('Downloaded artifact hash differs from lock', code='artifact_mismatch')
                with temporary.open('r+b') as stream:
                    os.fsync(stream.fileno())
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
        return target

    def _manifest(self, generation):
        path = self.root / 'generations' / safe_name(generation)
        try:
            manifest = read(path / 'manifest.json')
            receipt = read(path / 'verification.json')
            requirement = EnvironmentRequirement.model_validate(manifest['requirement'])
            identity = manifest['identity']
            requirement_digest = sha256_hex(requirement)
            if ((manifest.get('format'), manifest.get('schema_version')) != ('operon.environment-generation', 1)
                    or type(manifest.get('schema_version')) is not int
                    or manifest.get('generation_id') != generation
                    or receipt.get('status') != 'passed' or receipt.get('relocation') != 'passed'
                    or receipt.get('content_digest') != manifest.get('content_digest')
                    or sha256_hex(manifest['files']) != manifest['content_digest']
                    or identity.get('content_digest') != manifest['content_digest']
                    or manifest.get('requirement_digest') != requirement_digest
                    or identity.get('requirement_digest') != requirement_digest
                    or identity.get('target') != requirement.target.model_dump(mode='json')
                    or sha256_hex(identity) != generation):
                raise ValueError('Generation identity, requirement and verification receipt differ')
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            raise ContractError('Incomplete or inconsistent generation manifest',
                                code='environment_corrupt', details={'generation_id': generation}) from exc
        return path, manifest, receipt

    def binding(self, generation, *, verify=True):
        path, manifest, receipt = self._manifest(generation)
        if verify:
            from .packages import verify as verify_packages
            if verify == 'deep' or not verify_packages(self, generation):
                verify_inventory(path / 'payload', manifest['files'])
        return EnvironmentBinding(requirement_digest=manifest['requirement_digest'],
            target=manifest['requirement']['target'], generation_id=generation,
            content_digest=manifest['content_digest'], verification_receipt=receipt)

    def resolve(self, requirement):
        requirement = EnvironmentRequirement.model_validate(requirement)
        key = sha256_hex(requirement)
        with self.lock:
            pointer = self.root / 'references' / (key + '.json')
            generation = read(pointer)['generation_id'] if pointer.exists() else None
        return self.binding(generation) if generation else None

    def prepare(self, requirement, builder, *, cancel=None, checkpoint=None):
        """Builder must materialize and verify a target-specific locked closure.

        checkpoint is an explicit crash-injection hook, never a success shortcut.
        A BaseException simulates process death; recover() reconciles publication.
        """
        requirement = EnvironmentRequirement.model_validate(requirement)
        key = sha256_hex(requirement)
        checkpoint = checkpoint or (lambda phase: None)
        with FileLock(self.root / 'locks' / (key + '.prepare.lock'), timeout=1800):
            existing = self.resolve(requirement)
            if existing:
                return existing
            preparation = uuid.uuid4().hex
            staging = self.root / 'staging' / preparation
            staging.mkdir()
            journal = self.root / 'journal' / (preparation + '.json')
            record = {'preparation_id': preparation, 'requirement_digest': key,
                      'state': 'requested', 'generation_id': None}

            def phase(state):
                record['state'] = state
                atomic_json(journal, record)
                checkpoint(state)
                if cancel and cancel():
                    raise InterruptedError('Environment preparation cancelled')

            try:
                phase('requested')
                phase('resolving')
                builder.resolve(requirement)
                phase('building')
                payload = staging / 'payload'
                payload.mkdir()
                provenance = builder.build(payload, self, cancel=cancel)
                phase('verifying')
                verification = builder.verify(payload, cancel=cancel)
                if verification.get('status') != 'passed' or verification.get('relocation') != 'passed':
                    raise ContractError('Target import/tool and relocation probes are required', code='environment_unverified')
                files = inventory(payload)
                content = sha256_hex(files)
                identity = {'requirement_digest': key, 'content_digest': content,
                            'builder': provenance, 'target': requirement.target.model_dump(mode='json')}
                generation = sha256_hex(identity)
                record['generation_id'] = generation
                manifest = {'format': 'operon.environment-generation', 'schema_version': 1,
                            'generation_id': generation, 'identity': identity, 'files': files,
                            'requirement_digest': key, 'requirement': requirement.model_dump(mode='json'),
                            'content_digest': content}
                verification = {**verification, 'content_digest': content}
                atomic_json(staging / 'manifest.json', manifest)
                atomic_json(staging / 'verification.json', verification)
                phase('verified')
                with self.lock:
                    destination = self.root / 'generations' / generation
                    if destination.exists():
                        self.binding(generation)
                    else:
                        os.replace(staging, destination)
                    checkpoint('published')
                    atomic_json(self.root / 'references' / (key + '.json'), {'generation_id': generation})
                    record['state'] = 'ready'
                    atomic_json(journal, record)
                checkpoint('ready')
                from .packages import seal
                seal(self, generation, cancel=cancel)
                return self.binding(generation)
            except Exception as exc:
                # A publish with a lost acknowledgment is reconciled, not deleted.
                record.update(state='cancelled' if isinstance(exc, InterruptedError) else 'failed',
                              error=f'{type(exc).__name__}: {exc}')
                atomic_json(journal, record)
                raise

    def recover(self):
        outcomes = []
        for journal in sorted((self.root / 'journal').glob('*.json')):
            item = read(journal)
            if item['state'] == 'ready':
                continue
            generation = item.get('generation_id')
            with FileLock(self.root / 'locks' / (item['requirement_digest'] + '.prepare.lock')):
                if not generation or not (self.root / 'generations' / generation).exists():
                    # Staging never becomes ready just because its creator died.
                    outcomes.append({'preparation_id': item['preparation_id'], 'state': item['state']})
                    continue
                self.binding(generation)
                with self.lock:
                    atomic_json(self.root / 'references' / (item['requirement_digest'] + '.json'),
                                {'generation_id': generation})
                    item.update(state='ready', recovered=True)
                    atomic_json(journal, item)
                outcomes.append(item)
        return outcomes

    def acquire(self, generation, *, attempt_id, fence):
        safe_name(attempt_id)
        if type(fence) is not int or fence < 1:
            raise ContractError('Lease requires a positive attempt fence', code='stale_attempt')
        with self.lock:
            binding = self.binding(generation)
            path = self.root / 'leases' / (attempt_id + '.json')
            if path.exists():
                lease = read(path)
                if lease['generation_id'] != generation or lease['fence'] != fence or lease['state'] == 'released':
                    raise ContractError('Attempt already has a different or terminal lease', code='stale_attempt')
                return lease
            lease = {'attempt_id': attempt_id, 'fence': fence, 'generation_id': generation,
                     'state': 'acquired', 'binding': binding.model_dump(mode='json')}
            atomic_json(path, lease)
            return lease

    def spawning(self, attempt_id, fence, supervisor_directory):
        """Persist before calling spawn; an interrupted launch remains pinned."""
        with self.lock:
            path = self.root / 'leases' / (safe_name(attempt_id) + '.json')
            lease = read(path)
            if lease['fence'] != fence or lease['state'] != 'acquired':
                raise ContractError('Lease cannot enter spawning', code='stale_attempt')
            lease.update(state='spawning', supervisor_directory=str(Path(supervisor_directory).resolve()))
            atomic_json(path, lease)

    def release_unstarted(self, attempt_id, fence):
        with self.lock:
            path = self.root / 'leases' / (safe_name(attempt_id) + '.json')
            lease = read(path)
            if lease['fence'] != fence or lease['state'] != 'acquired':
                raise ContractError('Launch may have started; tree proof is required', code='recovery_required')
            lease['state'] = 'released'
            atomic_json(path, lease)

    def release(self, attempt_id, fence):
        """Consume a supervisor-authored containment proof, never a caller bool."""
        with self.lock:
            path = self.root / 'leases' / (safe_name(attempt_id) + '.json')
            lease = read(path)
            if lease['fence'] != fence or lease['state'] not in ('spawning', 'released'):
                raise ContractError('Lease is not bound to a supervised attempt', code='stale_attempt')
            proof = read(Path(lease['supervisor_directory']) / (attempt_id + '.tree-exit.json'))
            if (proof.get('attempt_id') != attempt_id or proof.get('fence') != fence
                    or proof.get('tree_exited') is not True
                    or proof.get('method') not in ('windows-job', 'linux-subreaper', 'never-spawned')):
                raise ContractError('Process tree exit is not proven', code='recovery_required')
            lease.update(state='released', proof=proof)
            atomic_json(path, lease)

    def collect(self, generation):
        """Remove only explicitly unreferenced generations, never age-based GC."""
        with self.lock:
            path, _, _ = self._manifest(generation)
            for reference in (self.root / 'references').glob('*.json'):
                if read(reference).get('generation_id') == generation:
                    return False
            for lease in (self.root / 'leases').glob('*.json'):
                item = read(lease)
                if item['generation_id'] == generation and item['state'] != 'released':
                    return False
            from .windows_paths import remove_launch_alias
            remove_launch_alias(self.root, generation)
            trash = self.root / 'trash' / (generation + '-' + uuid.uuid4().hex)
            os.replace(path, trash)
        if trash.resolve().parent != (self.root / 'trash').resolve():
            raise ContractError('GC target escaped its store', code='path_escape')
        shutil.rmtree(io_path(trash))
        return True
