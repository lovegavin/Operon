import json
import zipfile
from pathlib import Path

from operon.environments import manifest_path
from operon.library_bundle import build_bundle, unpack_bundle
from operon.plugins import _runtime_class

ROOT = Path(__file__).resolve().parents[1]
LIBRARY_VERSION = json.loads((ROOT / "library/release.json").read_text(encoding="utf-8"))["version"]


def test_bundle_carries_environment_manifest(tmp_path):
    result = build_bundle(ROOT, tmp_path / "out", LIBRARY_VERSION)
    with zipfile.ZipFile(result["bundle"]) as archive:
        names = set(archive.namelist())
        document = json.loads(archive.read("library.json"))
        environment = archive.read("sources/operon/environments.json")
    assert "sources/operon/environments.json" in names
    assert document["minimum_application"] == "4.1.0"
    assert "openmm81" in json.loads(environment)["environments"]


def test_environment_manifest_prefers_active_library_source(tmp_path):
    source = tmp_path / "sources"
    (source / "operon").mkdir(parents=True)
    manifest = {"version": 1, "environments": {"demo": {"python": "3.11"}}}
    (source / "operon/environments.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert manifest_path(source) == source / "operon/environments.json"


def test_environment_descriptors_use_environment_proxy():
    descriptor = {
        "id": "demo", "kind": "operator", "version": "1.0.0",
        "inputs_arity": 0, "outputs": ["result"], "output_parameter": "output",
        "contracts": {"inputs": [], "output": {"mode": "declare", "schema": {}}},
        "resources": {"environment": "openmm81"},
    }
    step = _runtime_class(descriptor, {})
    assert step.__name__ == "EnvironmentStep"
    assert step._environment == "openmm81"
