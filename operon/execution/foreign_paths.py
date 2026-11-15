"""Physical-path validation for Windows R's remaining CRT restrictions.

Junctions do not make arbitrary R installations long-path compatible: R can
normalize them back to the physical directory. Reject unsupported placements
before launch instead of silently copying data or retrying AccessDenied.
"""
from operon.bytecode import io_path
from operon.contracts.base import ContractError
from operon.environment_store.windows_paths import _logical_path


def r_path(value, *, role='file', reserve=0, allow_spaces=True):
    path = _logical_path(io_path(value).resolve())
    text = str(path)
    if len(text.encode('utf-16-le')) // 2 + reserve >= 260 or (not allow_spaces and any(c.isspace() for c in text)):
        raise ContractError(
            'Windows R requires a shorter physical path and a temporary directory without spaces. '
            'Select a short local work directory (--work-dir for an exported package) and a short '
            'environment-store location; junctions do not remove this R runtime restriction.',
            code='foreign_runtime_path_unsupported', details={'role': role})
    return path


def validate_r_generation(store, generation_id):
    """Binding was verified by the adapter; check all its declared file paths."""
    root, manifest, _ = store._manifest(generation_id)
    payload = root / 'payload'
    for relative in manifest['files']:
        r_path(payload / relative, role='environment')
    return r_path(payload, role='environment')
