"""Fail-closed gate for a built library bundle."""

from __future__ import annotations

import ast
import configparser
import json
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from operon_sdk.declarations import verify_archive
from operon_sdk.protocol import Descriptor, PackageDescriptor

from . import manifest
from .identity import file_sha256

PACKAGE_ROOT = Path(__file__).resolve().parent
ENTRY_SECTIONS = {"operator": "operon.operators", "reader": "operon.readers"}


def builder_import_violations(root: Path) -> list[str]:
    """Report imports of the application ``operon`` package in builder sources."""
    violations: list[str] = []
    for path in sorted(Path(root).rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "operon" or alias.name.startswith("operon."):
                        violations.append(f"{path}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom) and not node.level:
                module = node.module or ""
                if module == "operon" or module.startswith("operon."):
                    violations.append(f"{path}: from {module} import ...")
    return violations


def _wheel_entries(data: bytes, name: str) -> dict[str, bytes]:
    entries: dict[str, bytes] = {}
    with ZipFile(BytesIO(data)) as archive:
        for info in archive.infolist():
            if info.filename.endswith("/"):
                continue
            if info.filename in entries:
                raise manifest.BundleError(f"{name}: duplicate wheel entry {info.filename!r}")
            entries[info.filename] = archive.read(info.filename)
    return entries


def _ordered(descriptors: list[dict]) -> list[dict]:
    return sorted(descriptors, key=lambda descriptor: (descriptor["kind"], descriptor["id"]))


def _check_install_manifest(
    wheel_path: str,
    info: str,
    package: dict,
    descriptors: list[dict],
    entries: dict[str, bytes],
) -> None:
    """Require the install manifests that ``operon.install_targets.wheel_entries`` reads."""
    try:
        value = json.loads(entries[f"{info}/operon.json"])
        PackageDescriptor.model_validate(value)
    except (KeyError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise manifest.BundleError(f"{wheel_path}: missing or invalid operon.json") from error
    expected = {
        "protocol_version": 3,
        "name": package["name"],
        "version": package["version"],
        "title": None,
        "origin": "wheel",
        "descriptors": _ordered(descriptors),
    }
    if value != expected:
        raise manifest.BundleError(f"{wheel_path}: operon.json does not match library.json")

    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read_string(entries[f"{info}/entry_points.txt"].decode("utf-8"))
    except (KeyError, UnicodeDecodeError, configparser.Error) as error:
        raise manifest.BundleError(f"{wheel_path}: missing or invalid entry_points.txt") from error
    expected_groups = {section: [] for section in ENTRY_SECTIONS.values()}
    for descriptor in _ordered(descriptors):
        expected_groups[ENTRY_SECTIONS[descriptor["kind"]]].append(descriptor["id"])
    for section, identifiers in expected_groups.items():
        if section not in parser:
            raise manifest.BundleError(f"{wheel_path}: entry_points.txt lacks [{section}]")
        if sorted(parser[section]) != sorted(identifier.lower() for identifier in identifiers):
            raise manifest.BundleError(f"{wheel_path}: [{section}] does not match the descriptors")


def gate(dist: Path) -> list[str]:
    path = manifest.resolve_bundle(Path(dist))
    entries = manifest.read_entries(path)
    document, descriptors = manifest.verify_entries(entries)
    checks = ["bundle structure and SHA256SUMS"]

    violations = builder_import_violations(PACKAGE_ROOT)
    if violations:
        raise manifest.BundleError(
            "builder imports application code: " + "; ".join(violations)
        )
    checks.append("builder sources import no `operon` module")

    for descriptor in descriptors:
        try:
            Descriptor.model_validate(descriptor)
        except Exception as error:  # pydantic reports the failing field
            raise manifest.BundleError(
                f"{descriptor.get('id')!r}: invalid descriptor ({error})"
            ) from error
    checks.append("descriptors validate against the protocol schema")

    by_id = {descriptor["id"]: descriptor for descriptor in descriptors}
    for package in document["packages"]:
        name = package["name"]
        wheel_path = package["wheel"]
        data = entries[wheel_path]
        if file_sha256(data) != package["wheel_sha256"]:
            raise manifest.BundleError(f"{wheel_path}: wheel digest does not match library.json")

        wheel_entries = _wheel_entries(data, wheel_path)
        info = f"{manifest.distribution_name(name)}-{package['version']}.dist-info"
        try:
            identity = json.loads(wheel_entries[f"{info}/operon_identity.json"])
        except (KeyError, json.JSONDecodeError) as error:
            raise manifest.BundleError(
                f"{wheel_path}: missing or invalid operon_identity.json"
            ) from error
        expected_identity = {
            "package": name,
            "version": package["version"],
            "code_sha": package["code_sha"],
        }
        if identity != expected_identity:
            raise manifest.BundleError(
                f"{wheel_path}: operon_identity.json does not match library.json"
            )

        package_descriptors = _ordered(
            [by_id[identifier] for identifier in package["entry_points"]]
        )
        _check_install_manifest(wheel_path, info, package, package_descriptors, wheel_entries)

        module = name.replace("-", "_").replace(".", "_").lower()
        for descriptor in package_descriptors:
            entry_module = descriptor["entry_point"].split(":", 1)[0]
            if not entry_module.startswith(f"{module}."):
                raise manifest.BundleError(
                    f"{descriptor['id']}: entry point is outside the package module"
                )
            if descriptor["code_sha"] != package["code_sha"]:
                raise manifest.BundleError(
                    f"{descriptor['id']}: descriptor code_sha differs from package code_sha"
                )
            source = entry_module.replace(".", "/")
            if f"{source}.py" not in wheel_entries and f"{source}/__init__.py" not in wheel_entries:
                raise manifest.BundleError(
                    f"{descriptor['id']}: entry module is missing from {wheel_path}"
                )

        try:
            verify_archive(wheel_entries, package_descriptors)
        except ValueError as error:
            raise manifest.BundleError(f"{wheel_path}: verify_archive failed: {error}") from error
        checks.append(f"{name}: wheel digest, identity, entry points and archive verified")

    return checks