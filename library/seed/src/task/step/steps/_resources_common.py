"""Helpers for the library-owned large-resource manifest (``resources.json``).

The manifest is the single place that records, for every large external
resource (model weights, database bundles, official checkouts), the environment
variable that can point at a local copy, the default roots to probe, and the
exact files a dependent operator needs.  ``resource_preflight`` and the
``scripts/check_resources.py`` helper both build on this module, so an operator
fails with an actionable installation command instead of a bare
``FileNotFoundError``.

Links to an existing external copy are recorded as ``receipt-<id>.json``
files inside the resource root so a later check can tell a linked resource
from a downloaded one.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.core.errors import StepError

MANIFEST_NAME = "resources.json"
_RECEIPTS_DIR = ".receipts"


@dataclass(frozen=True)
class Resource:
    """One entry of the adjacent library resource manifest."""

    id: str
    title: str
    kind: str
    url: str
    install: str
    env: str
    roots: tuple[str, ...]
    files: tuple[str, ...]
    downloads: tuple[dict[str, Any], ...] = ()
    link_roots: tuple[str, ...] = ()
    expected_files: tuple[str, ...] = ()

    @classmethod
    def from_entry(cls, entry: dict[str, Any]) -> "Resource":
        identifier = str(entry.get("id") or "").strip()
        if not identifier:
            raise StepError("resource manifest entry without an id")
        files = tuple(str(name) for name in entry.get("files") or [] if str(name).strip())
        if not files:
            raise StepError(f"resource '{identifier}' lists no expected files")
        roots = tuple(str(root) for root in entry.get("roots") or [] if str(root).strip())
        downloads: list[dict[str, Any]] = []
        raw_downloads = entry.get("downloads") or []
        items: list[dict[str, Any]] = []
        if isinstance(raw_downloads, dict):
            hashes = entry.get("sha256") or {}
            sizes = entry.get("sizes") or {}
            for relative, value in raw_downloads.items():
                if isinstance(value, dict):
                    item = dict(value)
                    item.setdefault("path", relative)
                else:
                    item = {
                        "url": value,
                        "path": relative,
                        "sha256": hashes.get(relative, "") if isinstance(hashes, dict) else "",
                        "bytes": sizes.get(relative, 0) if isinstance(sizes, dict) else 0,
                    }
                items.append(item)
        elif isinstance(raw_downloads, list):
            items = list(raw_downloads)
        else:
            raise StepError(
                f"resource '{identifier}' downloads must be a list or an object"
            )
        for item in items:
            if not isinstance(item, dict):
                raise StepError(f"resource '{identifier}' has a non-object download entry")
            url = str(item.get("url") or "").strip()
            relative = str(item.get("path") or "").strip()
            if not url.startswith("https://"):
                raise StepError(
                    f"resource '{identifier}' download URL must use https://: {url!r}"
                )
            candidate = Path(relative)
            if not relative or candidate.is_absolute() or ".." in candidate.parts:
                raise StepError(
                    f"resource '{identifier}' download path is not a safe relative path: {relative!r}"
                )
            downloads.append(
                {
                    "url": url,
                    "path": relative,
                    "sha256": str(item.get("sha256") or "").strip().lower(),
                    "bytes": int(item.get("bytes") or 0),
                    "license": str(item.get("license") or ""),
                    "requires_token": bool(item.get("requires_token") or False),
                }
            )
        raw_link_roots = entry.get("link_roots") or []
        if not isinstance(raw_link_roots, list):
            raise StepError(f"resource '{identifier}' link_roots must be a list")
        resource_link_roots = tuple(
            str(value).strip() for value in raw_link_roots if str(value).strip()
        )
        expected = tuple(
            str(name) for name in entry.get("expected_files") or [] if str(name).strip()
        )
        for name in expected:
            candidate = Path(name)
            if candidate.is_absolute() or ".." in candidate.parts:
                raise StepError(
                    f"resource '{identifier}' expected file is not a safe relative path: {name!r}"
                )
        return cls(
            id=identifier,
            title=str(entry.get("title") or identifier),
            kind=str(entry.get("kind") or "resource"),
            url=str(entry.get("url") or ""),
            install=str(entry.get("install") or ""),
            env=str(entry.get("env") or ""),
            roots=roots,
            files=files,
            downloads=tuple(downloads),
            link_roots=resource_link_roots,
            expected_files=expected,
        )


def manifest_path() -> Path:
    """Use the same immutable provider revision as this helper's code."""
    candidate = Path(__file__).resolve().with_name(MANIFEST_NAME)
    if candidate.is_file():
        return candidate
    raise StepError(
        "The operator library's resources.json is missing; reinstall the library bundle"
    )


def load_resources(path: Path | str | None = None) -> dict[str, Resource]:
    """Read the manifest and return its entries keyed by resource id."""

    file = Path(path) if path is not None else manifest_path()
    if not file.is_file():
        raise StepError(f"resource manifest {file} does not exist")
    try:
        payload = json.loads(file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StepError(f"resource manifest {file} is not valid JSON: {exc}") from exc
    entries = payload.get("resources") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        raise StepError(f"resource manifest {file} has no 'resources' list")
    resources: dict[str, Resource] = {}
    for entry in entries:
        resource = Resource.from_entry(entry)
        if resource.id in resources:
            raise StepError(f"resource manifest lists '{resource.id}' twice")
        resources[resource.id] = resource
    return resources


def resolve_root(resource: Resource, root: str | Path | None = None) -> Path | None:
    """First existing directory among explicit root, env override and defaults."""

    if root:
        path = Path(str(root)).expanduser()
        return path if path.is_dir() else None
    if resource.env and os.environ.get(resource.env):
        path = Path(str(os.environ[resource.env])).expanduser()
        return path if path.is_dir() else None
    for candidate in resource.roots:
        path = Path(candidate).expanduser()
        if path.is_dir():
            return path
    return None


def _fallback_root(resource: Resource) -> Path:
    """Path a resource would use even before any declared root exists."""

    if resource.env and os.environ.get(resource.env):
        return Path(str(os.environ[resource.env])).expanduser()
    if resource.roots:
        return Path(resource.roots[0]).expanduser()
    return Path.home() / ".local" / "share" / "operon" / "resources" / resource.id


def _manifest_payload(
    manifest: dict[str, Any] | str | Path | None = None,
) -> dict[str, Any]:
    """Parsed manifest, from an explicit mapping/path or the adjacent file."""

    if isinstance(manifest, dict):
        return manifest
    try:
        file = Path(manifest) if manifest is not None else manifest_path()
        payload = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, ValueError, StepError):
        return {}
    return payload if isinstance(payload, dict) else {}


def link_roots(
    resource: Resource | None = None,
    manifest: dict[str, Any] | str | Path | None = None,
) -> tuple[str, ...]:
    """Allowed link sources: the manifest-level roots plus the per-resource ones.

    ``resource`` may be omitted to read only the manifest-level defaults, which
    is what the application asks for when it lists a resource.
    """

    payload = _manifest_payload(manifest)
    configured = payload.get("link_roots")
    if configured is not None and not isinstance(configured, list):
        raise StepError("resource manifest 'link_roots' must be a list")
    roots: list[str] = []
    declared = getattr(resource, "link_roots", ()) if resource is not None else ()
    for value in list(configured or []) + list(declared or ()):
        text = os.path.expanduser(str(value).strip())
        if text and text not in roots:
            roots.append(text)
    return tuple(roots)


def expected_files(resource: Resource) -> tuple[str, ...]:
    """Files used to verify a resource link; ``files`` when none are declared."""

    return resource.expected_files or resource.files


def receipt_path(resource: Resource, root: str | Path | None = None) -> Path:
    """Location of the link receipt beside the resource root.

    The receipt never lives inside the resource root itself: for a directory
    link the root *is* the link, so a file below it would be written into the
    external source tree.  ``<parent>/.receipts/receipt-<id>.json`` stays in
    the local resources base directory and survives the link being removed.
    """

    if root:
        target = Path(str(root)).expanduser()
    else:
        target = resolve_root(resource) or _fallback_root(resource)
    return Path(target).parent / _RECEIPTS_DIR / f"receipt-{resource.id}.json"


def _read_receipt_file(file: Path | None) -> dict[str, Any] | None:
    if file is None:
        return None
    try:
        if not file.is_file():
            return None
        payload = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def read_receipt(resource: Resource) -> dict[str, Any] | None:
    """Stored receipt for a linked resource, or ``None``."""

    return _read_receipt_file(receipt_path(resource))


def write_receipt(resource: Resource, payload: dict[str, Any]) -> Path:
    """Atomically store the link receipt beside the resource root."""

    path = receipt_path(resource)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)
    return path


def link_state(resource: Resource) -> dict[str, Any]:
    """Receipt-backed view of a resource link plus live file presence."""

    check = check_resource(resource)
    receipt = read_receipt(resource) or {}
    linked = (
        bool(receipt)
        and str(receipt.get("kind") or "") == "linked"
        and bool(check["linked"])
    )
    return {
        "linked": linked,
        "source": str(receipt.get("source") or "") or None,
        "mode": str(receipt.get("mode") or "") or None,
        "created_at": str(receipt.get("created_at") or "") or None,
        "probe": str(receipt.get("probe") or "") or None,
        "present": bool(check["present"]),
    }


def check_resource(resource: Resource, root: str | Path | None = None) -> dict[str, Any]:
    """Presence and size of every expected file of one resource."""

    resolved = resolve_root(resource, root)
    files: dict[str, dict[str, Any]] = {}
    for name in resource.files:
        path = resolved / name if resolved is not None else None
        present = bool(path is not None and path.is_file())
        files[name] = {
            "present": present,
            "size_mb": round(path.stat().st_size / (1024 * 1024), 3) if present and path is not None else 0.0,
        }
    missing = [name for name, info in files.items() if not info["present"]]
    if resolved is None:
        status = "missing"
    elif missing:
        status = "partial"
    else:
        status = "ok"
    present = status == "ok"
    receipt_file = receipt_path(resource, root) if (resolved is not None or root) else None
    receipt = _read_receipt_file(receipt_file)
    linked = (
        bool(receipt) and str(receipt.get("kind") or "") == "linked" and resolved is not None
    )
    return {
        "id": resource.id,
        "title": resource.title,
        "kind": resource.kind,
        "status": status,
        "present": present,
        "root": str(resolved) if resolved is not None else "",
        "env": resource.env,
        "url": resource.url,
        "install": resource.install,
        "files": files,
        "missing": missing,
        "size_mb": round(sum(info["size_mb"] for info in files.values()), 3),
        "receipt": str(receipt_file) if receipt is not None else "",
        "linked": linked,
        "source": str(receipt.get("source") or "") if linked and receipt else None,
    }


def check_many(ids: list[str] | None = None, root: str | Path | None = None) -> dict[str, dict[str, Any]]:
    """Check every selected resource id (all of them when ``ids`` is empty)."""

    resources = load_resources()
    if ids:
        unknown = [identifier for identifier in ids if identifier not in resources]
        if unknown:
            raise StepError(
                f"unknown resource(s): {', '.join(unknown)}; "
                f"known resources: {', '.join(sorted(resources))}"
            )
        selected = [resources[identifier] for identifier in ids]
    else:
        selected = [resources[identifier] for identifier in sorted(resources)]
    return {resource.id: check_resource(resource, root) for resource in selected}


def remedy(check: dict[str, Any]) -> str:
    """One-line, copy-paste friendly explanation for a failed check."""

    parts = [f"resource '{check['id']}' is {check['status']}"]
    if check["root"]:
        parts.append(f"under {check['root']}")
        if check["missing"]:
            parts.append(f"missing: {', '.join(check['missing'])}")
    else:
        parts.append("no candidate directory exists")
    if check["env"]:
        parts.append(f"set {check['env']} to the directory that holds these files")
    if check["install"]:
        parts.append(f"install: {check['install']}")
    if check["url"]:
        parts.append(check["url"])
    return "; ".join(parts)


def require(operator: str, resource_id: str, root: str | Path | None = None) -> tuple[Resource, Path]:
    """Return the resource and its root directory, or raise a StepError."""

    resources = load_resources()
    resource = resources.get(resource_id)
    if resource is None:
        raise StepError(
            f"{operator}: unknown resource '{resource_id}'; "
            f"known resources: {', '.join(sorted(resources))}"
        )
    check = check_resource(resource, root)
    if check["status"] != "ok":
        raise StepError(f"{operator}: {remedy(check)}")
    assert check["root"]
    return resource, Path(check["root"])
