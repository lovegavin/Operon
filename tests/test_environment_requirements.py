"""Tests for scripts/environment_requirements.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "environment_requirements.py"


def load_module():
    spec = importlib.util.spec_from_file_location("environment_requirements", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_merge_keeps_one_specifier_per_package():
    module = load_module()
    merged = module.merge(["numpy>=1.24", "numpy>=1.26", "scipy", "SciPy>=1.11"])
    assert merged == ["numpy>=1.26", "SciPy>=1.11"]


def test_compare_reports_missing_and_unused():
    module = load_module()
    registry = {
        "descriptors": [
            {"id": "alpha", "dependencies": ["numpy>=1.24", "scipy>=1.11"], "resources": {"environment": "core"}},
            {"id": "beta", "dependencies": ["numpy>=1.24"], "resources": {"environment": "core"}},
            {"id": "gamma", "dependencies": ["rdkit"], "resources": {"environment": "chem"}},
        ]
    }
    environments = {
        "environments": {
            "core": {"requirements": ["numpy>=1.26", "pandas"]},
            "chem": {"requirements": []},
        }
    }
    rows = {row["environment"]: row for row in module.compare(environments, registry)}
    assert rows["core"]["operators"] == 2
    assert rows["core"]["needed"] == ["numpy>=1.24", "scipy>=1.11"]
    assert rows["core"]["missing"] == ["scipy>=1.11"]
    assert rows["core"]["unused"] == ["pandas"]
    assert rows["chem"]["missing"] == ["rdkit"]


def test_environment_entries_accepts_plain_mapping():
    module = load_module()
    assert module.environment_entries({"core": {}}) == {"core": {}}
    assert module.environment_entries({"environments": {"core": {}}}) == {"core": {}}