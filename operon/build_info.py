"""Application build identity shared by the HTTP API, the CLI and the UI."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from . import __version__

_BUILD = re.compile(r'^(?P<version>\d+\.\d+\.\d+(?:[.\-+][0-9A-Za-z.\-+]+)?)[-+](?P<build>[0-9a-f]{6,40})$')
_SEPARATOR = '\u00b7'


def _parse_directory(name: str) -> tuple[str, str]:
    """Split ``<semver>-<hex>`` into ``(version, build)``; unknown names yield empties."""
    match = _BUILD.match(name)
    if not match:
        return '', ''
    return match.group('version'), match.group('build')


def _version_directory() -> str:
    """Return the ``<version>[-<build>]`` directory that holds this package."""
    resolved = Path(__file__).resolve()
    if len(resolved.parents) > 1:
        return resolved.parents[1].name
    return ''


def _installation_record() -> dict:
    for parent in Path(__file__).resolve().parents:
        record = parent / 'installation.json'
        if record.is_file():
            try:
                return json.loads(record.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                return {}
    return {}


def build() -> str:
    """Return this application's build suffix, for example ``0bbcaa570d84``."""
    explicit = os.environ.get('OPERON_BUILD', '').strip()
    if explicit:
        return explicit
    for candidate in (_version_directory(), str(_installation_record().get('current') or '')):
        _version, suffix = _parse_directory(Path(candidate).name)
        if suffix:
            return suffix
    return ''


def version() -> str:
    return __version__


def display() -> str:
    """Return the label the footer shows: ``5.4.1 (0bbcaa57)`` when a build is known."""
    suffix = build()
    if not suffix:
        return version()
    return f'{version()} ({suffix[:8]})'


def info() -> dict:
    return {'version': version(), 'build': build(), 'display': display()}
