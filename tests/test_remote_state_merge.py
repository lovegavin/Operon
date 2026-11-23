"""Two adapters share one remote state file; a save must not erase the other."""
import json
from pathlib import Path
from types import SimpleNamespace

from src.web.remote_service import RemoteManager


def record(name):
    return {'profile_id': 'p', 'job_id': name,
            'summary': {'id': name, 'name': name, 'status': 'complete'}}


def test_persist_keeps_jobs_written_by_another_instance(tmp_path):
    desktop = RemoteManager(SimpleNamespace(directory=tmp_path))
    agent = RemoteManager(SimpleNamespace(directory=tmp_path))
    desktop.state['jobs']['ssh-p-desktop'] = record('desktop')
    desktop.persist()

    agent.state['jobs']['ssh-p-agent'] = record('agent')
    agent.persist()

    saved = json.loads(Path(tmp_path, 'remote', 'profiles.json').read_text(encoding='utf-8'))
    assert set(saved['jobs']) == {'ssh-p-desktop', 'ssh-p-agent'}


def test_the_merged_view_is_visible_to_the_instance_that_saved(tmp_path):
    first = RemoteManager(SimpleNamespace(directory=tmp_path))
    second = RemoteManager(SimpleNamespace(directory=tmp_path))
    second.state['jobs']['ssh-p-b'] = record('b')
    second.persist()

    first.state['jobs']['ssh-p-a'] = record('a')
    first.persist()

    assert {item['id'] for item in first.history()} == {'a', 'b'}
    reopened = RemoteManager(SimpleNamespace(directory=tmp_path))
    assert {item['id'] for item in reopened.history()} == {'a', 'b'}


def test_a_cancelled_connection_event_is_not_reused(tmp_path):
    import threading
    from src.web.remote_service import RemoteManager

    manager = RemoteManager.__new__(RemoteManager)
    manager.lock = threading.RLock()
    manager.connecting = {'srv': threading.Event()}
    manager.connecting['srv'].set()
    manager.pools = {}
    manager.connections = {}
    manager.credentials = {}

    manager.disconnect('srv')

    assert 'srv' not in manager.connecting


def test_an_install_may_take_over_a_stale_connection() -> None:
    from src.web.remote_service import RemoteError, RemoteManager
    import threading

    manager = RemoteManager.__new__(RemoteManager)
    manager.lock = threading.RLock()
    manager.connecting = {'srv': threading.Event()}
    manager.connections = {}
    manager.pools = {}
    manager.credentials = {}
    manager.pending_keys = {}
    manager.state = {'profiles': {'srv': {'host': 'h', 'port': 22, 'environment': 'managed'}}}
    manager.directory = __import__('pathlib').Path('.')
    manager._local_build = lambda: {}
    stale = manager.connecting['srv']
    try:
        manager.connect('srv', {}, install=True)
    except RemoteError as error:  # pragma: no cover - the takeover must not raise this
        assert '正在连接' not in str(error), str(error)
    except Exception:
        pass
    finally:
        assert stale.is_set()
        assert 'srv' not in manager.connecting
