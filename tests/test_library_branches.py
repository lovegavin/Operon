"""Equal-status named libraries coexist, conflict, and uninstall independently."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import zipfile

import pytest

import operon
from operon.library_install import (
    LibraryConflict,
    install_library,
    libraries_view,
    uninstall_library,
)
from operon.plugins import PluginManager
from operon_sdk.declarations import declaration_hash


def _zip(entries: dict[str, bytes]) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return stream.getvalue()


def _library(directory: Path, *, name: str, module: str, operator: str,
             package: str, version: str = "0.1.0", library_version: str = "0.0.0") -> Path:
    source = (
        '"""Synthetic operator used only by branch-coexistence tests."""\n\n\n'
        f"class {operator.title().replace('_', '')}Step:\n"
        "    def run(self, inputs, parameters):\n"
        "        return inputs\n"
    ).encode("utf-8")
    parameters = {"type": "object", "properties": {}, "additionalProperties": False}
    filename = f"{module}.py"
    descriptor = {
        "protocol_version": 3,
        "id": operator,
        "version": version,
        "kind": "operator",
        "entry_point": f"{module}:{operator.title().replace('_', '')}Step",
        "code_sha": "",
        "declaration_sha": "",
        "title": operator.replace("_", " ").title(),
        "description": "Synthetic operator used by branch tests.",
        "category": "Test",
        "parameters_schema": parameters,
        "inputs_arity": 1,
        "outputs": ["result"],
        "output_parameter": None,
        "contracts": {
            "inputs": [{"schema": {"type": "object"}}],
            "output": {"mode": "declare", "schema": {"type": "object"}},
        },
        "resources": {"memory_modes": ["memory"]},
    }
    digest = hashlib.sha256()
    digest.update(filename.encode("utf-8") + b"\0")
    digest.update(source)
    descriptor["code_sha"] = digest.hexdigest()
    descriptor["declaration_sha"] = declaration_hash(descriptor)
    info = f"{package.replace(chr(45), chr(95))}-{version}.dist-info"
    wheel_files = {
        filename: source,
        f"{module}.parameters.json": (json.dumps(parameters, indent=2) + "\n").encode("utf-8"),
        f"{info}/METADATA": (
            f"Metadata-Version: 2.1\nName: {package}\nVersion: {version}\n"
            "Summary: branch test\nRequires-Python: >=3.10\n"
        ).encode("utf-8"),
        f"{info}/WHEEL": b"Wheel-Version: 1.0\nGenerator: tests\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        f"{info}/operon.json": json.dumps(
            {"protocol_version": 3, "name": package, "version": version, "descriptors": [descriptor]},
            indent=2,
        ).encode("utf-8"),
    }
    record = [
        f"{entry},sha256={hashlib.sha256(content).hexdigest()},{len(content)}"
        for entry, content in wheel_files.items()
    ]
    record.append(f"{info}/RECORD,,")
    wheel_files[f"{info}/RECORD"] = ("\n".join(record) + "\n").encode("utf-8")
    wheel = _zip(wheel_files)
    wheel_name = f"{package.replace('-', '_')}-{version}-py3-none-any.whl"
    document = {
        "format": "operon.library",
        "library_version": library_version,
        "bundle_format": 1,
        "operator_protocol": {"version": 3, "revision": "3.7"},
        "minimum_application": operon.__version__,
        "builder": {"name": "tests", "version": "1.0.0"},
        "packages": [{
            "name": package,
            "version": version,
            "wheel": f"wheels/{wheel_name}",
            "wheel_sha256": hashlib.sha256(wheel).hexdigest(),
            "code_sha": descriptor["code_sha"],
            "entry_points": {operator: descriptor["entry_point"]},
        }],
    }
    entries = {
        "library.json": json.dumps(document, indent=2).encode("utf-8"),
        f"wheels/{wheel_name}": wheel,
    }
    entries["SHA256SUMS"] = "".join(
        f"{hashlib.sha256(content).hexdigest()}  {entry}\n" for entry, content in entries.items()
    ).encode("utf-8")
    target = directory / f"operon-library-{library_version}-{name}.operon-library.zip"
    target.write_bytes(_zip(entries))
    return target


def _manager(tmp_path: Path) -> PluginManager:
    return PluginManager(tmp_path / "data")


def test_two_libraries_coexist_with_metadata(tmp_path):
    manager = _manager(tmp_path)
    main = _library(tmp_path, name="main-lib", module="alpha_step", operator="alpha_scale",
                    package="operon-alpha")
    fork = _library(tmp_path, name="fork-lib", module="beta_step", operator="beta_scale",
                    package="operon-beta", version="0.2.0", library_version="0.2.0")
    install_library(manager, main, name="main")
    result = install_library(manager, fork, name="fork-v0.0.0")
    assert result["library"] == "fork-v0.0.0"
    assert result["libraries"] == ["fork-v0.0.0", "main"]
    view = libraries_view(manager)
    assert view["count"] == 2
    records = {record["name"]: record for record in view["libraries"]}
    assert set(records) == {"main", "fork-v0.0.0"}
    assert records["main"]["operators"] == 1
    library_root = Path(manager.directory) / "libraries"
    assert (library_root / "main" / "version.json").is_file()
    assert (library_root / "main" / "archive.zip").is_file()
    operator_dir = Path(manager.directory) / "operators"
    index = json.loads((operator_dir / "index.json").read_text())
    assert {"alpha_scale", "beta_scale"} <= set(index)
    labels = {
        json.loads((operator_dir / index[key]).read_text())["library"]
        for key in ("alpha_scale", "beta_scale")
    }
    assert labels == {"main", "fork-v0.0.0"}
    state = manager.state()
    by_id = {item["id"]: item for item in state["descriptors"]}
    assert by_id["alpha_scale"]["library"] == "main"
    assert by_id["beta_scale"]["library"] == "fork-v0.0.0"


def test_duplicate_operator_id_is_rejected(tmp_path):
    manager = _manager(tmp_path)
    base = _library(tmp_path, name="one", module="alpha_step", operator="alpha_scale",
                    package="operon-alpha")
    clash = _library(tmp_path, name="two", module="beta_step", operator="alpha_scale",
                     package="operon-beta")
    install_library(manager, base, name="main")
    with pytest.raises(LibraryConflict) as caught:
        install_library(manager, clash, name="fork")
    assert any(item["kind"] == "identifier" and item["id"] == "alpha_scale"
               for item in caught.value.conflicts)
    assert libraries_view(manager)["count"] == 1


def test_duplicate_package_name_is_rejected(tmp_path):
    manager = _manager(tmp_path)
    base = _library(tmp_path, name="one", module="alpha_step", operator="alpha_scale",
                    package="operon-alpha")
    clash = _library(tmp_path, name="two", module="alpha_step", operator="beta_scale",
                     package="operon-alpha")
    install_library(manager, base, name="main")
    with pytest.raises(LibraryConflict) as caught:
        install_library(manager, clash, name="fork")
    kinds = {(item["kind"], item["id"]) for item in caught.value.conflicts}
    assert ("package", "operon-alpha") in kinds
    assert ("module", "alpha_step") in kinds


def test_uninstall_keeps_other_library(tmp_path):
    manager = _manager(tmp_path)
    main = _library(tmp_path, name="main-lib", module="alpha_step", operator="alpha_scale",
                    package="operon-alpha")
    fork = _library(tmp_path, name="fork-lib", module="beta_step", operator="beta_scale",
                    package="operon-beta")
    install_library(manager, main, name="main")
    install_library(manager, fork, name="fork")
    result = uninstall_library(manager, "main")
    assert result["removed"] == "main"
    view = libraries_view(manager)
    assert [record["name"] for record in view["libraries"]] == ["fork"]
    state = manager.state()
    assert [item["id"] for item in state["descriptors"] if item.get("library")] == ["beta_scale"]
    assert set(state["libraries"]) == {"fork"}
    assert not (Path(state["_runtime_root"]) / "libraries" / "main" / "library.json").exists()
