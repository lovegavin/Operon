"""Explicit materialization boundaries; no semantic shape conversions or pickle.

Large buffers stay in files. Form uses the existing tagged exchange codec with
the caller's memory/disk admission hook. Foreign runtimes use declared files,
tables and JSON; they do not pretend to share managed Python heap memory.
"""
from __future__ import annotations

import json
from pathlib import Path

from operon.contracts.base import ContractError, canonical_json
from operon.engine.fs import atomic_json
from operon.environment_store.verification import confined, file_digest


def file_reference(path, *, representation='file', metadata=None):
    path = Path(path).resolve(strict=True)
    if not path.is_file():
        raise ContractError('Boundary expects a regular file', code='unsupported_boundary')
    return {'representation': representation, 'path': str(path), 'size_bytes': path.stat().st_size,
            'sha256': file_digest(path), 'metadata': metadata or {}}


def materialize(value, representation, directory, *, admit, buffer_bytes=65536, json_limit=1048576):
    """admit(bytes) accounts transport/scratch before creating owned payloads."""
    root = Path(directory).resolve()
    root.mkdir(parents=True, exist_ok=False)
    if representation == 'json':
        encoded = canonical_json(value).encode('utf-8')
        if len(encoded) > json_limit:
            raise ContractError('JSON boundary exceeds its declared allowance; use a file', code='unsupported_boundary')
        admit(len(encoded))
        path = root / 'value.json'
        path.write_bytes(encoded)
        return file_reference(path, representation='json')
    if representation == 'npy':
        import numpy as np
        if not isinstance(value, np.ndarray) or value.dtype.hasobject:
            raise ContractError('Numeric ndarray required; objects/sparse conversion is explicit', code='unsupported_boundary')
        admit(int(value.nbytes) + 4096)
        path = root / 'value.npy'
        with path.open('xb') as stream:
            # numpy's file writer streams non-contiguous arrays in bounded chunks.
            np.lib.format.write_array(stream, value, allow_pickle=False)
        return file_reference(path, representation='npy', metadata={
            'shape': list(value.shape), 'dtype': value.dtype.str})
    if representation == 'form':
        from operon.exchange import ExchangeWire
        from src.core import Form
        if not isinstance(value, Form):
            raise ContractError('This boundary requires a Form', code='unsupported_boundary')
        value.validate()
        wire = ExchangeWire(root, buffer_bytes=buffer_bytes, admit=admit)
        encoded = wire.encode(value)
        from src.core.contracts import describe_form
        packet = {'version': 1, 'value': encoded, 'contract': describe_form(value), 'audit': wire.audit}
        encoded = canonical_json(packet).encode('utf-8')
        if len(encoded) > json_limit:
            raise ContractError('Form metadata exceeds boundary allowance', code='unsupported_boundary')
        admit(len(encoded))
        path = root / 'value.bpform'
        path.write_bytes(encoded)
        from operon.environment_store.verification import inventory
        result = file_reference(path, representation='form')
        result['metadata'] = {'inventory': inventory(root)}
        return result
    raise ContractError('Use an explicit file/table adapter for this representation', code='unsupported_boundary')


def validate_reference(reference):
    path = Path(reference['path']).resolve(strict=True)
    if not path.is_file() or path.stat().st_size != reference['size_bytes'] or file_digest(path) != reference['sha256']:
        raise ContractError('Boundary payload changed after publication', code='artifact_mismatch')
    if reference.get('representation') == 'form':
        # A Form packet only names the arrays/attachments. Verifying its JSON
        # alone permits an unchanged packet to point at changed scientific data.
        from operon.environment_store.verification import verify_inventory
        expected = reference.get('metadata', {}).get('inventory')
        if not isinstance(expected, dict) or path.name not in expected:
            raise ContractError('Form boundary requires its published attachment inventory',
                                code='artifact_mismatch')
        try:
            verify_inventory(path.parent, expected)
        except (OSError, ValueError) as exc:
            raise ContractError('Form attachments changed after publication',
                                code='artifact_mismatch') from exc
    return path


def load(reference, *, mmap=True, json_limit=1048576):
    path = validate_reference(reference)
    kind = reference['representation']
    if kind == 'npy':
        import numpy as np
        result = np.load(path, mmap_mode='r' if mmap else None, allow_pickle=False)
        metadata = reference['metadata']
        if list(result.shape) != metadata['shape'] or result.dtype.str != metadata['dtype']:
            raise ContractError('Array header differs from boundary schema', code='artifact_mismatch')
        return result
    if kind == 'json':
        if path.stat().st_size > json_limit:
            raise ContractError('JSON payload too large', code='unsupported_boundary')
        return json.loads(path.read_text(encoding='utf-8'))
    if kind == 'form':
        from operon.exchange import ExchangeWire
        if path.stat().st_size > json_limit:
            raise ContractError('Form metadata too large', code='unsupported_boundary')
        packet = json.loads(path.read_text(encoding='utf-8'))
        if packet['version'] != 1:
            raise ContractError('Unsupported exchange packet', code='unsupported_boundary')
        wire = ExchangeWire(path.parent)
        wire.allowed_files = {confined(path.parent, name) for name in reference['metadata']['inventory']}
        result = wire.decode(packet['value'], mmap=mmap)
        result.validate()
        return result
    if kind in ('file', 'table', 'report', 'figure'):
        return path
    raise ContractError('Unknown boundary representation', code='unsupported_boundary')
