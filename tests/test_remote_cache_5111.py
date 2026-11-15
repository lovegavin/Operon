import json
from pathlib import Path
from types import SimpleNamespace
import operon
from src.web.remote_service import RemoteManager


def _manager(tmp_path):
    state = tmp_path / 'state'
    state.mkdir(exist_ok=True)
    return RemoteManager(SimpleNamespace(directory=state))


def test_upgrade_drops_catalogue_from_another_application(tmp_path):
    manager = _manager(tmp_path)
    stale = manager.directory / 'srv.catalog.json'
    stale.write_text(json.dumps({'build': {'application': {'version': '5.1.9'}}}), encoding='utf-8')
    current = manager.directory / 'live.catalog.json'
    current.write_text(json.dumps({'build': {'application': {'version': operon.__version__}}}), encoding='utf-8')
    fresh = RemoteManager(SimpleNamespace(directory=tmp_path / 'state'))
    assert not stale.exists()
    assert current.exists()
    fresh.forget_cache('live')
    assert not current.exists()


def test_forget_cache_is_idempotent(tmp_path):
    _manager(tmp_path).forget_cache('missing')