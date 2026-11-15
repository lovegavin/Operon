#!/usr/bin/env python3
"""Record the exact K00 baseline identity without changing execution state."""
from __future__ import annotations

from datetime import datetime, timezone
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ('operon-studio', 'pydantic', 'fastapi', 'uvicorn', 'paramiko', 'psycopg',
            'psycopg-pool', 'numpy', 'PyYAML', 'psutil', 'jsonschema', 'packaging',
            'pandas', 'scipy', 'matplotlib', 'pytest')
BOUNDARY = ('src.web', 'src.task.step.steps', 'matplotlib', 'torch', 'paramiko', 'fastapi')


def git(*args):
    result = subprocess.run(['git', *args], cwd=ROOT, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT / 'verification/backend/k00-runtime.json')
    args = parser.parse_args()
    dependencies = {}
    for name in PACKAGES:
        try:
            dependencies[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            dependencies[name] = None
    value = {
        'format': 'operon.backend-runtime-manifest',
        'schema_version': 1,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'application_version': '5.1.9',
        'baseline_commit': '600eed6f53b6db01f7391f408ade1e950d8679b3',
        'head': git('rev-parse', 'HEAD'),
        'branch': git('branch', '--show-current'),
        'dirty': bool(git('status', '--porcelain')),
        'source_sha256': {str(path.relative_to(ROOT)).replace('\\', '/'): hashlib.sha256(path.read_bytes()).hexdigest()
                          for folder in ('operon', 'operon_sdk', 'src', 'installer', 'tests', 'scripts')
                          for path in sorted((ROOT / folder).rglob('*'))
                          if path.is_file() and path.suffix in ('.py', '.cs', '.csproj') and
                          not {'__pycache__', 'bin', 'obj'}.intersection(path.parts)},
        'worktree': str(ROOT),
        'platform': {'system': platform.system(), 'machine': platform.machine(),
                     'python': sys.version.split()[0], 'executable': sys.executable},
        'dependencies': dependencies,
        'installed_distributions': sorted(
            ({'name': item.metadata.get('Name', ''), 'version': item.version}
             for item in importlib.metadata.distributions()),
            key=lambda item: (item['name'].lower(), item['version'])),
        'configuration_sha256': {
            path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted([ROOT / 'pyproject.toml', *ROOT.glob('requirements*.txt'),
                                *(ROOT / 'operon/contracts/schemas').glob('*.json')])
            if path.is_file()},
        'management_python_contract': 'CPython 3.11 runtime; source compatibility 3.11/3.12',
        'import_boundary': {
            'planning_contracts_must_not_import': list(BOUNDARY),
            'enforced_by': ['tests/test_run_plan_contract.py::test_planning_import_boundary_has_no_web_or_scientific_import',
                            'tests/test_run_plan_contract.py::test_actual_compilation_does_not_import_scientific_implementations'],
        },
    }
    output = args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + '\n',
                      encoding='utf-8')
    print(json.dumps({'output': str(output), 'head': value['head'], 'dirty': value['dirty']}))


if __name__ == '__main__':
    main()
