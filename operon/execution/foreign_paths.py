"""Physical-path validation for Windows R's remaining CRT restrictions.

Junctions do not make arbitrary R installations long-path compatible: R can
normalize them back to the physical directory. Reject unsupported placements
before launch instead of silently copying data or retrying AccessDenied.
"""
from operon.bytecode import io_path
from operon.contracts.base import ContractError
from operon.environment_store.windows_paths import _logical_path


def r_scratch(attempt_root):
    """Keep an attempt-owned R scratch directory when its workspace has spaces.

    Only temporary files use the OS temp area; inputs, outputs and spill remain
    in their original managed partitions. The receipt survives launcher recovery.
    """
    import json
    import tempfile
    from pathlib import Path
    from operon.engine.fs import atomic_json
    root = io_path(attempt_root)
    try:
        path = r_path(root / 'scratch', role='temporary', reserve=32, allow_spaces=False)
        path.mkdir(parents=True, exist_ok=True)
        return path
    except ContractError:
        pass
    receipt = root / 'r-scratch.json'
    identity = str(root.resolve())
    if receipt.is_file():
        value = json.loads(receipt.read_text())
        path = Path(value['path'])
        if (path / '.operon-owner.json').is_file() and json.loads((path / '.operon-owner.json').read_text()) == {'attempt': identity}:
            return r_path(path, role='temporary', reserve=32, allow_spaces=False)
        raise ContractError('R scratch ownership differs', code='recovery_required')
    base = r_path(tempfile.gettempdir(), role='temporary', reserve=70, allow_spaces=False)
    path = Path(tempfile.mkdtemp(prefix='operon-r-', dir=base))
    atomic_json(path / '.operon-owner.json', {'attempt': identity})
    atomic_json(receipt, {'path': str(path), 'attempt': identity})
    return path


def release_r_scratch(attempt_root):
    """Called only after the supervisor confirms all descendants have stopped."""
    import json
    import shutil
    from pathlib import Path
    root = io_path(attempt_root)
    receipt = root / 'r-scratch.json'
    if not receipt.is_file():
        return
    value = json.loads(receipt.read_text())
    path = Path(value['path'])
    marker = path / '.operon-owner.json'
    # Refuse links and altered ownership before recursive removal.
    if path.is_symlink() or path.resolve() != path.absolute() or not path.name.startswith('operon-r-'):
        return
    if value.get('attempt') != str(root.resolve()) or not marker.is_file():
        return
    if json.loads(marker.read_text()) != {'attempt': str(root.resolve())}:
        return
    shutil.rmtree(path)
    receipt.unlink()


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
