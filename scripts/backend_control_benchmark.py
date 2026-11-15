"""Reproducible K00 comparison against a separately extracted source baseline.

Run this same script with --source pointing to either checkout. Synthetic slow
browse/transfer handlers model I/O stalls; SQLite, sockets, graph compilation,
environment subprocess probes and scientific workers execute real product code.
This is a Windows component/product baseline, not Linux/SSH cluster acceptance.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import hashlib
import json
import math
from pathlib import Path
import platform
import socket
import struct
import subprocess
import sys
import threading
import time
import tracemalloc
import uuid


def percentile(values):
    values = sorted(values)
    return {f'p{p}': values[max(0, math.ceil(len(values) * p / 100) - 1)] if values else None
            for p in (50, 95, 99)} | {'count': len(values)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--rounds', type=int, default=5)
    parser.add_argument('--cycles', type=int, default=6)
    parser.add_argument('--science-runs', type=int, default=3)
    parser.add_argument('--planning-handlers', type=int)
    parser.add_argument('--profile-submissions', action='store_true')
    args = parser.parse_args()
    source = args.source.resolve()
    sys.path.insert(0, str(source))
    import os
    os.environ['OPERON_REGISTRY_MAINTENANCE'] = '1'
    os.environ['OPERON_ENGINE_METRICS'] = '1'
    import psutil
    from operon.engine.control import ControlLoop, ControlLimits
    from operon.engine.state import StateStore
    from operon.engine.contracts import PoolSpec
    from src.web.graph import compile_graph
    from src.web.models import Graph
    from src.web.operator_catalog import catalog_from_descriptors
    from src.web.service import JobService, Settings
    root = (args.output.parent / '.scratch' / ('.benchmark-' + uuid.uuid4().hex)).resolve()
    root.mkdir(parents=True)
    os.environ['OPERON_ADMISSION_DIR'] = str(root / 'admission')
    os.environ['OPERON_ENGINE_DIR'] = str(root / 'engine')
    import numpy as np
    np.save(root / 'input.npy', np.random.default_rng(42).normal(size=(1000, 16)))
    started = time.perf_counter()
    service = JobService(Settings(root, root / 'science', root / 'ui', testing=True, code_root=source), catalog_from_descriptors())
    catalog = service.catalog
    startup_seconds = time.perf_counter() - started
    def graph(count):
        nodes = [{'id': 'input', 'kind': 'source', 'position': {'x': 0, 'y': 0},
                  'source': {'path': 'input.npy', 'dims': ['sample', 'feature'], 'reader': 'NpyReader'}}]
        edges = []
        for i in range(count):
            nodes.append({'id': f'n{i}', 'kind': 'operator', 'operator': 'describe',
                          'position': {'x': i, 'y': 0}, 'params': {}})
            edges.append({'id': f'e{i}', 'source': 'input', 'target': f'n{i}',
                          'sourceHandle': 'out', 'targetHandle': 'in-0'})
        return {'name': 'baseline', 'base_dir': str(root), 'nodes': nodes, 'edges': edges,
                'memory': {'budget_mb': 64, 'process_limit_mb': 512, 'enabled': True}}
    graphs = {name: graph(size) for name, size in (('small', 2), ('large', 200))}
    process = psutil.Process()
    report = {'schema_version': 1, 'source': str(source), 'python': sys.version,
              'harness_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'platform': platform.platform(), 'cpu': platform.processor(),
              'logical_cpus': psutil.cpu_count(), 'total_ram': psutil.virtual_memory().total,
              'workload': '16 TCP clients; real SQLite/compile/probe; synthetic slow I/O',
              'cycles': args.cycles, 'clients': 16,
              'graphs': {k: len(v['nodes']) for k, v in graphs.items()}, 'startup_seconds': startup_seconds, 'rounds': []}
    for index in range(args.rounds):
        store = StateStore(root / f'state-{index}.sqlite3')
        store.ensure_pool(PoolSpec(pool_id='bench', principal='bench', capacity_domain='bench',
                                  ceiling_bytes=1024**3, management_reserve_bytes=0, cpu_threads=4))
        store.register_workspace('ws', 'bench', str(root), 'bench')
        waits, holds, timings, errors = [], [], defaultdict(list), []
        submission_profiles, profile_context = [], threading.local()
        if args.profile_submissions:
            for method in ('_submission_storage_pressure', '_submission_snapshot', '_check_submission_capacity'):
                original_method = getattr(store, method, None)
                if original_method is None: continue
                def profiled(*a, _method=method, _original=original_method, **kw):
                    before = time.perf_counter()
                    try: return _original(*a, **kw)
                    finally:
                        current = getattr(profile_context, 'current', None)
                        if current is not None:
                            current[_method] = (time.perf_counter() - before) * 1000
                setattr(store, method, profiled)
        original = store.transaction
        @contextmanager
        def timed_transaction(*a, **kw):
            nested = bool(getattr(store.local, 'depth', 0))
            before = time.perf_counter()
            with original(*a, **kw) as connection:
                acquired = time.perf_counter()
                if not nested: waits.append((acquired - before) * 1000)
                try:
                    yield connection
                finally:
                    if not nested:
                        duration = (time.perf_counter() - acquired) * 1000
                        holds.append(duration)
                        current = getattr(profile_context, 'current', None)
                        if current is not None:
                            current['writer_wait_ms'] = (acquired - before) * 1000
                            current['writer_hold_ms'] = duration
        store.transaction = timed_transaction
        def submit(key, value):
            return store.claim_submission(principal='bench', key=key, digest=key, operation='run',
                run={'id': key, 'workspace_id': 'ws', 'project': 'bench', 'plan_key': key,
                     'plan_digest': key, 'plan': value},
                units=[{'unit_id': 'u', 'node_ids': ['n'], 'depends_on': [],
                        'target': {'kind': 'local'}, 'requirement': {'managed_budget_bytes': 1,
                        'process_reservation_bytes': 2, 'cpu_threads': 1}}])
        submit('seed', {})
        def dispatch(method, params):
            if method == 'status': return store.run('seed')
            if method == 'events': return store.events_after(0, limit=10)
            if method == 'submit':
                before = time.perf_counter()
                if args.profile_submissions: profile_context.current = {}
                try: submit(params['key'], params['graph'])
                finally:
                    if args.profile_submissions:
                        submission_profiles.append({**profile_context.current,
                            'total_ms': (time.perf_counter() - before) * 1000})
                        profile_context.current = None
                return {'queued': params['key']}
            if method == 'cancel':
                store.request_cancel(params['key'])
                return {'cancel_requested': True}
            if method == 'compile':
                manifest, order = compile_graph(Graph.model_validate(params['graph']), catalog, root)
                return {'steps': len(order), 'sources': len(manifest['sources'])}
            if method == 'browse':
                time.sleep(.15)
                return {'entries': [p.name for p in root.iterdir()]}
            if method == 'transfer':
                with (root / 'input.npy').open('rb') as stream:
                    data = stream.read(65536)
                    time.sleep(.02)
                return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
            if method == 'probe':
                completed = subprocess.run([sys.executable, '-c', 'import sys; print(sys.version_info[:2])'],
                    capture_output=True, timeout=10)
                if completed.returncode: raise RuntimeError(completed.stderr.decode(errors='replace'))
                return {'ready': True}
            raise ValueError(method)
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0)); listener.listen(64)
        loop = ControlLoop(dispatch, limits=(ControlLimits(max_planning_handlers=args.planning_handlers)
                           if args.planning_handlers is not None else ControlLimits()))
        server = threading.Thread(target=loop.serve, kwargs={'listener': listener, 'idle_seconds': 60}, daemon=True)
        server.start(); address = listener.getsockname()
        peak = {'rss': process.memory_info().rss, 'threads': 0, 'inflight_bytes': 0}
        stop = threading.Event()
        def monitor():
            while not stop.wait(.01):
                peak['rss'] = max(peak['rss'], process.memory_info().rss)
                peak['threads'] = max(peak['threads'], process.num_threads())
                peak['inflight_bytes'] = max(peak['inflight_bytes'], loop.stats()['inflight_bytes'])
        watcher = threading.Thread(target=monitor, daemon=True); watcher.start()
        def exact(connection, size):
            result = bytearray()
            while len(result) < size:
                data = connection.recv(size - len(result))
                if not data: raise ConnectionError('closed frame')
                result.extend(data)
            return result
        def client(client_id):
            methods = ('status', 'submit', 'events', 'compile', 'browse', 'status', 'transfer', 'cancel', 'probe')
            for cycle in range(args.cycles):
                for method in methods:
                    value = graphs['large' if (client_id + cycle) % 4 == 0 else 'small']
                    payload = json.dumps({'id': f'{client_id}-{cycle}-{method}', 'method': method,
                        'params': {'key': f'r-{client_id}-{cycle}', 'graph': value} if method in ('compile', 'submit')
                        else {'key': f'r-{client_id}-{cycle}'}}).encode()
                    started = time.perf_counter()
                    with socket.create_connection(address, timeout=30) as connection:
                        connection.sendall(struct.pack('!Q', len(payload)) + payload)
                        response = json.loads(exact(connection, struct.unpack('!Q', exact(connection, 8))[0]))
                    timings[method].append((time.perf_counter() - started) * 1000)
                    if not response['ok']: errors.append(response)
        started = time.perf_counter()
        try:
            with ThreadPoolExecutor(max_workers=16) as clients:
                list(clients.map(client, range(16)))
        finally:
            elapsed = time.perf_counter() - started
            loop.close(); listener.close(); server.join(3)
            stop.set(); watcher.join(2)
        with store.lock:
            counts = {row[0]: row[1] for row in store.connection.execute('SELECT status, count(*) FROM runs GROUP BY status')}
        report['rounds'].append({'phase': 'cold' if index == 0 else 'warm', 'seconds': elapsed,
            'latency_ms': {key: percentile(values) for key, values in timings.items()},
            'latency_samples_ms': dict(timings),
            'writer_wait_ms': percentile(waits), 'writer_hold_ms': percentile(holds),
            'peak': peak, 'queue': counts, 'errors': errors, 'control': loop.stats()})
        if args.profile_submissions: report['rounds'][-1]['submission_profiles'] = submission_profiles
        store.close()
    # Allocation estimate calibration is separate from timed dispatch.
    report['decoded_memory'] = []
    for name, value in graphs.items():
        raw = json.dumps(value).encode()
        estimate = len(raw)*7 + raw.count(b'{')*240 + raw.count(b'[')*72 + raw.count(b',')*64 + raw.count(b':')*160 + raw.count(b'"')*40
        tracemalloc.start(); parsed = json.loads(raw); _, peak = tracemalloc.get_traced_memory(); tracemalloc.stop()
        report['decoded_memory'].append({'graph': name, 'raw_bytes': len(raw), 'measured_peak': peak,
                                         'reserved_estimate': estimate, 'nodes': len(parsed['nodes'])})
    # Product path: identical real Reader -> PCA -> Describe workers in each tree.
    report['science'] = []
    try:
        science = graph(1)
        science['nodes'][1].update(operator='pca', params={'dim': 'feature', 'n_components': 2, 'output': 'pcs'})
        science['nodes'].append({'id': 'describe', 'kind': 'operator', 'operator': 'describe', 'params': {}, 'position': {'x': 2, 'y': 0}})
        science['edges'].append({'id': 'out', 'source': 'n0', 'target': 'describe', 'targetHandle': 'in-0', 'sourceHandle': 'out'})
        for index in range(args.science_runs):
            started = time.perf_counter(); job = service.launch(Graph.model_validate(science))
            while not service.require(job['id']).get('logs_complete'):
                if time.perf_counter() - started > 60: raise TimeoutError('Scientific worker')
                time.sleep(.02)
            result = service.require(job['id'])
            report['science'].append({'phase': 'cold' if index == 0 else 'warm', 'seconds': time.perf_counter()-started,
                                      'status': result['status'], 'error': result.get('error')})
    finally:
        service.shutdown()
    args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'output': str(args.output), 'errors': sum(len(r['errors']) for r in report['rounds']),
                      'science': report['science']}))


if __name__ == '__main__':
    main()
