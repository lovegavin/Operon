#!/usr/bin/env python3
"""Client-side evidence collection for a real multi-workspace pool.

This script is deliberately outside pytest: it connects to a running pool over
the loopback control channel, submits through the product client, records raw
status snapshots, and then cancels the work.  It does not mock workers or SSH.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from biopipe.pool_service import PoolClient


def read_graph(path):
    value = json.loads(Path(path).read_text(encoding='utf-8'))
    return value.get('graph', value)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--address', required=True)
    parser.add_argument('--token', required=True)
    parser.add_argument('--workspace-a', required=True)
    parser.add_argument('--workspace-b', required=True)
    parser.add_argument('--principal-a', required=True)
    parser.add_argument('--principal-b', required=True)
    parser.add_argument('--graph-a', required=True)
    parser.add_argument('--graph-b', required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    host, port = args.address.rsplit(':', 1)
    client = PoolClient((host, int(port)), args.token, timeout=30)
    evidence = {'started_at': time.time(), 'steps': [], 'ok': False}
    try:
        status = client.status()
        evidence['initial_status'] = status
        evidence['steps'].append({'step': 'connect', 'ok': True,
                                  'mode': status['pool'].get('mode')})
        graph_a, graph_b = read_graph(args.graph_a), read_graph(args.graph_b)
        first = client.submit(args.workspace_a, graph_a, request_id='accept-a',
                              principal=args.principal_a)
        duplicate = client.submit(args.workspace_a, graph_a, request_id='accept-a',
                                  principal=args.principal_a)
        if duplicate['id'] != first['id']:
            raise AssertionError('duplicate request launched a second run')
        second = client.submit(args.workspace_b, graph_b, request_id='accept-b',
                               principal=args.principal_b)
        evidence['runs'] = [first['id'], second['id']]
        evidence['steps'].append({'step': 'duplicate', 'ok': True, 'run_id': first['id']})
        # Close the client connection and reconnect: the submitted runs must
        # remain observable and must not be cancelled by disconnect.
        client = PoolClient((host, int(port)), args.token, timeout=30)
        snapshots = []
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            left = client.details(args.workspace_a, first['id'], principal=args.principal_a)
            right = client.details(args.workspace_b, second['id'], principal=args.principal_b)
            current = client.status()
            snapshots.append({'time': time.time(), 'a': left['status'], 'b': right['status'],
                              'leases': current.get('coordinator', {}).get('active_attempts')})
            if left['status'] in ('running', 'complete') and right['status'] in ('running', 'complete'):
                break
            time.sleep(.2)
        evidence['snapshots'] = snapshots[-20:]
        evidence['status_after_submit'] = client.status()
        if not any(item['a'] in ('running', 'complete') and item['b'] in ('running', 'complete')
                   for item in snapshots):
            raise AssertionError('both workspaces did not start')
        evidence['steps'].append({'step': 'disconnect_reconnect', 'ok': True})
        # Cancel only workspace A; workspace B must remain non-cancelled.
        cancelled = client.cancel(args.workspace_a, first['id'], principal=args.principal_a)
        evidence['cancelled_a'] = cancelled['status']
        evidence['steps'].append({'step': 'cancel_one', 'ok': True,
                                  'cancel_state': cancelled.get('cancel_state')})
        right = client.details(args.workspace_b, second['id'], principal=args.principal_b)
        evidence['workspace_b_after_cancel'] = right['status']
        if right['status'] == 'cancelled':
            raise AssertionError('cancelling one workspace cancelled the other')
        evidence['status_after_cancel'] = client.status()
        evidence['steps'].append({'step': 'independent_cancel', 'ok': True})
        client.cancel(args.workspace_b, second['id'], principal=args.principal_b)
        evidence['cleanup_b'] = 'cancel requested'
        evidence['ok'] = True
    except Exception as exc:  # noqa: BLE001 - evidence must capture failures
        evidence['error'] = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        evidence['finished_at'] = time.time()
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(evidence, indent=2, ensure_ascii=False), encoding='utf-8')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        sys.exit(1)
