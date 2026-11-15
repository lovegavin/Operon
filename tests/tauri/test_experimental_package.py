from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "package_tauri_experimental.py"
VERIFICATION_ROOT = ROOT / "verification" / "tauri-package-tests"


@pytest.fixture
def work_dir():
    """Per-test scratch tree inside the project verification workspace."""
    VERIFICATION_ROOT.mkdir(parents=True, exist_ok=True)
    case = Path(tempfile.mkdtemp(prefix="case-", dir=VERIFICATION_ROOT))
    try:
        yield case
    finally:
        shutil.rmtree(case, ignore_errors=True)
        try:
            VERIFICATION_ROOT.rmdir()
        except OSError:
            pass


def load_module():
    spec = importlib.util.spec_from_file_location("package_tauri_experimental", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write(path: Path, body: bytes = b"value"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)


def make_base(work_dir: Path, extra: bool = False):
    base = work_dir / "base"
    files = {
        "runtime/python/python.exe": b"MZruntime",
        "scripts/desktop_server.py": b"print('server')",
        "frontend/index.html": b"<html></html>",
        "library/base/seed.json": b'{"seed":true}',
        "package-manifest.json": b"",
    }
    for relative, body in files.items():
        write(base / relative, body)
    manifest = {
        "version": "5.3.0",
        "python_bundled": True,
        "files": [
            {"path": path, "bytes": (base / path).stat().st_size,
             "sha256": hashlib.sha256((base / path).read_bytes()).hexdigest()}
            for path in files if path != "package-manifest.json"
        ],
    }
    (base / "package-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    if extra:
        write(base / "unexpected.txt", b"extra")
    return base


def test_base_payload_requires_an_exact_manifest_set(work_dir):
    module = load_module()
    base = make_base(work_dir)
    module.verify_base_payload(base)
    write(base / "unexpected.txt", b"extra")
    with pytest.raises(ValueError, match="file set"):
        module.verify_base_payload(base)


def test_safe_relative_rejects_traversal_and_reserved_names(work_dir):
    module = load_module()
    assert module.safe_relative("library/base/seed.json") == "library/base/seed.json"
    for value in ("../escape", "a/../../b", "C:/absolute", "CON", "lpt1.txt", "file."):
        with pytest.raises(ValueError):
            module.safe_relative(value)


def test_manifest_identity_is_deterministic_and_uses_lock_hashes(work_dir):
    module = load_module()
    candidate = work_dir / "candidate"
    write(candidate / "operon-desktop-experimental.exe", b"MZhost")
    write(candidate / "runtime/python/python.exe", b"MZruntime")
    write(candidate / "frontend/index.html", b"<html></html>")
    cargo = work_dir / "Cargo.lock"
    frontend = work_dir / "package-lock.json"
    cargo.write_text("cargo", encoding="utf-8")
    frontend.write_text("frontend", encoding="utf-8")
    base_manifest = work_dir / "package-manifest.json"
    base_manifest.write_text("{}", encoding="utf-8")
    manifest = module.build_manifest(candidate, "tauri-0.1.0-rc1", "abc123", False, frontend, cargo, base_manifest)
    assert manifest["product"] == module.PRODUCT
    assert manifest["channel"] == "experimental"
    assert manifest["payload_id"] == module.payload_id(manifest)
    assert manifest["locks"]["cargo_lock_sha256"] == module.digest(cargo)
    assert manifest["locks"]["frontend_lock_sha256"] == module.digest(frontend)
    assert {item["path"] for item in manifest["files"]} == {
        "operon-desktop-experimental.exe", "runtime/python/python.exe", "frontend/index.html"
    }


def test_production_wrappers_are_removed_but_library_is_preserved(work_dir):
    module = load_module()
    source = make_base(work_dir)
    candidate = work_dir / "candidate"
    module.copy_tree(source, candidate)
    module.remove_production_wrappers(candidate)
    assert not (candidate / "package-manifest.json").exists()
    assert (candidate / "library/base/seed.json").read_bytes() == b'{"seed":true}'
    module.verify_library_resources(source, candidate)


def test_append_payload_writes_the_existing_footer_contract(work_dir):
    module = load_module()
    setup = work_dir / "setup.exe"
    setup.write_bytes(b"MZ" + b"0" * 8190)
    payload = work_dir / "payload.zip"
    payload.write_bytes(b"PKpayload")
    destination = work_dir / "setup-with-payload.exe"
    module.append_payload(setup, payload, destination)
    offset, length = module.read_footer(destination)
    assert offset == setup.stat().st_size
    assert length == payload.stat().st_size
    with destination.open("rb") as stream:
        stream.seek(offset)
        assert stream.read(length) == payload.read_bytes()
