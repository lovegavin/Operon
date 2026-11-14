from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from src.core.errors import StepError
from src.task.step.steps.boltz_predict import cache_directory


def _resource(*roots, env="OPERON_BOLTZ_CACHE"):
    return SimpleNamespace(env=env, roots=tuple(str(root) for root in roots))


def test_creates_first_declared_root_even_when_missing(tmp_path, monkeypatch):
    monkeypatch.delenv("OPERON_BOLTZ_CACHE", raising=False)
    canonical = tmp_path / "canonical" / "boltz"
    existing = tmp_path / "existing"
    existing.mkdir()

    resolved = cache_directory({}, _resource(canonical, existing))

    assert Path(resolved) == canonical.resolve()
    assert canonical.is_dir()


def test_explicit_cache_dir_wins(tmp_path, monkeypatch):
    monkeypatch.setenv("OPERON_BOLTZ_CACHE", str(tmp_path / "environment"))
    explicit = tmp_path / "explicit"

    resolved = cache_directory({"cache_dir": str(explicit)}, _resource(tmp_path / "root"))

    assert Path(resolved) == explicit.resolve()
    assert explicit.is_dir()


def test_environment_variable_is_used(tmp_path, monkeypatch):
    monkeypatch.setenv("OPERON_BOLTZ_CACHE", str(tmp_path / "environment"))

    resolved = cache_directory({}, _resource(tmp_path / "root"))

    assert Path(resolved) == (tmp_path / "environment").resolve()


def test_fallback_is_the_operon_resource_directory(tmp_path, monkeypatch):
    monkeypatch.delenv("OPERON_BOLTZ_CACHE", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))

    resolved = cache_directory({}, None)

    assert Path(resolved) == (tmp_path / ".local/share/operon/resources/boltz").resolve()


def test_unwritable_cache_raises_step_error(tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("file", encoding="utf-8")

    with pytest.raises(StepError, match="cannot create cache directory"):
        cache_directory({"cache_dir": str(blocker / "child")}, None)
