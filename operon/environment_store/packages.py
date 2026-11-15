"""Content-addressed environment layers; expanded payloads are managed caches.

Only sealing/migration walks and hashes the expanded files. Ordinary validation
checks the immutable archives. An explicit deep audit remains available through
EnvironmentStore.binding(..., verify='deep'). Same-account cache editing is not
a supported environment update; repair must rematerialize from these archives.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import tarfile
import uuid

from operon.bytecode import io_path
from operon.contracts.base import ContractError, sha256_hex
from operon.engine.fs import FileLock, atomic_json
from .verification import confined, file_digest, verify_inventory


def layer_for(name):
    parts = name.lower().split('/')
    if parts[0] == 'packages' or 'site-packages' in parts or 'dist-packages' in parts:
        return 'dependencies'
    return 'runtime' if parts[0] == 'runtime' else 'resources'


def blob_path(store, digest):
    import re
    if not isinstance(digest, str) or not re.fullmatch('[a-f0-9]{64}', digest):
        raise ContractError('Invalid environment package digest', code='environment_corrupt')
    return io_path(store.root / 'packages' / 'sha256' / (digest + '.tar'))


def descriptor(store, generation):
    directory, manifest, _ = store._manifest(generation)
    path = directory / 'packages.json'
    if not path.exists():
        return None
    value = json.loads(io_path(path).read_text(encoding='utf-8'))
    if (value.get('format') != 'operon.environment-packages/1'
            or value.get('generation_id') != generation
            or value.get('content_digest') != manifest['content_digest']):
        raise ContractError('Environment package binding differs', code='environment_corrupt')
    layers = value.get('layers', [])
    if not layers or len({x['kind'] for x in layers}) != len(layers):
        raise ContractError('Invalid package layers', code='environment_corrupt')
    for item in layers:
        blob_path(store, item['sha256'])
        expected = {k: v for k, v in manifest['files'].items() if layer_for(k) == item['kind']}
        if not expected or item['files_digest'] != sha256_hex(expected):
            raise ContractError('Package layer inventory differs', code='environment_corrupt')
    if {layer_for(k) for k in manifest['files']} != {x['kind'] for x in layers}:
        raise ContractError('Missing package layer', code='environment_corrupt')
    return value


def verify(store, generation, *, require_cache=True):
    value = descriptor(store, generation)
    if value is None:
        return False
    for layer in value['layers']:
        path = blob_path(store, layer['sha256'])
        if not path.is_file() or path.stat().st_size != layer['bytes'] or file_digest(path) != layer['sha256']:
            raise ContractError('Environment package is corrupt', code='environment_corrupt')
    directory, _, _ = store._manifest(generation)
    marker = directory / 'materialized.json'
    if require_cache and (not marker.exists() or json.loads(io_path(marker).read_text()).get('packages_digest') != sha256_hex(value)
            or not (directory / 'payload').is_dir()):
        raise ContractError('Environment cache requires materialization', code='environment_unavailable')
    return True


def seal(store, generation, *, cancel=None):
    """One-time legacy migration or initial publication; never trusts old bytes."""
    with FileLock(store.root / 'locks' / (generation + '.packages.lock'), timeout=1800):
        current = descriptor(store, generation)
        if current is not None:
            verify(store, generation, require_cache=False)
            return current
        directory, manifest, _ = store._manifest(generation)
        verify_inventory(directory / 'payload', manifest['files'])
        layers = []
        folder = store.root / 'packages' / 'sha256'; folder.mkdir(parents=True, exist_ok=True)
        for kind in sorted({layer_for(k) for k in manifest['files']}):
            records = {k: v for k, v in manifest['files'].items() if layer_for(k) == kind}
            temporary = io_path(folder / (uuid.uuid4().hex + '.tmp'))
            try:
                with tarfile.open(io_path(temporary), 'w', format=tarfile.PAX_FORMAT) as archive:
                    for name, record in sorted(records.items()):
                        if cancel and cancel():
                            raise InterruptedError('Environment packaging cancelled')
                        path = io_path(confined(directory / 'payload', name))
                        info = tarfile.TarInfo(name); info.mtime = info.uid = info.gid = 0
                        if record['kind'] == 'symlink':
                            if os.readlink(path) != record['target']:
                                raise ContractError('Changed environment link', code='environment_corrupt')
                            info.type = tarfile.SYMTYPE; info.linkname = record['target']; info.mode = 0o777
                            archive.addfile(info)
                        else:
                            info.size = record['size']; info.mode = 0o755 if record['executable'] else 0o644
                            # Validate the bytes actually put into the archive, not
                            # just the preceding scan (files may change meanwhile).
                            with path.open('rb') as stream:
                                digest = hashlib.sha256()
                                class Reader:
                                    def read(self, size):
                                        block = stream.read(size); digest.update(block); return block
                                archive.addfile(info, Reader())
                                if stream.read(1) or digest.hexdigest() != record['sha256']:
                                    raise ContractError('Changed environment file', code='environment_corrupt')
                digest = file_digest(temporary); target = blob_path(store, digest)
                if target.exists():
                    if file_digest(target) != digest:
                        raise ContractError('Existing package is corrupt', code='environment_corrupt')
                else:
                    os.replace(temporary, target)
                layers.append({'kind': kind, 'sha256': digest, 'bytes': target.stat().st_size,
                    'files_digest': sha256_hex(records)})
            finally:
                temporary.unlink(missing_ok=True)
        value = {'format': 'operon.environment-packages/1', 'generation_id': generation,
                 'content_digest': manifest['content_digest'], 'layers': layers}
        atomic_json(directory / 'materialized.json', {'packages_digest': sha256_hex(value)})
        atomic_json(directory / 'packages.json', value)
        return value


def copy_generation(source, destination, generation, *, cancel=None):
    """Copy a few immutable blobs, then materialize once; no expanded-tree copy."""
    from .builders import extract_locked
    value = seal(source, generation, cancel=cancel)
    original, manifest, _ = source._manifest(generation)
    with FileLock(destination.root / 'locks' / (generation + '.packages.lock'), timeout=1800):
        target = destination.root / 'generations' / generation
        if target.exists():
            if verify(destination, generation):
                return
            raise ContractError('Existing generation requires explicit repair', code='environment_corrupt')
        staged = destination.root / 'staging' / uuid.uuid4().hex
        staged.mkdir(parents=True)
        try:
            for layer in value['layers']:
                source_blob = blob_path(source, layer['sha256'])
                blob = blob_path(destination, layer['sha256']); blob.parent.mkdir(parents=True, exist_ok=True)
                if not blob.exists():
                    temp = blob.with_suffix('.' + uuid.uuid4().hex + '.tmp')
                    try:
                        digest = hashlib.sha256()
                        with source_blob.open('rb') as inp, temp.open('xb') as out:
                            while block := inp.read(1024 * 1024):
                                if cancel and cancel(): raise InterruptedError('Package copy cancelled')
                                out.write(block); digest.update(block)
                        if digest.hexdigest() != layer['sha256']:
                            raise ContractError('Package copy is corrupt', code='environment_corrupt')
                        os.replace(temp, blob)
                    finally:
                        temp.unlink(missing_ok=True)
                elif file_digest(blob) != layer['sha256']:
                    raise ContractError('Stored package is corrupt', code='environment_corrupt')
                maximum = sum(v.get('size', 0) for k, v in manifest['files'].items() if layer_for(k) == layer['kind'])
                extract_locked(blob, staged / 'payload', format='tar', maximum=maximum, cancel=cancel)
            for name in ('manifest.json', 'verification.json'):
                shutil.copyfile(io_path(original / name), io_path(staged / name))
            atomic_json(staged / 'packages.json', value)
            atomic_json(staged / 'materialized.json', {'packages_digest': sha256_hex(value)})
            os.replace(io_path(staged), io_path(target))
        finally:
            if staged.exists(): shutil.rmtree(io_path(staged))
