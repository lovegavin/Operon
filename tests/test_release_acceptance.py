import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "check_release_acceptance", ROOT / "scripts" / "check_release_acceptance.py"
)
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


def _record() -> dict:
    return {
        "schema_version": 1,
        "library_version": "8.0.8",
        "commit": "4a566727",
        "bundle": {
            "asset": "Operon-Library-v8.0.8-Linux.operon-library.zip",
            "sha256": "e4884979192e69c3998d8ad573df1572419c9d668c49f8dcb42c5dbffdcf2d1e",
        },
        "application": "4.1.9",
        "os": "linux",
        "profile": {"clean": True, "root": "/tmp/profile"},
        "install": {
            "status": "PASS",
            "installed_version": "8.0.8",
            "source_root": "/tmp/profile/library/8.0.8",
            "exit_code": 0,
        },
        "environment": {
            "name": "openmm81",
            "status": "PASS",
            "spec_sha256": "59c91e698872254ba783294b5264eff1904f634ecfbf1213a1319701b8a07c32",
            "interpreter": "/tmp/profile/envs/openmm81/bin/python",
            "bytes": 154686868,
            "files": 3748,
            "imports": ["openmm", "numpy"],
            "tool_probe": "PDBFixer 1MEL -> 8247 atoms / 587 residues",
        },
        "operator": {
            "id": "interface_alanine_scan",
            "status": "PASS",
            "command": "operon run route",
            "outputs": [{"name": "alanine.csv", "sha256": "0" * 64}],
        },
        "layers": {name: {"status": "PASS"} for name in ("L1", "L2", "L3", "L4", "L5")},
        "release_blocking": [],
    }


def test_acceptance_record_passes():
    assert checker.validate(_record()) == []


def test_missing_bundle_identity_fails():
    record = _record()
    record["bundle"]["sha256"] = "not-a-sha"
    errors = checker.validate(record)
    assert any("bundle.sha256" in error for error in errors)


def test_bundle_hash_mismatch_fails(tmp_path):
    bundle = tmp_path / "Operon-Library-v8.0.8-Linux.operon-library.zip"
    bundle.write_bytes(b"frozen artifact")
    errors = checker.validate(_record(), bundle)
    assert any("does not match" in error for error in errors)
    assert hashlib.sha256(bundle.read_bytes()).hexdigest() != _record()["bundle"]["sha256"]
