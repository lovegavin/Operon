#!/usr/bin/env python3
"""Build Operon Studio Experimental Setup from explicit, validated inputs.

The base 5.3.0 payload is read-only. This script never searches for a Python
interpreter, installs scientific dependencies, signs, publishes, or updates over
the network. It replaces only the production host/frontend wrappers with the
experimental host and frontend, invalidates bytecode cached for those explicit
Python overlays, writes a distinct experimental manifest, and appends the
payload to the experimental Setup with the existing footer format.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import zipfile

PRODUCT = "operon-studio-experimental"
CHANNEL = "experimental"
HOST_VERSION = "0.1.0"
MANAGEMENT_RELEASE = "5.3.0"
HOST_EXE = "operon-desktop-experimental.exe"
MANIFEST_NAME = "experimental-manifest.json"
FOOTER_MAGIC = b"OPERON-SETUP-V1"
PAYLOAD_ROOT = "Operon Studio/"
PRODUCTION_WRAPPERS = {
    "Operon Studio.exe",
    "operon-desktop.json",
    "START_HERE.txt",
    "operon.cmd",
    "package-manifest.json",
    "Operon_Setup.exe",
    "Operon_Uninstall.exe",
}
README = """Operon Studio Experimental
==========================

This is an independent experimental Tauri host installation. It is not the
production Operon Studio application.

- Management/backend payload: Operon Studio 5.3.0 (read-only input)
- Experimental host version: 0.1.0
- Product identifier: org.operon.studio.experimental
- The profile is retained by updates and uninstall.
- This package has no automatic updater and is not signed for publication.

Operator libraries are independent. If the input application payload has no
library, import a compatible existing .operon-library.zip through Add operators
before using library-based routes. Any libraries present in the input payload
are preserved unchanged. Prepare only the chosen route's execution dependencies.

Use the Setup normally, or run it with:
  --silent --install-dir <path> [--uninstall] [--result <path>]
"""


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def safe_relative(value: str) -> str:
    normalized = value.replace("\\", "/")
    pure = PurePosixPath(normalized)
    parts = normalized.split("/")
    if not normalized or pure.is_absolute() or any(part in ("", ".", "..") or ":" in part for part in parts):
        raise ValueError(f"Unsafe relative path: {value!r}")
    if any(part.endswith((" ", ".")) for part in parts):
        raise ValueError(f"Unsafe relative path segment: {value!r}")
    if any(re.fullmatch(r"(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?", part) for part in parts):
        raise ValueError(f"Reserved relative path: {value!r}")
    return pure.as_posix()


FILE_ATTRIBUTE_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


def is_reparse_point(path: Path) -> bool:
    """Return True for symlinks and Windows reparse points such as junctions."""
    if path.is_symlink():
        return True
    try:
        attributes = os.lstat(path).st_file_attributes
    except (OSError, AttributeError):
        return False
    return bool(attributes & FILE_ATTRIBUTE_REPARSE_POINT)


def reject_reparse(path: Path, description: str) -> None:
    if is_reparse_point(path):
        raise ValueError(f"Refusing symlink or reparse point in {description}: {path}")


def iter_files(root: Path):
    pending = [root]
    while pending:
        directory = pending.pop()
        reject_reparse(directory, "payload directory")
        for entry in sorted(directory.iterdir(), key=lambda item: item.name):
            reject_reparse(entry, "payload")
            if entry.is_dir():
                pending.append(entry)
            elif entry.is_file():
                yield entry


def verify_base_payload(base: Path) -> dict:
    base = base.resolve()
    manifest_path = base / "package-manifest.json"
    if not manifest_path.is_file():
        raise ValueError("Base payload is missing package-manifest.json.")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Base package-manifest.json is invalid: {error}") from error
    if manifest.get("version") != MANAGEMENT_RELEASE:
        raise ValueError(f"Base payload is not {MANAGEMENT_RELEASE}: {manifest.get('version')!r}")
    if manifest.get("python_bundled") is not True:
        raise ValueError("Base payload must include its private management Python runtime.")
    declared: dict[str, tuple[int, str]] = {}
    for item in manifest.get("files", []):
        path = safe_relative(str(item.get("path", "")))
        if path in declared:
            raise ValueError(f"Base manifest repeats a path: {path}")
        declared[path] = (int(item.get("bytes", -1)), str(item.get("sha256", "")))
    actual: dict[str, tuple[int, str]] = {}
    for file in iter_files(base):
        relative = file.relative_to(base).as_posix()
        if relative == "package-manifest.json":
            continue
        actual[relative] = (file.stat().st_size, digest(file))
    if set(actual) != set(declared):
        missing = sorted(set(declared) - set(actual))[:5]
        extra = sorted(set(actual) - set(declared))[:5]
        raise ValueError(f"Base payload file set differs from its manifest (missing={missing}, extra={extra}).")
    for path, (size, sha) in declared.items():
        actual_size, actual_sha = actual[path]
        if actual_size != size or actual_sha != sha:
            raise ValueError(f"Base payload file hash mismatch: {path}")
    if "runtime/python/python.exe" not in declared or "scripts/desktop_server.py" not in declared:
        raise ValueError("Base payload does not contain the reusable management runtime.")
    return manifest


def copy_tree(source: Path, destination: Path) -> None:
    for file in iter_files(source):
        target = destination / file.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(file, target)


def remove_production_wrappers(candidate: Path) -> None:
    reject_reparse(candidate, "candidate payload")
    for name in PRODUCTION_WRAPPERS:
        path = candidate / name
        reject_reparse(path, "candidate payload")
        if path.is_file():
            path.unlink()
    for link in candidate.glob("*.lnk"):
        reject_reparse(link, "candidate payload")
        link.unlink()


def verify_library_resources(base: Path, candidate: Path) -> None:
    for file in iter_files(base):
        relative = file.relative_to(base).as_posix()
        if relative.startswith("library/"):
            target = candidate / relative
            if not target.is_file() or digest(target) != digest(file):
                raise ValueError(f"Bundled library resource was not preserved: {relative}")


EXPERIMENTAL_BACKEND_OVERLAY = (
    'operon/installation.py', 'operon/processes.py', 'operon/process_paths.py',
    'operon/tool_runner.py', 'scripts/verify_release_agent.py',
    'operon/process_path_scopes.py', 'operon/execution/unit_executor.py',
    'operon/export/collector.py', 'operon/export/automatic.py', 'operon/canvas_plans.py',
    'operon/python_paths.py', 'operon/bytecode.py', 'operon/runtime_bootstrap.py',
    'operon/environment_store/canvas.py', 'operon/environment_store/acquisition.py',
    'operon/environment_store/python_builder.py', 'operon/execution/adapters/command.py',
    'operon/environment_store/builders.py',
    'operon/export/service.py', 'operon/env_worker.py',
)


def is_module_bytecode_name(name: str, stem: str) -> bool:
    """Match ``<module>.<tag>[.opt-*].pyc`` without matching another module."""
    prefix = stem + '.'
    return name.startswith(prefix) and name.endswith('.pyc') and len(name) > len(prefix) + 4


def checked_candidate_path(candidate: Path, path: Path, description: str) -> Path:
    """Require a path to stay inside the candidate and contain no reparse points."""
    reject_reparse(candidate, description)
    try:
        relative = path.relative_to(candidate)
    except ValueError as error:
        raise ValueError(f'Refusing bytecode outside the candidate payload: {path}') from error
    current = candidate
    for part in relative.parts:
        current = current / part
        if current.exists() or current.is_symlink():
            reject_reparse(current, description)
    try:
        path.resolve().relative_to(candidate.resolve())
    except (OSError, ValueError) as error:
        raise ValueError(f'Refusing bytecode outside the candidate payload: {path}') from error
    return path


def remove_stale_module_bytecode(candidate: Path, module: Path) -> list[dict]:
    """Remove this module's candidate-only bytecode, recording path and hash."""
    removed: list[dict] = []
    legacy = module.with_suffix('.pyc')
    if legacy.exists() or legacy.is_symlink():
        checked_candidate_path(candidate, legacy, 'candidate bytecode')
        if legacy.is_dir():
            raise ValueError(f'Candidate bytecode path is a directory: {legacy}')
        removed.append({'path': legacy.relative_to(candidate).as_posix(), 'sha256': digest(legacy)})
        legacy.unlink()
    cache = module.parent / '__pycache__'
    if not (cache.exists() or cache.is_symlink()):
        return removed
    checked_candidate_path(candidate, cache, 'candidate bytecode cache')
    if not cache.is_dir():
        return removed
    for entry in sorted(cache.iterdir(), key=lambda item: item.name):
        if not is_module_bytecode_name(entry.name, module.stem):
            continue
        checked_candidate_path(candidate, entry, 'candidate bytecode')
        if entry.is_dir():
            raise ValueError(f'Candidate bytecode path is a directory: {entry}')
        removed.append({'path': entry.relative_to(candidate).as_posix(), 'sha256': digest(entry)})
        entry.unlink()
    return removed


def apply_backend_overlay(source: Path, candidate: Path) -> dict:
    """Ship a small, audited experimental delta without mutating the release base."""
    records = []
    for name in EXPERIMENTAL_BACKEND_OVERLAY:
        origin, target = source / name, candidate / name
        reject_reparse(origin, 'experimental backend overlay')
        if not origin.is_file():
            raise ValueError(f'Missing experimental backend overlay: {name}')
        checked_candidate_path(candidate, target, 'experimental backend target')
        before = digest(target) if target.is_file() else None
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origin, target)
        caches = remove_stale_module_bytecode(candidate, target)
        records.append({'path': name, 'base_sha256': before, 'sha256': digest(target), 'caches': caches})
    receipt = {'format': 'operon.experimental-backend-overlay', 'version': 1, 'files': records}
    (candidate / 'experimental-backend-overlay.json').write_text(
        json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    return receipt


def payload_id(manifest: dict) -> str:
    lines = [
        manifest["product"], manifest["channel"], manifest["build_id"],
        manifest["host_version"], manifest["management_release"],
        manifest["source_commit"], "true" if manifest["source_dirty"] else "false",
    ]
    for key in sorted(manifest["locks"]):
        lines.append(f"{key}={manifest['locks'][key]}")
    for item in sorted(manifest["files"], key=lambda value: value["path"]):
        lines.append(f"{item['path']}\t{item['bytes']}\t{item['sha256']}")
    return hashlib.sha256(("\n".join(lines) + "\n").encode("utf-8")).hexdigest()


def build_manifest(candidate: Path, build_id: str, source_commit: str, source_dirty: bool,
                   frontend_lock: Path | None, cargo_lock: Path, base_manifest: Path) -> dict:
    files = []
    for file in sorted(iter_files(candidate), key=lambda value: value.relative_to(candidate).as_posix()):
        relative = file.relative_to(candidate).as_posix()
        if relative == MANIFEST_NAME:
            continue
        files.append({"path": relative, "bytes": file.stat().st_size, "sha256": digest(file)})
    if not files:
        raise ValueError("Candidate payload is empty.")
    locks = {
        "cargo_lock_sha256": digest(cargo_lock),
        "frontend_lock_sha256": digest(frontend_lock) if frontend_lock else "0" * 64,
        "base_manifest_sha256": digest(base_manifest),
    }
    runtime_receipt = candidate / "runtime/python/operon-runtime.json"
    if runtime_receipt.is_file():
        locks["runtime_receipt_sha256"] = digest(runtime_receipt)
    groups = {"management": 0, "frontend": 0, "host": 0}
    for item in files:
        path = item["path"]
        if path == HOST_EXE:
            groups["host"] += item["bytes"]
        elif path.startswith("frontend/"):
            groups["frontend"] += item["bytes"]
        else:
            groups["management"] += item["bytes"]
    manifest = {
        "schema": 1,
        "product": PRODUCT,
        "channel": CHANNEL,
        "build_id": build_id,
        "host_version": HOST_VERSION,
        "management_release": MANAGEMENT_RELEASE,
        "source_commit": source_commit,
        "source_dirty": bool(source_dirty),
        "locks": locks,
        "components": [{"id": key, "bytes": value} for key, value in groups.items()],
        "files": files,
    }
    manifest["payload_id"] = payload_id(manifest)
    return manifest


def write_zip(candidate: Path, zip_path: Path) -> tuple[int, int]:
    count = 0
    unpacked = 0
    with zipfile.ZipFile(zip_path, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
        for file in sorted(iter_files(candidate), key=lambda value: value.relative_to(candidate).as_posix()):
            relative = file.relative_to(candidate).as_posix()
            entry = zipfile.ZipInfo(PAYLOAD_ROOT + relative, date_time=(2000, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            with file.open("rb") as source, archive.open(entry, "w") as target:
                shutil.copyfileobj(source, target, 1024 * 1024)
            count += 1
            unpacked += file.stat().st_size
    with zipfile.ZipFile(zip_path) as archive:
        if archive.testzip() is not None:
            raise ValueError("Generated payload archive failed its integrity check.")
    return count, unpacked


def append_payload(setup: Path, payload: Path, destination: Path) -> None:
    setup_size = setup.stat().st_size
    payload_size = payload.stat().st_size
    if setup_size < 4096 or payload_size <= 0:
        raise ValueError("Setup or payload is empty.")
    with destination.open("xb") as output:
        with setup.open("rb") as stream:
            shutil.copyfileobj(stream, output)
        offset = output.tell()
        with payload.open("rb") as stream:
            shutil.copyfileobj(stream, output)
        output.write(struct.pack("<16sqq", FOOTER_MAGIC, offset, payload_size))
    if read_footer(destination) != (offset, payload_size):
        raise ValueError("Written Setup footer is inconsistent.")


def read_footer(setup: Path) -> tuple[int, int]:
    size = setup.stat().st_size
    if size < 32:
        raise ValueError("Setup is too small to contain a footer.")
    with setup.open("rb") as stream:
        stream.seek(-32, os.SEEK_END)
        footer = stream.read(32)
    if footer[:16] != FOOTER_MAGIC.ljust(16, b"\0"):
        raise ValueError("Setup footer magic is missing.")
    offset, length = struct.unpack("<qq", footer[16:32])
    if offset < 64 or length <= 0 or offset + length + 32 != size:
        raise ValueError("Setup footer bounds are invalid.")
    return offset, length


def source_identity(root: Path, supplied_commit: str | None, supplied_dirty: bool | None) -> tuple[str, bool]:
    if supplied_commit is not None:
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,80}", supplied_commit):
            raise ValueError("Invalid --source-commit.")
        if supplied_dirty is not None:
            return supplied_commit, supplied_dirty
        try:
            dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True,
                                                 stderr=subprocess.DEVNULL).strip())
        except (OSError, subprocess.CalledProcessError):
            dirty = True
        return supplied_commit, dirty
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True,
                                         stderr=subprocess.DEVNULL).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True,
                                             stderr=subprocess.DEVNULL).strip())
        return commit, dirty
    except (OSError, subprocess.CalledProcessError):
        return "unknown", True


def publish(dotnet: str, project: Path, output: Path, obj: Path, extra: list[str]) -> Path:
    obj.mkdir(parents=True, exist_ok=True)
    command = [dotnet, "publish", str(project), "-c", "Release", "-r", "win-x64",
               "--self-contained", "true", "-p:PublishSingleFile=true", "-p:DebugType=None",
               "-p:BaseIntermediateOutputPath=" + str(obj) + os.sep,
               "-o", str(output), *extra]
    subprocess.run(command, check=True)
    candidates = sorted(output.glob("*.exe"))
    if len(candidates) != 1:
        raise RuntimeError(f"Expected one published executable in {output}, found {[item.name for item in candidates]}")
    return candidates[0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-payload", type=Path, required=True,
                        help="Validated Operon Studio 5.3.0 Windows payload directory")
    parser.add_argument("--host", type=Path, required=True, help="Experimental host release executable")
    parser.add_argument("--frontend", type=Path, required=True, help="Experimental frontend dist directory")
    parser.add_argument("--output", type=Path, required=True, help="New output directory")
    parser.add_argument("--build-id", default="tauri-0.1.0-rc1")
    parser.add_argument("--source-commit")
    parser.add_argument("--source-dirty", choices=("true", "false"))
    parser.add_argument("--frontend-lock", type=Path)
    parser.add_argument("--dotnet", default="dotnet")
    parser.add_argument("--installer-project", type=Path,
                        default=Path(__file__).resolve().parents[1] / "desktop-tauri/installer/OperonExperimentalInstaller.csproj")
    args = parser.parse_args(argv)

    if not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", args.build_id):
        parser.error("--build-id must contain only letters, digits, dot, underscore or dash.")
    base = args.base_payload.resolve()
    host = args.host.resolve()
    frontend = args.frontend.resolve()
    output = args.output.resolve()
    root = Path(__file__).resolve().parents[1]
    cargo_lock = root / "desktop-tauri/Cargo.lock"
    project = args.installer_project.resolve()
    if not host.is_file() or host.read_bytes()[:2] != b"MZ":
        parser.error("--host must be a Windows executable.")
    if not (frontend / "index.html").is_file() or not (frontend / "assets").is_dir():
        parser.error("--frontend must be a built frontend dist directory.")
    if not cargo_lock.is_file() or not project.is_file():
        parser.error("The experimental Cargo.lock or installer project is missing.")
    frontend_lock = args.frontend_lock or (frontend.parent / "package-lock.json")
    if not frontend_lock.is_file():
        parser.error("A frontend package-lock.json is required; pass --frontend-lock.")
    if output.exists() and any(output.iterdir()):
        parser.error(f"Output directory is not empty: {output}")

    verify_base_payload(base)
    output.mkdir(parents=True, exist_ok=True)
    commit, dirty = source_identity(root, args.source_commit, None if args.source_dirty is None else args.source_dirty == "true")
    work = Path(tempfile.mkdtemp(prefix="operon-experimental-package-"))
    try:
        candidate = work / "candidate"
        copy_tree(base, candidate)
        remove_production_wrappers(candidate)
        verify_library_resources(base, candidate)
        apply_backend_overlay(root, candidate)
        frontend_target = candidate / "frontend"
        reject_reparse(frontend_target, "candidate payload")
        shutil.rmtree(frontend_target, ignore_errors=True)
        copy_tree(frontend, frontend_target)
        shutil.copyfile(host, candidate / HOST_EXE)
        (candidate / "EXPERIMENTAL_README.txt").write_text(README, encoding="utf-8")

        manifest = build_manifest(candidate, args.build_id, commit, dirty, frontend_lock, cargo_lock,
                                  base / "package-manifest.json")
        manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
        (candidate / MANIFEST_NAME).write_bytes(manifest_bytes)
        archive = work / "payload.zip"
        count, unpacked = write_zip(candidate, archive)
        spec = {
            "version": HOST_VERSION,
            "sha256": digest(archive),
            "bytes": archive.stat().st_size,
            "unpackedBytes": unpacked,
            "files": count,
        }
        spec_path = work / "payload.json"
        spec_path.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")

        stub_dir = work / "stub"
        stub_obj = work / f"obj-{args.build_id}-stub"
        stub = publish(args.dotnet, project, stub_dir, stub_obj, ["-p:UninstallerStub=true"])
        setup_dir = work / "setup"
        setup_obj = work / f"obj-{args.build_id}-setup"
        setup = publish(args.dotnet, project, setup_dir, setup_obj,
                        [f"-p:ExperimentalManifest={candidate / MANIFEST_NAME}",
                         f"-p:PayloadManifest={spec_path}",
                         f"-p:UninstallerStubPath={stub}"])

        setup_name = "Operon_Experimental_Setup.exe"
        uninstall_name = "Operon_Experimental_Uninstall.exe"
        append_payload(setup, archive, output / setup_name)
        shutil.copyfile(stub, output / uninstall_name)
        (output / MANIFEST_NAME).write_bytes(manifest_bytes)
        sums = []
        for name in (setup_name, uninstall_name):
            sums.append(f"{digest(output / name)}  {name}\n")
        (output / "SHA256SUMS.txt").write_text("".join(sums), encoding="ascii")
        components = {
            "build_id": args.build_id,
            "payload_id": manifest["payload_id"],
            "components": manifest["components"] + [
                {"id": "setup", "bytes": (output / setup_name).stat().st_size},
                {"id": "uninstaller", "bytes": (output / uninstall_name).stat().st_size},
            ],
            "payload": spec,
        }
        (output / "components.json").write_text(json.dumps(components, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"setup": str(output / setup_name), "payload_id": manifest["payload_id"],
                          "files": count, "unpackedBytes": unpacked}, indent=2))
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
