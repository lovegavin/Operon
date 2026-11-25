from __future__ import annotations

import json
import os

from src.task.step.steps import _resources_common as common
from src.task.step.steps.alphafold2_predict import data_directory, runner_path


def _manifest(tmp_path, root, env="OPERON_TEST_RESOURCE_ROOT"):
    path = tmp_path / "resources.json"
    path.write_text(
        json.dumps(
            {
                "resources": [
                    {
                        "id": "toy",
                        "title": "Toy",
                        "kind": "tree",
                        "url": "",
                        "install": "",
                        "env": env,
                        "roots": [str(root)],
                        "files": ["payload.txt"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return path


def test_apply_environment_exports_existing_root(tmp_path, monkeypatch):
    root = tmp_path / "toy"
    root.mkdir()
    (root / "payload.txt").write_text("x", encoding="utf-8")
    monkeypatch.delenv("OPERON_TEST_RESOURCE_ROOT", raising=False)

    applied = common.apply_environment(_manifest(tmp_path, root))

    assert applied == {"OPERON_TEST_RESOURCE_ROOT": str(root)}
    assert os.environ["OPERON_TEST_RESOURCE_ROOT"] == str(root)


def test_apply_environment_keeps_an_explicit_value(tmp_path, monkeypatch):
    root = tmp_path / "toy"
    root.mkdir()
    (root / "payload.txt").write_text("x", encoding="utf-8")
    chosen = tmp_path / "chosen"
    chosen.mkdir()
    monkeypatch.setenv("OPERON_TEST_RESOURCE_ROOT", str(chosen))

    assert common.apply_environment(_manifest(tmp_path, root)) == {}
    assert os.environ["OPERON_TEST_RESOURCE_ROOT"] == str(chosen)


def test_apply_environment_skips_missing_root(tmp_path, monkeypatch):
    monkeypatch.delenv("OPERON_TEST_RESOURCE_ROOT", raising=False)
    applied = common.apply_environment(_manifest(tmp_path, tmp_path / "absent"))
    assert applied == {}
    assert "OPERON_TEST_RESOURCE_ROOT" not in os.environ


def test_manifest_links_the_alphafold2_checkout():
    resource = common.load_resources()["alphafold2_code"]
    assert resource.env == "OPERON_ALPHAFOLD2_HOME"
    assert "run_alphafold.py" in resource.expected_files


def test_alphafold2_runner_uses_the_linked_checkout(tmp_path, monkeypatch):
    checkout = tmp_path / "alphafold-2.3.1"
    checkout.mkdir()
    (checkout / "run_alphafold.py").write_text("# runner\n", encoding="utf-8")
    monkeypatch.setenv("OPERON_ALPHAFOLD2_HOME", str(checkout))
    monkeypatch.delenv("OPERON_ALPHAFOLD_HOME", raising=False)

    assert runner_path({}) == checkout / "run_alphafold.py"


def test_alphafold2_data_directory_accepts_the_declared_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("OPERON_ALPHAFOLD_DATA", str(tmp_path))
    monkeypatch.delenv("OPERON_ALPHAFOLD2_DATA", raising=False)

    assert data_directory({}) == tmp_path


def test_worker_applies_the_resource_environment(monkeypatch):
    from src.task.step.steps import _resources_common
    from operon import env_worker

    calls = []
    monkeypatch.setattr(
        _resources_common,
        "apply_environment",
        lambda *args, **kwargs: calls.append((args, kwargs)) or {},
    )

    env_worker._apply_resource_environment()

    assert calls


def test_worker_ignores_a_library_without_the_helper(monkeypatch):
    from src.task.step.steps import _resources_common
    from operon import env_worker

    def boom(*args, **kwargs):
        raise ImportError("older library")

    monkeypatch.setattr(_resources_common, "apply_environment", boom)

    env_worker._apply_resource_environment()  # must not raise
