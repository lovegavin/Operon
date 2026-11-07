"""The dedicated pool has a real CLI service entry and control client."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import pytest

from biopipe.pool_service import PoolClient

ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def test_pool_serve_cli_and_status_client(tmp_path):
    workspace = tmp_path / 'workspace'; workspace.mkdir()
    (workspace / 'input.csv').write_text('a,b\n1,2\n', encoding='utf-8')
    code = tmp_path / 'code'; (code / 'scripts').mkdir(parents=True)
    (code / 'scripts/run.py').write_text('import json,sys\nfrom pathlib import Path\nt=Path(sys.argv[1]); (t/"output").mkdir(); (t/"output/run_summary.json").write_text(json.dumps({"status":"complete"}))\n')
    config = {
        'root': str(tmp_path / 'pool-state'),
        'admission_dir': str(tmp_path / 'admission'),
        'workspaces': [{'root': str(workspace), 'principal': 'cli-user'}],
        'code_root': str(code),
        'capacity_bytes': 256 * 1024 ** 2,
        'cpu_threads': 2,
        'token': 'cli-pool-token',
    }
    config_path = tmp_path / 'pool.json'
    config_path.write_text(json.dumps(config), encoding='utf-8')
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONIOENCODING='utf-8',
               PYTHONUNBUFFERED='1')
    log = tmp_path / 'pool.log'
    with log.open('wb') as output:
        process = subprocess.Popen(
            [sys.executable, '-m', 'biopipe', 'pool', 'serve', '--config', str(config_path),
             '--port', '0'],
            cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
            stdout=output, stderr=subprocess.STDOUT)
    try:
        import re
        deadline = time.monotonic() + 30
        port = None
        while time.monotonic() < deadline and port is None:
            if process.poll() is not None:
                break
            text = log.read_text(encoding='utf-8', errors='replace')
            match = re.search(r'"address":\s*\[\s*"127\.0\.0\.1",\s*(\d+)', text)
            if match:
                port = int(match.group(1))
            else:
                time.sleep(.1)
        if port is None:
            pytest.fail('pool CLI did not start: ' + log.read_text(encoding='utf-8', errors='replace')[-4000:])
        client = PoolClient(('127.0.0.1', port), 'cli-pool-token', timeout=5)
        status = client.status()
        assert status['workspaces'][0]['root'] == str(workspace)
        assert status['pool']['mode'] == 'coordinator'
        cli = subprocess.run(
            [sys.executable, '-m', 'biopipe', 'pool', 'status',
             '--address', f'127.0.0.1:{port}', '--token', 'cli-pool-token'],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
        assert cli.returncode == 0, cli.stderr
        assert json.loads(cli.stdout)['pool']['mode'] == 'coordinator'
    finally:
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill(); process.wait(timeout=5)
