import json
from pathlib import Path

import pytest

from operon import plugins as plugins_module
from operon.plugins import PluginManager


def test_refresh_without_editable_library_is_noop(tmp_path, monkeypatch):
    app_root = tmp_path / "app"
    app_root.mkdir()
    monkeypatch.setattr(plugins_module, "ROOT", app_root)
    manager = PluginManager(tmp_path / "data", library_root=tmp_path / "library")
    result = manager.refresh()
    assert result["updated"] == []
    assert result["unchanged"] == ["No editable operator library is installed"]
    assert isinstance(result["generation"], str) and result["generation"]
    assert not (manager.source_root / "operon" / "builtin_packages.json").exists()
    assert not list((tmp_path / "data").rglob("builtin_packages.json"))
