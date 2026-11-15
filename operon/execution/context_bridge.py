"""Context bridge preserving the existing scientific worker semantics.

The bridge intentionally delegates to ``src.task.Context`` and ``src.task.runner``;
there is no second DAG engine.  It makes the worker importable by the new
invocation ABI and keeps memory, spill, logs, artifact validation and process
ownership on the existing implementation.
"""
from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any

from operon.bytecode import io_path


class ContextBridge:
    def __init__(self, task_dir: Path, manifest: dict[str, Any], *, out_dir: Path,
                 memory_overrides: dict[str, Any] | None = None, run_log=None):
        from src.task.context import Context
        self.task_dir = Path(task_dir).resolve()
        self.manifest = manifest
        if memory_overrides:
            memory = manifest.setdefault('runtime', {}).setdefault('memory', {})
            memory.update(memory_overrides)
            memory['enabled'] = True
        self.context = Context(self.task_dir, manifest, out_dir=out_dir, run_log=run_log)

    def register_sources(self) -> None:
        for name, source in self.manifest.get('sources', {}).items():
            self.context.register_source(name, source)

    def run(self) -> None:
        from src.task.runner import run
        run(self.context, self.manifest.get('steps') or [])

    def finalize(self) -> None:
        self.context.finalize()

    @property
    def out_dir(self) -> Path:
        return self.context.out_dir

    def write_output_manifest(self, path: Path, *, status: str, error: str | None = None) -> dict:
        return write_output_manifest(self.out_dir, path, status=status, error=error)


def write_output_manifest(out_dir: Path, path: Path, *, status: str, error=None) -> dict:
    out_dir = Path(out_dir).resolve()
    summary_path = out_dir / 'run_summary.json'
    summary = None
    if io_path(summary_path).is_file():
        try:
            summary = json.loads(io_path(summary_path).read_text(encoding='utf-8'))
        except (OSError, ValueError):
            summary = None
    files = []
    hashes = {}
    for candidate in sorted(out_dir.rglob('*')):
        if candidate.is_file():
            if not candidate.resolve().is_relative_to(out_dir):
                raise ValueError('Output file resolves outside its owned directory')
            relative = candidate.relative_to(out_dir).as_posix()
            files.append(relative)
            digest = hashlib.sha256()
            with candidate.open('rb') as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(block)
            hashes[relative] = {'sha256': digest.hexdigest(), 'size': candidate.stat().st_size}
    value = {'format': 'operon.output-manifest', 'schema_version': 1,
             'status': status, 'output_dir': str(out_dir),
             'run_summary': str(summary_path) if summary is not None else None,
             'summary_status': (summary or {}).get('status'),
             'files': files, 'hashes': hashes, 'error': error}
    atomic = path.with_suffix(path.suffix + '.tmp')
    atomic.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    atomic.replace(path)
    return value
