"""Bounded control admission: slow clients, frame deadlines, handler and byte limits."""
from concurrent.futures import ThreadPoolExecutor
import json
import socket
import struct
import threading
import time

from operon.engine.control import ControlLimits, ControlLoop


def start_loop(dispatch, **limits):
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(('127.0.0.1', 0))
    listener.listen(64)
    loop = ControlLoop(dispatch, limits=ControlLimits(**limits))
    thread = threading.Thread(target=loop.serve,
                              kwargs={'listener': listener, 'alive': lambda: False, 'idle_seconds': 60},
                              daemon=True)
    thread.start()
    return loop, listener.getsockname(), thread


def request(address, method, params=None, *, timeout=10, slow_body=None):
    client = socket.create_connection(address, timeout=timeout)
    payload = json.dumps({'id': 'req-' + method, 'method': method, 'params': params or {}}).encode()
    client.sendall(struct.pack('!Q', len(payload)))
    if slow_body is None:
        client.sendall(payload)
    else:
        for index in range(len(payload)):
            client.sendall(payload[index:index + 1])
            time.sleep(slow_body)
    header = recv_exact(client, 8)
    size = struct.unpack('!Q', header)[0]
    value = json.loads(recv_exact(client, size))
    client.close()
    return value


def recv_exact(client, size):
    data = b''
    while len(data) < size:
        block = client.recv(size - len(data))
        if not block:
            raise ConnectionError('closed')
        data += block
    return data


def test_a_slow_handler_does_not_block_another_client():
    entered = threading.Event()

    def dispatch(method, params):
        if method == 'slow':
            entered.set()
            time.sleep(0.9)
            return {'slept': True}
        return {'status': 'running'}

    loop, address, thread = start_loop(dispatch, max_handlers=8)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            slow = pool.submit(request, address, 'slow')
            assert entered.wait(2)
            started = time.perf_counter()
            value = request(address, 'status')
            elapsed = time.perf_counter() - started
            assert value['ok'] and value['value'] == {'status': 'running'}
            # Server-side status acknowledgement is far below the 0.9s handler.
            assert elapsed < 0.5, elapsed
            assert slow.result()['ok']
    finally:
        loop.close()


def test_slow_drip_body_hits_the_absolute_deadline_and_frees_the_handler():
    def dispatch(method, params):
        return {'ok': True}

    loop, address, thread = start_loop(dispatch, max_handlers=2, absolute_seconds=0.5,
                                       inactivity_seconds=5)
    try:
        started = time.perf_counter()
        client = socket.create_connection(address, timeout=10)
        client.sendall(struct.pack('!Q', 1000) + b'{"method":')
        header = recv_exact(client, 8)
        size = struct.unpack('!Q', header)[0]
        value = json.loads(recv_exact(client, size))
        client.close()
        elapsed = time.perf_counter() - started
        assert value['ok'] is False and value['code'] == 'request_timeout'
        assert elapsed < 4, elapsed
        # The handler slot was released: an ordinary request now succeeds.
        assert request(address, 'status')['ok']
    finally:
        loop.close()


def test_handler_limit_rejects_busy_immediately():
    inside = threading.Event()

    def dispatch(method, params):
        inside.set()
        time.sleep(1.2)
        return {'done': True}

    loop, address, thread = start_loop(dispatch, max_handlers=1)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            first = pool.submit(request, address, 'work')
            assert inside.wait(2)
            started = time.perf_counter()
            value = request(address, 'status')
            elapsed = time.perf_counter() - started
            assert value['ok'] is False and value['code'] == 'busy'
            assert elapsed < 0.6, elapsed
            assert first.result()['ok']
    finally:
        loop.close()


def test_aggregate_body_budget_rejects_before_reading_the_body():
    def dispatch(method, params):
        return {'unexpected': True}

    loop, address, thread = start_loop(dispatch, max_handlers=2, max_inflight_bytes=64)
    try:
        client = socket.create_connection(address, timeout=5)
        client.sendall(struct.pack('!Q', 1024))
        header = recv_exact(client, 8)
        size = struct.unpack('!Q', header)[0]
        value = json.loads(recv_exact(client, size))
        client.close()
        assert value['ok'] is False and value['code'] == 'busy'
    finally:
        loop.close()


def test_decoded_request_is_reserved_until_dispatch_finishes():
    entered, release = threading.Event(), threading.Event()
    def dispatch(method, params):
        entered.set()
        assert release.wait(3)
        return {}
    loop, address, _ = start_loop(dispatch)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(request, address, 'hold', {'rows': list(range(1000))})
            assert entered.wait(2)
            assert loop.budget.used > 10000
            release.set()
            assert future.result()['ok']
        deadline = time.monotonic() + 2
        while loop.budget.used and time.monotonic() < deadline:
            time.sleep(.01)
        assert loop.budget.used == 0
    finally:
        release.set(); loop.close()


def test_nested_control_json_is_rejected_before_dispatch():
    value = {}
    for _ in range(70): value = {'x': value}
    loop, address, _ = start_loop(lambda *args: (_ for _ in ()).throw(AssertionError('dispatch')))
    try:
        result = request(address, 'too-deep', value)
        assert result['code'] == 'payload_too_large'
    finally:
        loop.close()


def test_bulk_dispatch_cannot_occupy_reserved_lifecycle_threads():
    release = threading.Event()
    entered = []
    def dispatch(method, params):
        if method == 'bulk':
            entered.append(1)
            assert release.wait(5)
        return {'method': method}
    loop, address, _ = start_loop(dispatch, max_handlers=8)
    try:
        with ThreadPoolExecutor(max_workers=6) as workers:
            futures = [workers.submit(request, address, 'bulk') for _ in range(6)]
            deadline = time.monotonic() + 3
            while len(entered) < 6 and time.monotonic() < deadline: time.sleep(.01)
            assert len(entered) == 6
            assert request(address, 'bulk')['code'] == 'busy'
            assert request(address, 'status')['ok']
            assert request(address, 'run.cancel')['ok']
            release.set()
            assert all(f.result()['ok'] for f in futures)
    finally:
        release.set(); loop.close()


def test_client_disconnect_detaches_observation_but_does_not_cancel_dispatch():
    entered = threading.Event()
    release = threading.Event()
    finished = threading.Event()

    def dispatch(method, params):
        entered.set()
        assert release.wait(5)
        finished.set()
        return {'continued': True}

    loop, address, thread = start_loop(dispatch, max_handlers=2)
    try:
        client = socket.create_connection(address, timeout=5)
        payload = json.dumps({'id': 'disconnect', 'method': 'run', 'params': {}}).encode()
        client.sendall(struct.pack('!Q', len(payload)) + payload)
        assert entered.wait(2)
        client.close()  # the client no longer observes the in-flight operation
        release.set()
        assert finished.wait(2)
        assert loop.stats()['errors'] == 0
    finally:
        loop.close()


def test_invalid_method_and_oversized_frame_are_machine_readable():
    def dispatch(method, params):
        return {'value': method}

    loop, address, thread = start_loop(dispatch, max_handlers=2, max_frame_bytes=1024)
    try:
        client = socket.create_connection(address, timeout=5)
        client.sendall(struct.pack('!Q', 2048))
        header = recv_exact(client, 8)
        size = struct.unpack('!Q', header)[0]
        value = json.loads(recv_exact(client, size))
        client.close()
        assert value['code'] == 'payload_too_large'
        client = socket.create_connection(address, timeout=5)
        client.sendall(struct.pack('!Q', 2) + b'[]')
        header = recv_exact(client, 8)
        size = struct.unpack('!Q', header)[0]
        value = json.loads(recv_exact(client, size))
        client.close()
        assert value['code'] == 'invalid_request'
    finally:
        loop.close()

def test_dispatch_exception_is_reported_to_diagnostics_without_breaking_response():
    seen = []
    def dispatch(method, params):
        raise ValueError('password=hunter2 request failed')
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(('127.0.0.1', 0)); listener.listen(8)
    loop = ControlLoop(dispatch, limits=ControlLimits(max_handlers=2),
                       on_error=lambda exc, context: seen.append((str(exc), context)))
    thread = threading.Thread(target=loop.serve,
                              kwargs={'listener': listener, 'alive': lambda: False, 'idle_seconds': 10},
                              daemon=True)
    thread.start()
    try:
        value = request(listener.getsockname(), 'status')
        assert value['ok'] is False and value['code'] == 'invalid_request'
        assert seen and 'password=hunter2' in seen[0][0]
        assert seen[0][1]['method'] == 'status'
    finally:
        loop.close()


def test_rejected_silent_connections_do_not_block_the_accept_thread():
    loop = ControlLoop(lambda method, params: None, limits=ControlLimits(max_handlers=1))
    peers = []
    assert loop.slots.acquire(blocking=False)
    try:
        started = time.monotonic()
        for _ in range(8):
            server, client = socket.socketpair()
            peers.append(client)
            assert not loop.submit(server)
        # Rejection must never perform a network read/drain in the accept loop.
        assert time.monotonic() - started < 0.5
    finally:
        for peer in peers:
            peer.close()
        loop.slots.release()
        loop.close()


def test_planning_concurrency_is_bounded_and_status_bypasses_it():
    guard, release = threading.Lock(), threading.Event()
    active, peak = 0, 0
    def dispatch(method, params):
        nonlocal active, peak
        if method != 'compile': return {'alive': True}
        with guard:
            active += 1
            peak = max(peak, active)
        try:
            assert release.wait(4)
            return {'compiled': True}
        finally:
            with guard: active -= 1
    loop, address, _ = start_loop(dispatch, max_handlers=12, max_planning_handlers=2)
    try:
        with ThreadPoolExecutor(max_workers=6) as clients:
            pending = [clients.submit(request, address, 'compile') for _ in range(6)]
            deadline = time.monotonic() + 2
            while peak < 2 and time.monotonic() < deadline: time.sleep(.01)
            assert peak == 2
            assert request(address, 'status', timeout=1)['ok']
            release.set()
            assert all(future.result()['ok'] for future in pending)
            assert peak == 2
    finally:
        release.set()
        loop.close()


def test_rejection_drain_has_an_absolute_deadline_even_if_peer_keeps_sending():
    loop = ControlLoop(lambda method, params: None)
    server, client = socket.socketpair()
    stop = threading.Event()
    def drip():
        while not stop.wait(.05):
            try:
                client.sendall(b'x')
            except OSError:
                return
    thread = threading.Thread(target=drip, daemon=True)
    thread.start()
    try:
        started = time.monotonic()
        loop._send_busy(server)
        assert time.monotonic() - started < .8
    finally:
        stop.set(); client.close(); thread.join(timeout=1); loop.close()
