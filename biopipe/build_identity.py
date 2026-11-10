"""Deterministic identity for one Operon application plus its bundled library.

The desktop and a managed server derive the same identifier from identical
source trees.  It is deliberately *not* a version string: a source edit, a
library edit or a release bump changes the identifier even when the editable
version was not updated by hand.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
import sys


SCHEMA_VERSION = 1


def application_version(root):
    root = Path(root)
    project = root / "pyproject.toml"
    if project.is_file():
        try:
            import tomllib
            value = tomllib.loads(project.read_text(encoding="utf-8"))
            version = value.get("project", {}).get("version")
            if isinstance(version, str) and version:
                return version
        except (OSError, ValueError):
            pass
    from biopipe import __version__
    return __version__


def source_digest(root):
    """Hash the exact deterministic archive that a managed server receives."""
    from biopipe.remote.provision import source_archive
    return hashlib.sha256(source_archive(Path(root))).hexdigest()


def library_identity(root):
    from biopipe.library_location import source_root
    seed = source_root(root)
    if seed is None:
        return {"bundle_sha256": "", "library_version": "",
                "package_count": 0, "descriptor_count": 0, "catalog_digest": ""}
    index = seed / "biopipe/builtin_packages.json"
    document = json.loads(index.read_text(encoding="utf-8"))
    descriptors = [descriptor for package in document.get("packages", [])
                   for descriptor in package.get("descriptors", [])]
    release = {}
    for candidate in (Path(root) / "library/release.json", seed.parent / "release.json"):
        if candidate.is_file():
            try:
                release = json.loads(candidate.read_text(encoding="utf-8"))
            except ValueError:
                release = {}
            break
    catalog = sorted((descriptor.get("kind"), descriptor.get("id"),
                      descriptor.get("code_sha"), descriptor.get("declaration_sha"))
                     for descriptor in descriptors)
    # Identity must survive transport.  The source archive intentionally omits
    # route fixture data, so a raw tree hash differs between the desktop and an
    # extracted managed copy.  Hash the installed library definition instead.
    content = sorted((package.get("name"), package.get("version"), descriptor.get("kind"),
                      descriptor.get("id"), descriptor.get("code_sha"),
                      descriptor.get("declaration_sha"))
                     for package in document.get("packages", [])
                     for descriptor in package.get("descriptors", []))
    bundle_sha256 = hashlib.sha256(
        json.dumps(content, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {
        "bundle_sha256": bundle_sha256,
        "library_version": str(release.get("version") or document.get("version") or ""),
        "package_count": len(document.get("packages", [])),
        "descriptor_count": len(descriptors),
        "operator_count": sum(1 for descriptor in descriptors if descriptor.get("kind") == "operator"),
        "catalog_digest": hashlib.sha256(
            json.dumps(catalog, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
    }


@lru_cache(maxsize=8)
def _identity(root, digest):
    root = Path(root)
    version = application_version(root)
    library = library_identity(root)
    value = {
        "schema": SCHEMA_VERSION,
        "application": {"source_sha256": digest, "version": version},
        "library": {
            "bundle_sha256": library["bundle_sha256"],
            "library_version": library["library_version"],
            "package_count": library["package_count"],
            "descriptor_count": library["descriptor_count"],
        },
        "catalog": {
            "digest": library["catalog_digest"],
            "operator_count": library["operator_count"],
        },
        "environment": {"python": f"{sys.version_info.major}.{sys.version_info.minor}",
                        "platform": sys.platform},
    }
    material = {"schema": SCHEMA_VERSION, "application": value["application"],
                "library": value["library"], "catalog": {"digest": value["catalog"]["digest"]}}
    value["build_id"] = hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return value


def build_identity(root, *, source_sha256=None):
    root = Path(root).resolve()
    digest = source_sha256 or source_digest(root)
    return json.loads(json.dumps(_identity(root, digest)))


def matches(identity, other):
    """Compare only fields every build producer is required to publish."""
    if not isinstance(identity, dict) or not isinstance(other, dict):
        return False
    return (identity.get("build_id") == other.get("build_id")
            and identity.get("application", {}).get("source_sha256")
            == other.get("application", {}).get("source_sha256")
            and identity.get("library", {}).get("bundle_sha256")
            == other.get("library", {}).get("bundle_sha256"))
