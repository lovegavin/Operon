"""Deterministic pure-Python wheel writer.

Mirrors ``operon/dropins.write_wheel`` without importing application code.
"""

from __future__ import annotations

import base64
import csv
import io
import json
from hashlib import sha256
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def distribution_name(name: str) -> str:
    return name.replace("-", "_").replace(".", "_")


def wheel_filename(name: str, version: str) -> str:
    return f"{distribution_name(name)}-{version}-py3-none-any.whl"


def _metadata(name: str, version: str) -> bytes:
    lines = [
        "Metadata-Version: 2.1",
        f"Name: {name}",
        f"Version: {version}",
        "Requires-Python: >=3.11",
        "",
        "",
    ]
    return "\n".join(lines).encode("utf-8")


def _wheel() -> bytes:
    return (
        b"Wheel-Version: 1.0\n"
        b"Generator: Operon library\n"
        b"Root-Is-Purelib: true\n"
        b"Tag: py3-none-any\n"
    )


def _ordered(descriptors: list[dict]) -> list[dict]:
    return sorted(descriptors, key=lambda item: (item["kind"], item["id"]))


def _entry_points(descriptors: list[dict]) -> bytes:
    groups: dict[str, list[str]] = {"operator": [], "reader": []}
    for descriptor in _ordered(descriptors):
        groups[descriptor["kind"]].append(
            f"{descriptor['id']} = {descriptor['entry_point']}"
        )
    lines: list[str] = []
    for kind, section in (("operator", "operon.operators"), ("reader", "operon.readers")):
        lines.append(f"[{section}]")
        lines.extend(groups[kind])
        lines.append("")
    return "\n".join(lines).encode("utf-8")


def _operon_manifest(name: str, version: str, descriptors: list[dict]) -> bytes:
    value = {
        "protocol_version": 3,
        "name": name,
        "version": version,
        "title": None,
        "origin": "wheel",
        "descriptors": _ordered(descriptors),
    }
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _record(rows: list[tuple[str, bytes]]) -> bytes:
    stream = io.StringIO()
    writer = csv.writer(stream, lineterminator="\n")
    for path, data in rows:
        digest = base64.urlsafe_b64encode(sha256(data).digest()).rstrip(b"=").decode("ascii")
        writer.writerow([path, f"sha256={digest}", str(len(data))])
    return stream.getvalue().encode("utf-8")


def build_wheel(
    name: str,
    version: str,
    files: dict[str, bytes],
    *,
    code_sha: str,
    descriptors: list[dict],
) -> bytes:
    """Build a wheel whose bytes depend only on the arguments."""
    info = f"{distribution_name(name)}-{version}.dist-info"
    entries = {path: bytes(data) for path, data in files.items()}
    entries[f"{info}/METADATA"] = _metadata(name, version)
    entries[f"{info}/WHEEL"] = _wheel()
    identity = {
        "package": name,
        "version": version,
        "code_sha": code_sha,
    }
    entries[f"{info}/operon_identity.json"] = (
        json.dumps(identity, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")
    entries[f"{info}/operon.json"] = _operon_manifest(name, version, descriptors)
    entries[f"{info}/entry_points.txt"] = _entry_points(descriptors)

    ordered = sorted(entries)
    record = _record([(path, entries[path]) for path in ordered])
    record += f"{info}/RECORD,,\n".encode("utf-8")

    buffer = io.BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        for path in ordered:
            _write(archive, path, entries[path])
        _write(archive, f"{info}/RECORD", record)
    return buffer.getvalue()


def _write(archive: ZipFile, path: str, data: bytes) -> None:
    info = ZipInfo(path, ZIP_TIMESTAMP)
    info.compress_type = ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    archive.writestr(info, data)