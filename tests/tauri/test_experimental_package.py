from __future__ import annotations

import hashlib
import importlib.util
import json
import py_compile
import shutil
import subprocess
import sys
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


def compile_unchecked_hash(source: Path, target: Path, optimize: int = 0) -> str:
    """Write a real hash-based, unchecked bytecode file and return its hash."""
    target.parent.mkdir(parents=True, exist_ok=True)
    py_compile.compile(
        str(source),
        cfile=str(target),
        doraise=True,
        optimize=optimize,
        invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH,
    )
    return hashlib.sha256(target.read_bytes()).hexdigest()


def imported_value(candidate: Path, module_name: str, optimize: bool = False) -> str:
    """Import in an isolated child that may read, but never write, bytecode."""
    code = (
        "import importlib, sys\n"
        "sys.path.insert(0, sys.argv[1])\n"
        "print(importlib.import_module(sys.argv[2]).VALUE)\n"
    )
    flags = ["-I", "-B"] + (["-O"] if optimize else [])
    result = subprocess.run(
        [sys.executable, *flags, "-c", code, str(candidate), module_name],
        cwd=str(candidate),
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        pytest.fail(f"child import failed for {module_name}:\n{result.stderr}")
    return result.stdout.strip()


def test_base_payload_requires_an_exact_manifest_set(work_dir):
    module = load_module()
    base = make_base(work_dir)
    module.verify_base_payload(base)
    write(base / "unexpected.txt", b"extra")
    with pytest.raises(ValueError, match="file set"):
        module.verify_base_payload(base)


def test_experimental_overlay_is_explicit_and_leaves_library_and_base_alone(work_dir):
    module = load_module()
    source, candidate = work_dir / 'source', work_dir / 'candidate'
    for name in module.EXPERIMENTAL_BACKEND_OVERLAY:
        write(source / name, b'new experimental code')
        write(candidate / name, b'release code')
    write(candidate / 'library/seed/keep', b'library unchanged')
    receipt = module.apply_backend_overlay(source, candidate)
    assert len(receipt['files']) == len(module.EXPERIMENTAL_BACKEND_OVERLAY)
    assert all(item['base_sha256'] != item['sha256'] for item in receipt['files'])
    assert (candidate / 'library/seed/keep').read_bytes() == b'library unchanged'
    assert all(not name.startswith('library/') for name in module.EXPERIMENTAL_BACKEND_OVERLAY)


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


def test_overlay_invalidates_stale_unchecked_hash_bytecode(work_dir):
    module = load_module()
    source, candidate = work_dir / "source", work_dir / "candidate"
    old_body = b'VALUE = "rc3-old"\n'
    new_body = b'VALUE = "rc4-new"\n'
    for name in module.EXPERIMENTAL_BACKEND_OVERLAY:
        write(source / name, new_body)
        write(candidate / name, old_body)
    write(candidate / "operon" / "__init__.py", b"")
    sibling = candidate / "operon" / "unrelated.py"
    write(sibling, b'VALUE = "sibling"\n')
    library = candidate / "library" / "base" / "seed.json"
    write(library, b'{"seed": true}\n')

    module_py = candidate / "operon" / "installation.py"
    cache_tag = sys.implementation.cache_tag
    legacy_pyc = module_py.with_suffix(".pyc")
    cache_dir = module_py.parent / "__pycache__"
    plain_pyc = cache_dir / f"installation.{cache_tag}.pyc"
    optimized_pyc = cache_dir / f"installation.{cache_tag}.opt-1.pyc"
    sibling_pyc = cache_dir / f"unrelated.{cache_tag}.pyc"
    stale_hashes = {
        legacy_pyc: compile_unchecked_hash(module_py, legacy_pyc),
        plain_pyc: compile_unchecked_hash(module_py, plain_pyc),
        optimized_pyc: compile_unchecked_hash(module_py, optimized_pyc, optimize=1),
        sibling_pyc: compile_unchecked_hash(sibling, sibling_pyc),
    }
    source_cache = source / "operon" / "__pycache__" / f"installation.{cache_tag}.pyc"
    compile_unchecked_hash(source / "operon" / "installation.py", source_cache)
    unaffected = [sibling, sibling_pyc, library, source_cache]
    unaffected_hashes = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in unaffected}

    # Reproduce the RC4 overlay state: new source in place, RC3 bytecode still cached.
    shutil.copyfile(source / "operon" / "installation.py", module_py)
    assert imported_value(candidate, "operon.installation") == "rc3-old"
    assert imported_value(candidate, "operon.installation", optimize=True) == "rc3-old"

    receipt = module.apply_backend_overlay(source, candidate)

    assert not legacy_pyc.exists()
    assert not plain_pyc.exists()
    assert not optimized_pyc.exists()
    assert imported_value(candidate, "operon.installation") == "rc4-new"
    assert imported_value(candidate, "operon.installation", optimize=True) == "rc4-new"
    assert {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in unaffected} == unaffected_hashes

    record = next(item for item in receipt["files"] if item["path"] == "operon/installation.py")
    recorded = {item["path"]: item["sha256"] for item in record["caches"]}
    expected = {
        path.relative_to(candidate).as_posix(): stale_hashes[path]
        for path in (legacy_pyc, plain_pyc, optimized_pyc)
    }
    assert recorded == expected


def test_overlay_refuses_reparse_bytecode_directory(work_dir):
    module = load_module()
    source, candidate = work_dir / "source", work_dir / "candidate"
    outside = work_dir / "outside"
    for name in module.EXPERIMENTAL_BACKEND_OVERLAY:
        write(source / name, b'VALUE = "new"\n')
        write(candidate / name, b'VALUE = "old"\n')
    write(outside / "installation.pyc", b"outside-bytes")
    cache_dir = candidate / "operon" / "__pycache__"
    try:
        cache_dir.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("directory symlinks are not permitted in this environment")

    with pytest.raises(ValueError, match="reparse"):
        module.apply_backend_overlay(source, candidate)
    assert (outside / "installation.pyc").read_bytes() == b"outside-bytes"


def test_overlay_refuses_reparse_bytecode_file(work_dir):
    module = load_module()
    source, candidate = work_dir / "source", work_dir / "candidate"
    outside = work_dir / "outside"
    for name in module.EXPERIMENTAL_BACKEND_OVERLAY:
        write(source / name, b'VALUE = "new"\n')
        write(candidate / name, b'VALUE = "old"\n')
    write(outside / "installation.pyc", b"outside-bytes")
    cache_dir = candidate / "operon" / "__pycache__"
    cache_dir.mkdir(parents=True)
    link = cache_dir / f"installation.{sys.implementation.cache_tag}.pyc"
    try:
        link.symlink_to(outside / "installation.pyc")
    except (OSError, NotImplementedError):
        pytest.skip("file symlinks are not permitted in this environment")

    with pytest.raises(ValueError, match="reparse"):
        module.apply_backend_overlay(source, candidate)
    assert (outside / "installation.pyc").read_bytes() == b"outside-bytes"
