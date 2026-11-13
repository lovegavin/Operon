"""Bundle manifest assembly and structural verification."""

from __future__ import annotations

import json
import re
from collections import Counter
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from .identity import file_sha256
from .wheel import distribution_name, wheel_filename

BUILDER_NAME = "operon-library-builder"
BUILDER_VERSION = "1.0.0"
LIBRARY_FORMAT = "operon.library"
BUNDLE_FORMAT = 1
PROTOCOL_VERSION = 3
PROTOCOL_REVISION = "3.7"
REQUIRED_FILES = (
    "library.json",
    "descriptors.json",
    "environments.json",
    "SHA256SUMS",
    "docs/README.md",
)
LIBRARY_KEYS = {
    "format",
    "bundle_format",
    "library_version",
    "operator_protocol",
    "minimum_application",
    "builder",
    "packages",
    "descriptor_count",
    "operator_count",
    "reader_count",
}
PACKAGE_KEYS = {
    "name",
    "version",
    "wheel",
    "wheel_sha256",
    "code_sha",
    "entry_points",
    "kind_counts",
}
VERSION = re.compile(r"^\d+\.\d+\.\d+$")
SHA256 = re.compile(r"^[a-f0-9]{64}$")


class BundleError(ValueError):
    """Raised when a bundle violates the library format."""


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def library_document(
    *,
    version: str,
    minimum_application: str,
    packages: list[dict[str, Any]],
    descriptor_count: int,
    operator_count: int,
    reader_count: int,
) -> dict[str, Any]:
    return {
        "format": LIBRARY_FORMAT,
        "bundle_format": BUNDLE_FORMAT,
        "library_version": version,
        "operator_protocol": {"version": PROTOCOL_VERSION, "revision": PROTOCOL_REVISION},
        "minimum_application": minimum_application,
        "builder": {"name": BUILDER_NAME, "version": BUILDER_VERSION},
        "packages": sorted(packages, key=lambda package: package["name"]),
        "descriptor_count": descriptor_count,
        "operator_count": operator_count,
        "reader_count": reader_count,
    }


def package_record(
    *,
    name: str,
    version: str,
    wheel: str,
    wheel_sha256: str,
    code_sha: str,
    descriptors: list[dict[str, Any]],
) -> dict[str, Any]:
    ordered = sorted(descriptors, key=lambda descriptor: (descriptor["kind"], descriptor["id"]))
    counts = Counter(descriptor["kind"] for descriptor in ordered)
    return {
        "name": name,
        "version": version,
        "wheel": wheel,
        "wheel_sha256": wheel_sha256,
        "code_sha": code_sha,
        "entry_points": {
            descriptor["id"]: descriptor["entry_point"] for descriptor in ordered
        },
        "kind_counts": {
            "operator": counts.get("operator", 0),
            "reader": counts.get("reader", 0),
        },
    }


def readme(document: dict[str, Any], packages: list[dict[str, Any]]) -> str:
    lines = [
        "# Operon library bundle",
        "",
        f"Library version `{document['library_version']}` for Operon "
        f"`>={document['minimum_application']}`.",
        "",
        "Every wheel is pure Python and platform independent; this is a single",
        "universal bundle with no per-OS variants.",
        "",
        f"- Operator protocol: {document['operator_protocol']['version']} "
        f"revision {document['operator_protocol']['revision']}",
        f"- Descriptors: {document['descriptor_count']} "
        f"({document['operator_count']} operators, {document['reader_count']} readers)",
        f"- Packages: {len(packages)}",
        "",
        "| Package | Version | Operators | Readers | Wheel |",
        "| --- | --- | --- | --- | --- |",
    ]
    for package in packages:
        lines.append(
            f"| {package['name']} | {package['version']} | "
            f"{package['kind_counts']['operator']} | {package['kind_counts']['reader']} | "
            f"`{package['wheel']}` |"
        )
    lines.extend(
        [
            "",
            "## Verifying a bundle",
            "",
            "`SHA256SUMS` lists every entry except itself. `code_sha` identifies the",
            "Python sources of a package; `wheel_sha256` only guards transport.",
            "",
        ]
    )
    return "\n".join(lines)


def sha256sums(entries: dict[str, bytes]) -> bytes:
    lines = [
        f"{file_sha256(entries[name])}  {name}\n" for name in sorted(entries)
    ]
    return "".join(lines).encode("utf-8")


def bundle_entries(
    *,
    document: dict[str, Any],
    descriptors: list[dict[str, Any]],
    environments: bytes,
    readme_text: str,
    wheels: dict[str, bytes],
) -> dict[str, bytes]:
    entries: dict[str, bytes] = {
        "library.json": json_bytes(document),
        "descriptors.json": json_bytes(descriptors),
        "environments.json": environments,
        "docs/README.md": readme_text.encode("utf-8"),
    }
    for name, data in wheels.items():
        entries[f"wheels/{name}"] = data
    entries["SHA256SUMS"] = sha256sums(entries)
    return entries


def write_bundle(entries: dict[str, bytes], path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        for name in sorted(entries):
            info = ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, entries[name])
    return path


def resolve_bundle(path: Path) -> Path:
    path = Path(path)
    if path.is_file():
        return path
    if not path.is_dir():
        raise BundleError(f"{path}: no such bundle or directory")
    candidates = sorted(path.glob("operon-library-*.zip"))
    if len(candidates) != 1:
        raise BundleError(
            f"{path}: expected exactly one operon-library-*.zip, found {len(candidates)}"
        )
    return candidates[0]


def read_entries(path: Path) -> dict[str, bytes]:
    entries: dict[str, bytes] = {}
    with ZipFile(path) as archive:
        for info in archive.infolist():
            name = info.filename
            if name.endswith("/"):
                continue
            posix = PurePosixPath(name)
            if posix.is_absolute() or ".." in posix.parts:
                raise BundleError(f"{path}: unsafe entry {name!r}")
            if name in entries:
                raise BundleError(f"{path}: duplicate entry {name!r}")
            entries[name] = archive.read(name)
    return entries


def _json_object(entries: dict[str, bytes], name: str) -> Any:
    try:
        return json.loads(entries[name].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BundleError(f"{name}: invalid JSON ({error})") from error


def verify_entries(entries: dict[str, bytes]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    missing = [name for name in REQUIRED_FILES if name not in entries]
    if missing:
        raise BundleError(f"bundle is missing {', '.join(missing)}")

    document = _json_object(entries, "library.json")
    if not isinstance(document, dict) or set(document) != LIBRARY_KEYS:
        raise BundleError("library.json: unexpected keys")
    if document["format"] != LIBRARY_FORMAT:
        raise BundleError(f"library.json: format must be {LIBRARY_FORMAT!r}")
    if document["bundle_format"] != BUNDLE_FORMAT:
        raise BundleError(f"library.json: bundle_format must be {BUNDLE_FORMAT}")
    if not isinstance(document["library_version"], str) or not VERSION.match(document["library_version"]):
        raise BundleError("library.json: invalid library_version")
    protocol = document["operator_protocol"]
    if protocol != {"version": PROTOCOL_VERSION, "revision": PROTOCOL_REVISION}:
        raise BundleError("library.json: unsupported operator_protocol")
    if not isinstance(document["minimum_application"], str) or not VERSION.match(
        document["minimum_application"]
    ):
        raise BundleError("library.json: invalid minimum_application")
    builder = document["builder"]
    if not isinstance(builder, dict) or set(builder) != {"name", "version"}:
        raise BundleError("library.json: invalid builder record")

    packages = document["packages"]
    if not isinstance(packages, list) or not packages:
        raise BundleError("library.json: packages must be a non-empty list")

    descriptors = _json_object(entries, "descriptors.json")
    if not isinstance(descriptors, list):
        raise BundleError("descriptors.json: expected a list")
    if descriptors != sorted(descriptors, key=lambda item: (item.get("kind", ""), item.get("id", ""))):
        raise BundleError("descriptors.json: entries are not sorted by kind, id")

    by_id: dict[str, dict[str, Any]] = {}
    for descriptor in descriptors:
        if not isinstance(descriptor, dict):
            raise BundleError("descriptors.json: every entry must be an object")
        identifier = descriptor.get("id")
        if not isinstance(identifier, str) or not identifier:
            raise BundleError("descriptors.json: entry without id")
        if identifier in by_id:
            raise BundleError(f"descriptors.json: duplicate descriptor {identifier!r}")
        if descriptor.get("kind") not in {"operator", "reader"}:
            raise BundleError(f"descriptors.json: {identifier!r} has invalid kind")
        code_sha = descriptor.get("code_sha")
        if not isinstance(code_sha, str) or not SHA256.match(code_sha):
            raise BundleError(f"descriptors.json: {identifier!r} has invalid code_sha")
        declaration_sha = descriptor.get("declaration_sha")
        if not isinstance(declaration_sha, str) or not SHA256.match(declaration_sha):
            raise BundleError(f"descriptors.json: {identifier!r} has invalid declaration_sha")
        entry_point = descriptor.get("entry_point")
        if not isinstance(entry_point, str) or ":" not in entry_point:
            raise BundleError(f"descriptors.json: {identifier!r} has no entry point")
        by_id[identifier] = descriptor

    covered: set[str] = set()
    for package in packages:
        _verify_package(package, entries, by_id)
        covered.update(package["entry_points"])
    if covered != set(by_id):
        missing_ids = sorted(set(by_id) - covered)
        extra_ids = sorted(covered - set(by_id))
        raise BundleError(
            f"library.json: package entry points do not match descriptors "
            f"(missing {missing_ids[:5]}, unknown {extra_ids[:5]})"
        )

    counts = Counter(descriptor["kind"] for descriptor in descriptors)
    expected = {
        "descriptor_count": len(descriptors),
        "operator_count": counts.get("operator", 0),
        "reader_count": counts.get("reader", 0),
    }
    for key, value in expected.items():
        if document[key] != value:
            raise BundleError(f"library.json: {key} is {document[key]!r}, expected {value}")

    _verify_checksums(entries)
    environments = _json_object(entries, "environments.json")
    if not isinstance(environments, dict) or not isinstance(environments.get("environments"), dict):
        raise BundleError("environments.json: expected an 'environments' object")
    return document, descriptors


def _verify_package(
    package: Any,
    entries: dict[str, bytes],
    by_id: dict[str, dict[str, Any]],
) -> None:
    if not isinstance(package, dict) or set(package) != PACKAGE_KEYS:
        raise BundleError("library.json: unexpected package keys")
    name = package["name"]
    if not isinstance(name, str) or not name:
        raise BundleError("library.json: package without name")
    module = name.replace("-", "_").replace(".", "_").lower()
    version = package["version"]
    if not isinstance(version, str) or not VERSION.match(version):
        raise BundleError(f"library.json: {name} has invalid version")
    wheel = package["wheel"]
    if wheel != f"wheels/{wheel_filename(name, version)}":
        raise BundleError(f"library.json: {name} has unexpected wheel path {wheel!r}")
    if wheel not in entries:
        raise BundleError(f"{wheel}: wheel is missing from the bundle")
    if package["wheel_sha256"] != file_sha256(entries[wheel]):
        raise BundleError(f"{wheel}: wheel digest does not match library.json")
    code_sha = package["code_sha"]
    if not isinstance(code_sha, str) or not SHA256.match(code_sha):
        raise BundleError(f"library.json: {name} has invalid code_sha")
    entry_points = package["entry_points"]
    if not isinstance(entry_points, dict) or not entry_points:
        raise BundleError(f"library.json: {name} has no entry points")
    counts = Counter()
    for identifier, entry_point in entry_points.items():
        descriptor = by_id.get(identifier)
        if descriptor is None:
            raise BundleError(f"library.json: {name} lists unknown descriptor {identifier!r}")
        if descriptor["entry_point"] != entry_point:
            raise BundleError(f"{identifier}: entry point differs between manifest and descriptor")
        if descriptor["code_sha"] != code_sha:
            raise BundleError(f"{identifier}: descriptor code_sha differs from package code_sha")
        if not entry_point.startswith(f"{module}."):
            raise BundleError(f"{identifier}: entry point {entry_point!r} is outside {module}")
        counts[descriptor["kind"]] += 1
    declared = package["kind_counts"]
    if not isinstance(declared, dict) or set(declared) != {"operator", "reader"}:
        raise BundleError(f"library.json: {name} has invalid kind_counts")
    if declared != {"operator": counts.get("operator", 0), "reader": counts.get("reader", 0)}:
        raise BundleError(f"library.json: {name} kind_counts do not match its descriptors")


def _verify_checksums(entries: dict[str, bytes]) -> None:
    try:
        text = entries["SHA256SUMS"].decode("utf-8")
    except UnicodeDecodeError as error:
        raise BundleError("SHA256SUMS: invalid UTF-8") from error
    listed: dict[str, str] = {}
    for line in text.splitlines():
        digest, separator, name = line.partition("  ")
        if not separator or not SHA256.match(digest) or not name:
            raise BundleError(f"SHA256SUMS: malformed line {line!r}")
        if name in listed:
            raise BundleError(f"SHA256SUMS: duplicate entry {name!r}")
        listed[name] = digest
    expected = set(entries) - {"SHA256SUMS"}
    if set(listed) != expected:
        raise BundleError("SHA256SUMS: entries do not match bundle contents")
    for name, digest in listed.items():
        if file_sha256(entries[name]) != digest:
            raise BundleError(f"SHA256SUMS: digest mismatch for {name!r}")


def package_pins(document: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Map descriptor id to the package pin used by route lock files."""
    pins: dict[str, dict[str, str]] = {}
    for package in document["packages"]:
        pin = {
            "package": package["name"],
            "version": package["version"],
            "code_sha": package["code_sha"],
        }
        for identifier in package.get("entry_points", {}):
            pins[identifier] = pin
    return pins


__all__ = [
    "BundleError",
    "bundle_entries",
    "distribution_name",
    "json_bytes",
    "library_document",
    "package_pins",
    "package_record",
    "read_entries",
    "readme",
    "resolve_bundle",
    "sha256sums",
    "verify_entries",
    "wheel_filename",
    "write_bundle",
]
