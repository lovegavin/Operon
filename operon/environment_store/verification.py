"""Streaming inventories and confined paths used by builders and collectors."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

from operon.contracts.base import ContractError, sha256_hex
from operon.contracts.run_plan import validate_relative_path
from operon.bytecode import io_path


def confined(root, relative):
    validate_relative_path(relative)
    root = Path(root).resolve()
    path = root / relative
    if not path.resolve().is_relative_to(root):
        raise ContractError('Path escapes its owned root', code='path_escape')
    return path


def file_digest(path):
    digest = hashlib.sha256()
    with io_path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def inventory(root):
    """No dereferencing of external links, no in-memory file contents."""
    root = Path(root).resolve()
    scan_root = io_path(root)
    result = {}
    for directory, dirs, files in os.walk(scan_root, followlinks=False):
        for name in sorted(dirs + files):
            path = Path(directory) / name
            relative = path.relative_to(scan_root).as_posix()
            confined(root, relative)
            if path.is_symlink():
                target = os.readlink(path)
                if Path(target).is_absolute():
                    raise ContractError('Absolute symlinks are not relocatable', code='invalid_environment')
                result[relative] = {'kind': 'symlink', 'target': target}
            elif path.is_file():
                stat = path.stat()
                result[relative] = {'kind': 'file', 'size': stat.st_size,
                                    'sha256': file_digest(path), 'executable': bool(stat.st_mode & 0o111)}
            elif not path.is_dir():
                raise ContractError('Special files cannot be packaged', code='invalid_environment')
    return result


def verify_inventory(root, expected):
    actual = inventory(root)
    if actual != expected:
        changed = sorted(set(actual) ^ set(expected) | {
            key for key in actual.keys() & expected.keys() if actual[key] != expected[key]})
        raise ContractError('Environment contents changed: ' + ', '.join(changed[:12]),
                            code='environment_corrupt')
    return sha256_hex(actual)
