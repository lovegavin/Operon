"""Startup must refuse agent work while Setup replaces the installation."""
from __future__ import annotations

import pytest

from operon import installation_maintenance as maintenance


def test_require_idle_allows_a_normal_start(monkeypatch):
    monkeypatch.setattr(maintenance, "maintenance_active", lambda root: False)
    maintenance.require_idle()  # must not raise


def test_require_idle_refuses_during_setup(monkeypatch):
    monkeypatch.setattr(maintenance, "maintenance_active", lambda root: True)
    with pytest.raises(SystemExit) as blocked:
        maintenance.require_idle()
    assert "updated or uninstalled" in str(blocked.value)


def test_require_idle_checks_the_installation_root(monkeypatch):
    seen = {}

    def fake(root):
        seen["root"] = root
        return False

    monkeypatch.setattr(maintenance, "maintenance_active", fake)
    maintenance.require_idle()
    assert seen["root"].name == "Operon-540"
    assert (seen["root"] / "operon" / "installation_maintenance.py").is_file()
