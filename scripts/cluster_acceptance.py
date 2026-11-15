"""Grouped cluster evidence runner. Fixtures never substitute for real gates.

This script is prepared during development; run it only in the coordinated
acceptance batch. DSNs and other credentials are inherited, never recorded.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
GROUPS = {
    'module': {'evidence_kind': 'module_and_mock_fixtures', 'tests': [
        'tests/test_cluster_placement.py', 'tests/test_cluster_recovery.py',
        'tests/test_cluster_cli.py', 'tests/test_cluster_daemon.py', 'tests/test_cluster_invocation.py',
        'tests/test_cluster_host_receipts.py', 'tests/test_cluster_consumer.py',
        'tests/test_cluster_artifact_bindings.py', 'tests/test_cluster_prepared_bindings.py',
        'tests/test_cluster_terminal_recovery.py', 'tests/test_slurm_executor.py']},
    'local': {'evidence_kind': 'real_local_host_store_and_synthetic_worker', 'tests': ['tests/test_cluster_host.py']},
    'postgres': {'evidence_kind': 'real_postgresql17_with_explicit_fault_injection',
                 'tests': ['tests/test_cluster_repository.py'], 'requires_environment': 'OPERON_TEST_POSTGRES_DSN'},
}


def snapshot():
    try:
        head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=10).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        head = None
    paths = list((ROOT / 'operon/cluster').rglob('*.py')) + list((ROOT / 'operon/cluster/migrations').glob('*.sql'))
    paths += list((ROOT / 'tests').glob('test_cluster_*.py'))
    paths += list((ROOT / 'operon/contracts').glob('*.py')) + list((ROOT / 'operon/execution').rglob('*.py'))
    paths += [ROOT / path for path in ('tests/test_slurm_executor.py', 'pyproject.toml',
        'scripts/cluster_acceptance.py',
        'operon/engine/state.py', 'operon/engine/coordinator.py', 'operon/engine/control.py',
        'operon/pool_service.py', 'operon/managed_pool.py', 'operon/remote/server.py', 'operon/remote/handshake.py')]
    sources = {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
               for path in sorted(paths) if path.is_file()}
    versions = {}
    for name in ('pytest', 'psycopg', 'psycopg-pool'):
        try: versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError: versions[name] = None
    return {'revision': head, 'source_sha256': sources,
            'source_manifest_sha256': hashlib.sha256(json.dumps(sources, sort_keys=True).encode()).hexdigest(),
            'platform': platform.platform(), 'python': sys.version, 'executable': sys.executable,
            'dependency_versions': versions}


def counts(path):
    if not path.is_file():
        return None
    suites = list(ET.parse(path).getroot().iter('testsuite'))
    return {name: sum(int(suite.attrib.get(name, '0')) for suite in suites)
            for name in ('tests', 'failures', 'errors', 'skipped')}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'verification/backend' /
                        ('cluster-acceptance-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + str(os.getpid())))
    parser.add_argument('--groups', nargs='+', choices=tuple(GROUPS), default=list(GROUPS))
    parser.add_argument('--timeout-seconds', type=int, default=1200)
    parser.add_argument('--plan-only', action='store_true', help='Write NOT RUN evidence without invoking pytest')
    args = parser.parse_args(argv)
    if args.timeout_seconds <= 0:
        parser.error('Timeout must be positive')
    output = args.output.resolve()
    if (output / 'evidence.json').exists():
        parser.error('Evidence already exists; choose a new output directory to preserve prior results')
    output.mkdir(parents=True, exist_ok=True)
    report = {'format': 'operon.cluster-acceptance-evidence', 'schema_version': 1,
        'created_at': datetime.now(timezone.utc).isoformat(), 'source': snapshot(), 'groups': [],
        'gates': {'K08': 'not_accepted', 'K09': 'not_accepted', 'K10': 'not_accepted', 'K12': 'not_accepted'},
        'limitations': ['Module/mocked results are not real PostgreSQL, SSH or Slurm evidence.',
                       'Local host workers do not satisfy the two-compute-host K09 gate.',
                       'The PostgreSQL lost-reply fixture injects an error after a real commit; it is not a network-partition test.',
                       'Package acceptance and real target validation remain separate gates.']}
    for name in args.groups:
        definition = GROUPS[name]
        junit, log = output / (name + '.xml'), output / (name + '.log')
        command = [sys.executable, '-m', 'pytest', *definition['tests'], '-q', '--junitxml=' + str(junit)]
        record = {'name': name, 'evidence_kind': definition['evidence_kind'], 'command': command,
                  'cwd': str(ROOT), 'status': 'not_run', 'counts': None, 'log': str(log), 'junit': str(junit)}
        required = definition.get('requires_environment')
        if required and not os.environ.get(required):
            record['reason'] = required + ' is not configured; real database gate remains missing'
        elif args.plan_only:
            record['reason'] = 'Development handoff: coordinated test execution has not started'
        else:
            start = time.monotonic()
            with log.open('w', encoding='utf-8') as stream:
                try:
                    result = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                                            timeout=args.timeout_seconds, check=False)
                    record['returncode'] = result.returncode
                    record['counts'] = counts(junit)
                    record['status'] = 'passed' if result.returncode == 0 else 'failed'
                    if record['counts'] and record['counts']['skipped']:
                        record['status'] = 'passed_with_missing_capabilities' if result.returncode == 0 else 'failed'
                except subprocess.TimeoutExpired:
                    record['status'] = 'timed_out'
                except OSError as exc:
                    record['status'], record['reason'] = 'unavailable', type(exc).__name__
            record['elapsed_seconds'] = time.monotonic() - start
        report['groups'].append(record)
    report['groups'].extend([
        {'name': 'two_compute_hosts', 'evidence_kind': 'real_ssh_cluster', 'status': 'not_run',
         'reason': 'Two independently verified compute hosts and fault scenarios have not been supplied'},
        {'name': 'slurm_site', 'evidence_kind': 'real_slurm_scheduler', 'status': 'not_run',
         'reason': 'Actual scheduler/accounting access and a verified site profile have not been supplied'},
    ])
    report['source_after'] = snapshot()
    report['source_unchanged'] = (report['source']['source_manifest_sha256'] ==
                                  report['source_after']['source_manifest_sha256'])
    path = output / 'evidence.json'
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(str(path))
    return int(not report['source_unchanged'] or any(item['status'] in ('failed', 'timed_out', 'unavailable') for item in report['groups']))


if __name__ == '__main__':
    raise SystemExit(main())
