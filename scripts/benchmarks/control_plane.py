"""Reproducible control-plane benchmark for the legacy and concurrent loops.

This measures the server-side loop, not network RTT or UI rendering.  Both
modes use the same framed request/response fixture and the same dispatch
function, so the difference is the accept/concurrency policy rather than the
pay of the scientific work.

Usage (from the repository root):

    python scripts/benchmarks/control_plane.py --mode both --clients 16 \
        --requests 20 --slow-seconds 0.4 --output .verify-tmp/control.json

The report records the machine and workload so a number is never detached from
its conditions.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
import platform
import socket
import statistics
import struct
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from biopipe.engine.control import ControlLimits, ControlLoop  # noqa: E402


def recv_exact(connection, size):
    data = bytearray()
    while len(data) < size:
        block = connection.recv(size - len(data))
        if not block:
            raise ConnectionError('closed')
        data.extend(block)
    return bytes(data)


def send_frame(connection, value):
    data = json.dumps(value).encode('utf-8')
    connection.sendall(struct.pack('!Q', len(data)) + data)


def read_frame(connection):
    size = struct.unpack('!Q', recv_exact(connection, 8))[0]
    return json.loads(recv_exact(connection, size))


def dispatch_factory(slow_seconds, entered=None):
    def dispatch(method, params):
        if method == 'slow':
            if entered is not None:
                entered.set()
            time.sleep(slow_seconds)
            return {'slow': True}
        if method == 'status':
            return {'status': 'running', 'queue': 0}
        return {'value': method}
    return dispatch


def serve_concurrent(listener, dispatch, *, handlers):
    loop = ControlLoop(dispatch, limits=ControlLimits(max_handlers=handlers))
    thread = threading.Thread(target=loop.serve,
                              kwargs={'listener': listener, 'alive': lambda: False,
                                      'idle_seconds': 120}, daemon=True)
    thread.start()
    return loop, thread


def serve_serial(listener, dispatch):
    """Faithful reproduction of the pre-change accept -> read -> dispatch -> reply loop."""
    stop = threading.Event()

    def run():
        listener.settimeout(0.5)
        while not stop.is_set():
            try:
                connection, _ = listener.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            with connection:
                connection.settimeout(30)
                try:
                    request = read_frame(connection)
                    value = dispatch(request['method'], request.get('params', {}))
                    response = {'ok': True, 'value': value}
                except Exception as exc:  # noqa: BLE001
                    response = {'ok': False, 'error': str(exc), 'code': getattr(exc, 'code', 'error')}
                try:
                    send_frame(connection, response)
                except OSError:
                    pass

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return stop, thread


def listen():
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(('127.0.0.1', 0))
    listener.listen(128)
    return listener, listener.getsockname()


def one_request(address, method):
    started = time.perf_counter()
    client = socket.create_connection(address, timeout=30)
    send_frame(client, {'id': method, 'method': method, 'params': {}})
    response = read_frame(client)
    client.close()
    return (time.perf_counter() - started) * 1000, response


def percentile(samples, value):
    if not samples:
        return None
    ordered = sorted(samples)
    index = max(0, min(len(ordered) - 1, int(__import__('math').ceil(value / 100 * len(ordered)) - 1)))
    return ordered[index]


def workload(address, *, clients, requests, barrier, start_after):
    start_after.wait(10)
    barrier.wait(10)
    samples = []
    errors = []

    def client(_):
        local = []
        for _ in range(requests):
            try:
                latency, response = one_request(address, 'status')
                if not response.get('ok'):
                    errors.append(response)
                    continue
                local.append(latency)
            except Exception as exc:  # noqa: BLE001
                errors.append(repr(exc))
        return local

    with ThreadPoolExecutor(max_workers=clients) as pool:
        for values in pool.map(client, range(clients)):
            samples.extend(values)
    return samples, errors


def run_mode(mode, *, clients, requests, slow_seconds, handlers):
    entered = threading.Event()
    dispatch = dispatch_factory(slow_seconds, entered)
    listener, address = listen()
    if mode == 'concurrent':
        loop, thread = serve_concurrent(listener, dispatch, handlers=handlers)
        stop = None
    else:
        stop, thread = serve_serial(listener, dispatch)
        loop = None
    slow_result = {}
    slow_thread = threading.Thread(target=lambda: slow_result.update(
        {'value': one_request(address, 'slow')}), daemon=True)
    slow_thread.start()
    if not entered.wait(5):
        raise RuntimeError('slow request did not reach dispatch')
    barrier = threading.Barrier(2)
    started = threading.Event()
    import concurrent.futures as futures
    with futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(workload, address, clients=clients, requests=requests,
                             barrier=barrier, start_after=started)
        started.set()
        barrier.wait(10)
        samples, errors = future.result(timeout=180)
    slow_thread.join(timeout=30)
    if stop is not None:
        stop.set()
    if loop is not None:
        loop.close()
    listener.close()
    return {'mode': mode, 'samples': samples, 'errors': errors, 'slow': slow_result,
            'p50': percentile(samples, 50), 'p95': percentile(samples, 95),
            'p99': percentile(samples, 99), 'count': len(samples),
            'mean': statistics.fmean(samples) if samples else None,
            'stdev': statistics.stdev(samples) if len(samples) > 1 else 0.0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('baseline', 'concurrent', 'both'), default='both')
    parser.add_argument('--clients', type=int, default=16)
    parser.add_argument('--requests', type=int, default=20)
    parser.add_argument('--slow-seconds', type=float, default=0.4)
    parser.add_argument('--handlers', type=int, default=32)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    modes = ('baseline', 'concurrent') if args.mode == 'both' else (args.mode,)
    manifest = {'timestamp': datetime.now(timezone.utc).isoformat(),
                'platform': platform.platform(), 'python': sys.version,
                'cpu_count': os.cpu_count(), 'clients': args.clients,
                'requests_per_client': args.requests, 'slow_seconds': args.slow_seconds,
                'handlers': args.handlers, 'transport': 'loopback TCP framed JSON',
                'scope': 'server-side loop latency; excludes network RTT and UI'}
    results = [run_mode(mode, clients=args.clients, requests=args.requests,
                        slow_seconds=args.slow_seconds, handlers=args.handlers)
               for mode in modes]
    report = {'manifest': manifest, 'results': results}
    print(json.dumps(report, indent=2))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
