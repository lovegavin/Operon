"""Offline destination binding for runtimes requiring prefix fixups."""
from pathlib import Path
import shutil

from operon.bytecode import io_path
from operon.contracts.base import ContractError
from operon.environment_store.builders import LockedArchive, LockedArchiveBuilder
from operon.environment_store.verification import confined, file_digest


def collect_packed_inputs(store, payload_store, generation):
    _, manifest, _ = store._manifest(generation)
    recipe = manifest['identity']['builder']
    if not recipe.get('fixups'):
        return False
    if recipe.get('builder') != 'locked-archives-v1':
        raise ContractError('No packed relocation adapter for this environment builder',
                            code='environment_preparation_required')
    for item in recipe['artifacts']:
        digest = item['sha256']
        source = store.root / 'blobs/sha256' / digest
        if not source.is_file() or file_digest(source) != digest:
            raise ContractError('Original packed environment is required for offline relocation',
                                code='export_missing_resource')
        target = Path(payload_store) / 'blobs/sha256' / digest
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copyfile(io_path(source), io_path(target))
    return True


def destination_binding(source, target, generation, *, cancel=None):
    _, manifest, _ = source._manifest(generation)
    recipe = manifest['identity']['builder']
    if not recipe.get('fixups'):
        return None
    if recipe.get('builder') != 'locked-archives-v1':
        raise ContractError('Unsupported relocation recipe', code='environment_preparation_required')
    archives = [LockedArchive(source.root/'blobs/sha256'/item['sha256'], item['sha256'],
        item['destination'], item['max_unpacked_bytes'], item['format']) for item in recipe['artifacts']]
    builder = LockedArchiveBuilder(archives, recipe['probes'], fixups=recipe['fixups'],
                                   timeout=recipe['timeout'], environment=recipe['environment'])
    return target.prepare(manifest['requirement'], builder, cancel=cancel)
