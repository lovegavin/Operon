"""Real Linux monitors/signals with a fixture generation lease, not runtime E2E."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import sys
import time

import psutil
import pytest

from operon.engine.supervisor import ProcessSupervisor, LaunchSpec, SupervisorError, identity_alive
from operon.environment_store import EnvironmentStore
from test_environment_generations import FixtureBuilder, requirement


pytestmark = pytest.mark.skipif(not sys.platform.startswith('linux'), reason='Requires actual Linux subreaper/signals')


def _until(check, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = check()
        if result:
            return result
        time.sleep(.01)
    raise AssertionError('Explicit process handshake did not arrive')


def _setup(tmp_path, monkeypatch, *, mode='gate', ready_timeout=10):
    store = EnvironmentStore(tmp_path / 'env')
    binding = store.prepare(requirement(), FixtureBuilder())
    owner = ProcessSupervisor(tmp_path / 'super', environment_store=store,
                              ready_timeout_seconds=ready_timeout)
    helper = owner._containment_helper()
    gate, initializing = tmp_path / 'initialize.release', tmp_path / 'initializing'
    wrapper = tmp_path / 'delayed-monitor.py'
    if mode == 'gate':
        body = f"while not Path({str(gate)!r}).exists(): time.sleep(.01)\nrunpy.run_path({str(helper)!r}, run_name='__main__')\n"
    elif mode == 'exit':
        body = 'raise SystemExit(17)\n'
    else:
        # A forged readiness record must never release the scientific start gate.
        body = """import psutil
request=json.loads(Path(sys.argv[1]).read_text())
identity={'pid':os.getpid(), 'created':psutil.Process().create_time(), 'boot_id':request['boot_id'], 'host':None}
value={'schema_version':1, 'attempt_id':request['attempt_id'], 'fence':request['fence'], 'ready':True, 'identity':identity}
"""
        body += { 'wrong_fence': "value['fence'] += 1\n",
                  'wrong_identity': "value['identity']['created'] += 1\n" }[mode]
        body += "path=Path(request['ready']); temporary=path.with_suffix('.tmp'); temporary.write_text(json.dumps(value)); os.replace(temporary,path)\n"
        body += f"while not Path({str(gate)!r}).exists(): time.sleep(.01)\n"
    wrapper.write_text('import json,os,runpy,sys,time\nfrom pathlib import Path\n'
        + f'Path({str(initializing)!r}).touch()\n' + body, encoding='utf-8')
    monkeypatch.setattr(owner, '_containment_helper', lambda: wrapper)
    spec = LaunchSpec((sys.executable, '-I', '-c', 'import time; time.sleep(60)'), str(tmp_path),
        dict(os.environ), str(tmp_path / 'worker.log'), generation_id=binding.generation_id)
    return owner, store, spec, gate, initializing


def _cleanup(owner):
    process = owner._processes.get('attempt')
    if process is None:
        return
    if process.poll() is None:
        try:
            owner.stop('attempt', fence=7, timeout=2)
        except SupervisorError:
            # Fault-case cleanup terminates only this test-owned monitor/tree.
            # It never writes proof or edits/releases the generation lease.
            if process.poll() is None:
                try:
                    for child in reversed(psutil.Process(process.pid).children(recursive=True)):
                        try:
                            child.kill()
                        except psutil.NoSuchProcess:
                            pass
                except psutil.NoSuchProcess:
                    pass
                process.kill()
    process.wait(timeout=5)


def test_slow_monitor_initialization_blocks_running_and_early_stop_then_cancels(tmp_path, monkeypatch):
    owner, store, spec, gate, initializing = _setup(tmp_path, monkeypatch)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(owner.launch, 'attempt', fence=7, spec=spec)
        try:
            _until(initializing.exists)
            receipt = _until(lambda: (value if (value := owner.read_receipt('attempt'))
                                     and value.identity and value.state == 'spawned' else None))
            assert not future.done() and not (owner.directory / 'attempt.ready.json').exists()
            with pytest.raises(SupervisorError) as caught:
                owner.stop('attempt', fence=7, timeout=.1)
            assert caught.value.code == 'recovery_required'
            assert identity_alive(receipt.identity), 'Stop must not signal the uninitialized monitor'
            assert not (owner.directory / 'attempt.start').exists()
            assert not (owner.directory / 'attempt.tree-exit.json').exists()
            gate.touch()
            running = future.result(timeout=12)
            assert running.state == 'started'
            assert owner._monitor_ready('attempt', fence=7, identity=running.identity)
            # No arbitrary post-launch delay: cancellation immediately after
            # running must find installed handlers and obtain ECHILD proof.
            assert owner.stop('attempt', fence=7, timeout=10).confirmed
            proof = json.loads((owner.directory / 'attempt.tree-exit.json').read_text())
            assert proof['identity'] == running.identity.to_json()
            assert proof['attempt_id'] == 'attempt' and proof['fence'] == 7
            assert proof['tree_exited'] is True and proof['cancelled'] is True
            assert proof['method'] == 'linux-subreaper'
            assert json.loads((store.root / 'leases/attempt.json').read_text())['state'] == 'released'
        finally:
            gate.touch(exist_ok=True)
            try:
                future.result(timeout=12)
            except Exception:
                pass
            _cleanup(owner)


@pytest.mark.parametrize('mode', ['gate', 'exit', 'wrong_fence', 'wrong_identity'])
def test_unready_or_invalid_monitor_quarantines_without_start_or_exit_proof(tmp_path, monkeypatch, mode):
    owner, store, spec, gate, _ = _setup(tmp_path, monkeypatch, mode=mode,
                                      ready_timeout=.5 if mode == 'gate' else 10)
    try:
        with pytest.raises(SupervisorError) as caught:
            owner.launch('attempt', fence=7, spec=spec)
        assert caught.value.code == 'recovery_required'
        assert not (owner.directory / 'attempt.start').exists()
        assert not (owner.directory / 'attempt.tree-exit.json').exists()
        assert json.loads((store.root / 'leases/attempt.json').read_text())['state'] == 'spawning'
        receipt = owner.read_receipt('attempt')
        assert receipt.identity is not None and not owner.preparation_rejected('attempt', fence=7)
        if mode.startswith('wrong_'):
            assert (owner.directory / 'attempt.ready.json').exists()
            assert not owner._monitor_ready('attempt', fence=7, identity=receipt.identity)
        elif mode == 'exit':
            assert owner._processes['attempt'].poll() == 17
        if identity_alive(receipt.identity):
            with pytest.raises(SupervisorError) as caught:
                owner.reconcile('attempt', fence=7)
            assert caught.value.code == 'recovery_required'
            with pytest.raises(SupervisorError):
                owner.stop('attempt', fence=7, timeout=.1)
            assert identity_alive(receipt.identity)
    finally:
        _cleanup(owner)
