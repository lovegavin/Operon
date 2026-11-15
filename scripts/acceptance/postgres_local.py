"""Run real PostgreSQL 17 tests in an owned, loopback-only disposable instance.

No Windows service, global configuration, existing database or user account is
changed. The caller supplies trusted PostgreSQL binaries and test dependencies.
"""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import uuid


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bin', type=Path, required=True)
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--driver', type=Path, required=True)
    a = p.parse_args()
    root = a.work.resolve(); root.mkdir(parents=True, exist_ok=False)
    binary = a.bin.resolve()
    source = Path(__file__).resolve().parents[2]
    data, log = root/'data', root/'postgres.log'
    pw = root/'bootstrap-password'
    pw.write_text(uuid.uuid4().hex, encoding='ascii')
    password = pw.read_text()
    env = dict(os.environ)
    env.update(PYTHONPATH=str(a.driver.resolve())+os.pathsep+str(source),
               PYTHONDONTWRITEBYTECODE='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    report = {'platform': sys.platform, 'database': 'PostgreSQL 17 actual process',
              'scope': 'loopback owned data directory', 'stopped': False}
    started = False
    command_number = 0
    def command(arguments, *, timeout=60):
        nonlocal command_number
        command_number += 1
        capture = root / f'command-{command_number}.log'
        # A real file prevents helper grandchildren retaining a captured pipe
        # from masking the parent exit. Preserve diagnostics even on timeout.
        with capture.open('wb') as output:
            result = subprocess.run(list(map(str, arguments)), env=env,
                stdout=output, stderr=subprocess.STDOUT, timeout=timeout, creationflags=flags)
        content = capture.read_text(encoding='utf-8', errors='replace')
        if result.returncode:
            raise RuntimeError(content)
        return content
    try:
        report['version'] = command([binary/'postgres', '--version']).strip()
        if ' 17.' not in report['version']:
            raise ValueError('PostgreSQL 17 is required')
        command([binary/'initdb', '-D', data, '-U', 'operon_acceptance',
                 '--auth=scram-sha-256', '--pwfile', pw, '--encoding=UTF8', '--locale=C'], timeout=180)
        pw.unlink()
        with socket.socket() as endpoint:
            endpoint.bind(('127.0.0.1', 0)); port=endpoint.getsockname()[1]
        command([binary/'pg_ctl', '-D', data, '-l', log, '-o', f'-h 127.0.0.1 -p {port}', '-w', 'start'])
        started = True
        env['OPERON_TEST_POSTGRES_DSN'] = f'host=127.0.0.1 port={port} dbname=postgres user=operon_acceptance password={password}'
        with (root/'pytest.log').open('wb') as output:
            result = subprocess.run([sys.executable, '-B', '-X', 'utf8', '-m', 'pytest',
                'tests/test_cluster_repository.py', '-q', '--basetemp', str(root/'pytest'),
                '--junitxml', str(root/'pytest.xml')], cwd=source, env=env,
                stdout=output, stderr=subprocess.STDOUT, timeout=240, creationflags=flags)
        report['pytest_exit'] = result.returncode
        return result.returncode
    finally:
        try:
            if started:
                command([binary/'pg_ctl', '-D', data, '-m', 'fast', '-w', 'stop'])
                report['stopped'] = True
            else:
                report['server_started'] = False
        finally:
            pw.unlink(missing_ok=True)
            (root/'evidence.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
            print(json.dumps(report, indent=2))


if __name__ == '__main__':
    raise SystemExit(main())
