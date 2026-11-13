"""Package the builtin route templates as the Operon route-library collection.

The operator library is built once by ``operon_library_builder``; every route
pin must carry exactly ``{package, version, code_sha}`` from that same build.
This script compiles each reviewed ``task.yaml`` route into a three-file
workflow bundle, rewrites its ``plugin_lock`` from the built library manifest,
and collects the bundles into ``operon-routes-v<version>.zip``.

It is an application-side release tool: it may import the workflow compiler,
but it never computes library identity and never rewrites a wheel.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PIN_KEYS = ("package", "version", "code_sha")


def load_library(path: Path) -> dict:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if "library.json" not in names:
            raise SystemExit(f"{path}: missing library.json")
        document = json.loads(archive.read("library.json"))
        checksums = {}
        if "SHA256SUMS" in names:
            for line in archive.read("SHA256SUMS").decode("utf-8").splitlines():
                digest, _, name = line.partition("  ")
                if name:
                    checksums[name] = digest
        for name in names:
            if name == "SHA256SUMS" or name.endswith("/"):
                continue
            actual = hashlib.sha256(archive.read(name)).hexdigest()
            if checksums.get(name, actual) != actual:
                raise SystemExit(f"{path}: checksum mismatch for {name}")
    if document.get("bundle_format") != 1:
        raise SystemExit(f"{path}: not a bundle_format=1 library")
    return document


def pins_from_library(document: dict) -> dict[str, dict]:
    pins: dict[str, dict] = {}
    for package in document["packages"]:
        pin = {
            "package": package["name"],
            "version": package["version"],
            "code_sha": package["code_sha"],
        }
        for key in package.get("entry_points", {}):
            pins[key] = pin
    if not pins:
        raise SystemExit("library manifest declares no entry points")
    return pins


def route_key(record: dict, sources: dict) -> str:
    path = sources.get(record["id"], {}).get("path", "")
    parts = Path(path).parts
    if len(parts) >= 3 and parts[0] == "routes":
        return parts[1]
    slug = record["name"].lower().replace(" ", "_")
    return "".join(char if char.isalnum() or char in "_-" else "_" for char in slug)


def rewrite_pins(graph: dict, pins: dict[str, dict]) -> None:
    nodes = graph.get("nodes", [])
    operators = set()
    for node in nodes:
        operator = node.get("operator")
        if operator:
            operators.add(operator)
        source = node.get("source") or {}
        reader = source.get("reader")
        if reader:
            operators.add(reader)
    lock = graph.setdefault("plugin_lock", {})
    for operator in sorted(operators):
        pin = pins.get(operator)
        if pin is None:
            raise SystemExit(f"route references operator without a library pin: {operator}")
        lock[operator] = {key: pin[key] for key in PIN_KEYS}
    for key in list(lock):
        if key not in operators:
            del lock[key]


def validate_bundle(payload: bytes, pins: dict[str, dict]) -> None:
    with zipfile.ZipFile(__import__("io").BytesIO(payload)) as archive:
        names = set(archive.namelist())
        if names != {"graph.json", "parameters.json", "execution.json"}:
            raise SystemExit(f"route bundle must contain exactly three files, got {sorted(names)}")
        graph = json.loads(archive.read("graph.json"))
        lock = graph.get("plugin_lock") or {}
        for operator, pin in lock.items():
            expected = pins.get(operator)
            if expected is None:
                raise SystemExit(f"unknown pin in route bundle: {operator}")
            actual = {key: pin.get(key) for key in PIN_KEYS}
            wanted = {key: expected[key] for key in PIN_KEYS}
            if actual != wanted:
                raise SystemExit(f"pin mismatch for {operator}: {actual} != {wanted}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", type=Path, required=True, help="operon-library-v<version>.zip")
    parser.add_argument("--index", type=Path, default=ROOT / "library/seed/src/web/builtin_routes.json")
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    parser.add_argument("--version", default=None)
    args = parser.parse_args()

    document = load_library(args.library)
    version = args.version or document["library_version"]
    pins = pins_from_library(document)
    index = json.loads(args.index.read_text(encoding="utf-8"))

    from operon.application import Application
    from src.web.operator_catalog import catalog_from_descriptors
    from src.web.parameters import export_bundle
    from src.web.profile import make_settings

    packages = json.loads((ROOT / "library/seed/operon/builtin_packages.json").read_text(encoding="utf-8"))
    descriptors = [d for package in packages["packages"] for d in package.get("descriptors", [])]
    settings = make_settings(ROOT, ROOT / "frontend/dist", workspace=ROOT, data_dir=ROOT / ".studio/routes-build")
    application = Application(settings, catalog=catalog_from_descriptors(descriptors))
    written = []
    try:
        for record in index.get("routes", []):
            key = route_key(record, index.get("sources", {}))
            prepared = application.prepare(record["graph"])
            topology = prepared.model_dump(mode="json") if hasattr(prepared, "model_dump") else prepared
            rewrite_pins(topology, pins)
            payload = export_bundle(topology)
            validate_bundle(payload, pins)
            written.append((key, record["name"], payload))
    finally:
        application.shutdown()

    args.output.mkdir(parents=True, exist_ok=True)
    entries = []
    for key, name, payload in sorted(written):
        relpath = f"routes/{key}.operon.zip"
        entries.append((relpath, payload))

    routes = [
        {
            "key": key,
            "name": name,
            "file": f"routes/{key}.operon.zip",
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
        for key, name, payload in sorted(written)
    ]
    routes_document = {
        "schema_version": 1,
        "library_version": version,
        "routes": routes,
    }
    readme = [
        f"# Operon route library v{version}",
        "",
        f"{len(routes)} workflow bundles compiled against operator library v{version}.",
        "Import this collection in Studio (Route Operators -> Import route library) or",
        "import a single bundle with `operon graph open <key>.operon.zip`.",
        "",
    ]
    readme += [f"- {item['name']} ({item['key']})" for item in routes]

    payloads = [
        ("routes.json", (json.dumps(routes_document, indent=2, sort_keys=True) + "\n").encode("utf-8")),
        ("README.md", ("\n".join(readme) + "\n").encode("utf-8")),
        *entries,
    ]
    checksums = [f"{hashlib.sha256(payload).hexdigest()}  {relpath}" for relpath, payload in payloads]

    archive = args.output / f"operon-routes-v{version}.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for relpath, payload in payloads + [("SHA256SUMS", ("\n".join(sorted(checksums)) + "\n").encode("utf-8"))]:
            info = zipfile.ZipInfo(relpath, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            bundle.writestr(info, payload)
    print(json.dumps({"version": version, "routes": len(routes), "archive": str(archive),
                      "bytes": archive.stat().st_size}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
