"""Check an installed canvas HTTP boundary without capturing an environment.

This deliberately stops at the environment phase. It is not a scientific run or
an independent-export acceptance substitute. Use a fresh synthetic workspace.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--code-root', type=Path, required=True)
    parser.add_argument('--workflow', type=Path, required=True)
    parser.add_argument('--workspace', type=Path, required=True)
    args = parser.parse_args()
    source = args.code_root.resolve(strict=True)
    root = args.workspace.resolve()
    root.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(source))
    os.environ['OPERON_REGISTRY_MAINTENANCE'] = '1'
    from fastapi.testclient import TestClient
    import operon
    from operon.headless import create_headless_app
    from operon.workflow_spec import load_workflow
    from src.web.service import Settings
    import operon.environment_store.canvas as environment
    assert Path(operon.__file__).resolve().is_relative_to(source)
    original = environment.prepare_python
    def stop(*unused, **options):
        raise InterruptedError('acceptance reached environment capture boundary')
    environment.prepare_python = stop
    try:
        server = create_headless_app(Settings(root, root / '.studio', root / 'no-ui',
                                              testing=True, code_root=source))
        with TestClient(server, base_url='http://127.0.0.1') as client:
            token = client.post('/api/agent/connect', headers={'X-Operon-Bridge': server.state.bridge.secret},
                json={'name': 'preflight-acceptance', 'scopes': ['context', 'run']}).json()['token']
            client.headers['Authorization'] = 'Bearer ' + token
            graph = load_workflow(args.workflow)
            response = client.post('/api/v1/canvas-plans/prepare',
                json={'graph': graph, 'request_id': 'script-preflight'})
            assert response.status_code == 200, response.text
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                result = client.get('/api/v1/canvas-plans/status',
                                    params={'request_id': 'script-preflight'}).json()
                if result['status'] != 'preparing':
                    break
                time.sleep(.05)
            assert result['status'] == 'cancelled', result
            assert result['error'] == 'acceptance reached environment capture boundary', result
            report = {'status': 'passed', 'scope': 'installed HTTP/preflight only',
                      'application': operon.__file__, 'scientific_execution': False, 'receipt': result}
            (root / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
            print(json.dumps(report))
    finally:
        environment.prepare_python = original


if __name__ == '__main__':
    main()
