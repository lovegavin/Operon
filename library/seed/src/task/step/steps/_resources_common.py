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

from collections.abc import Mapping

import json
import os
import stat
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
    rsync: dict[str, Any] | None = None
    link_roots: tuple[str, ...] = ()
    expected_files: tuple[str, ...] = ()
    link_unit: str = "tree"
    link_root: str = ""
    environments: tuple[str, ...] = ()
    components: tuple[dict[str, Any], ...] = ()

    @classmethod
    def from_entry(cls, entry: dict[str, Any]) -> "Resource":
        identifier = str(entry.get("id") or "").strip()
        if not identifier:
            raise StepError("resource manifest entry without an id")
        files = tuple(str(name) for name in entry.get("files") or [] if str(name).strip())
        if not files:
            raise StepError(f"resource '{identifier}' lists no expected files")
        roots = tuple(str(root) for root in entry.get("roots") or [] if str(root).strip())
        environments = tuple(
            str(name).strip() for name in entry.get("envs") or [] if str(name).strip()
        )
        components: list[dict[str, Any]] = []
        for raw in entry.get("units") or []:
            if not isinstance(raw, dict):
                raise StepError(f"resource '{identifier}' has a malformed unit entry")
            name = str(raw.get("name") or "").strip()
            if not name:
                raise StepError(f"resource '{identifier}' has a unit without a name")
            unit_files: list[str] = []
            file_sizes: dict[str, int] = {}
            for item in raw.get("files") or []:
                if isinstance(item, dict):
                    # Released manifests may publish per-file sizes next to the
                    # name; keep them so a download without its own size can
                    # still report a planned total.
                    file_name = str(item.get("path") or item.get("name") or "").strip()
                    try:
                        file_size = int(item.get("bytes") or item.get("size_bytes") or 0)
                    except (TypeError, ValueError):
                        file_size = 0
                    if file_name:
                        unit_files.append(file_name)
                        if file_size > 0:
                            file_sizes[file_name] = file_size
                elif str(item).strip():
                    unit_files.append(str(item).strip())
            components.append(
                {
                    "name": name,
                    "path": str(raw.get("path") or "").strip(),
                    "mode": "items" if str(raw.get("mode") or "tree") == "items" else "tree",
                    "kind": str(raw.get("kind") or "").strip(),
                    "bytes": int(raw.get("bytes") or 0),
                    "url": str(raw.get("url") or "").strip(),
                    "files": tuple(unit_files),
                    "file_sizes": file_sizes,
                    "note": str(raw.get("note") or "").strip(),
                }
            )
        downloads: list[dict[str, Any]] = []
        raw_rsync = entry.get('rsync') or entry.get('rsync_source')
        rsync: dict[str, Any] | None = None
        if isinstance(raw_rsync, dict) and raw_rsync.get('url'):
            rsync = {str(key): value for key, value in raw_rsync.items()}
        elif isinstance(raw_rsync, str) and raw_rsync.strip():
            rsync = {'url': raw_rsync.strip()}

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
            raw_url = item.get("url")
            if isinstance(raw_url, (list, tuple)):
                mirrors = [str(entry).strip() for entry in raw_url if str(entry).strip()]
            elif raw_url:
                mirrors = [str(raw_url).strip()]
            else:
                mirrors = []
            raw_git = item.get("git")
            git_spec: dict[str, Any] | None = None
            if isinstance(raw_git, dict) and str(raw_git.get("url") or "").strip():
                git_url = str(raw_git.get("url")).strip()
                if git_url.startswith("git+"):
                    git_url = git_url[4:]
                git_spec = {
                    "url": git_url,
                    "branch": str(raw_git.get("branch") or raw_git.get("ref") or ""),
                    "subdir": str(raw_git.get("subdir") or ""),
                    "note": str(raw_git.get("note") or ""),
                }
            for mirror in mirrors:
                if not mirror.startswith(("https://", "http://", "ftp://")):
                    raise StepError(
                        f"resource '{identifier}' download URL must use https://, http:// "
                        f"or ftp://: {mirror!r}"
                    )
            url = mirrors[0] if len(mirrors) == 1 else mirrors
            rsync = item.get("rsync") or item.get("rsync_source") or ""
            if isinstance(rsync, dict):
                rsync_url = str(rsync.get("url") or "").strip()
                rsync_spec = {"url": rsync_url, "note": str(rsync.get("note") or "")}
            else:
                rsync_url = str(rsync or "").strip()
                rsync_spec = {"url": rsync_url, "note": str(item.get("rsync_note") or "")}
            if rsync_url and not rsync_url.startswith("rsync://"):
                raise StepError(
                    f"resource '{identifier}' rsync URL must use rsync://: {rsync_url!r}"
                )
            if not mirrors and not rsync_url and git_spec is None:
                raise StepError(f"resource '{identifier}' download entry without a url")
            relative = str(item.get("path") or "").strip()
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
                    "archive": str(item.get("archive") or "").strip().lower(),
                    "member": str(item.get("member") or ""),
                    "unit": str(item.get("unit") or ""),
                    "rsync": rsync_spec if rsync_url else None,
                    "git": git_spec,
                }
            )
        raw_link_roots = entry.get("link_roots") or []
        if not isinstance(raw_link_roots, list):
            raise StepError(f"resource '{identifier}' link_roots must be a list")
        resource_link_roots = tuple(
            str(value).strip() for value in raw_link_roots if str(value).strip()
        )
        expected = tuple(
            str(name.get("path") if isinstance(name, dict) else name).strip()
            for name in entry.get("expected_files") or []
            if str(name.get("path") if isinstance(name, dict) else name).strip()
        )
        unit = str(entry.get("link_unit") or "tree").strip().lower() or "tree"
        link_root = str(entry.get("link_root") or "").strip()
        if unit not in {"tree", "items"}:
            raise StepError(
                f"resource '{identifier}' link_unit must be 'tree' or 'items': {unit!r}"
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
            rsync=rsync,
            link_roots=resource_link_roots,
            expected_files=expected,
            link_unit=unit,
            link_root=link_root,
            environments=environments,
            components=tuple(components),
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
    """Files used to verify a resource link.

    A resource that publishes units verifies their released layout: the unit
    files are the only list that travels with the download entries, so they win
    over a resource-level ``expected_files`` that may still describe the old
    layout.  Resources without unit files keep the declared list.
    """

    declared: tuple[Any, ...] = ()
    for component in getattr(resource, "components", ()) or ():
        if not isinstance(component, Mapping):
            continue
        files = component.get("files") or ()
        prefix = str(component.get("path") or "").strip("/")
        if not files:
            continue
        if prefix:
            declared = declared + tuple(
                f"{prefix}/{str(entry.get('path') if isinstance(entry, Mapping) else entry).strip('/')}"
                for entry in files
            )
        else:
            declared = declared + tuple(files)
    if not declared:
        declared = resource.expected_files or resource.files or ()
    names: list[str] = []
    for entry in declared:
        if isinstance(entry, Mapping):
            name = str(entry.get("path") or "").strip()
        else:
            name = str(entry).strip()
        if name and name not in names:
            names.append(name)
    return tuple(names)


def link_unit_of(resource: Resource) -> str:
    """Official maintenance unit: one shipped tree, or one unit per file."""

    return "items" if str(getattr(resource, "link_unit", "tree") or "tree") == "items" else "tree"


def link_units(resource: Resource) -> list[dict[str, Any]]:
    """Units the user links one by one, in the order a UI should show them."""

    if link_unit_of(resource) == "items":
        return [
            {"name": name, "target": name, "title": Path(name).name}
            for name in expected_files(resource)
        ]
    declared = getattr(resource, "components", ()) or ()
    if declared:
        # A resource that publishes maintenance units is linked unit by unit:
        # showing one opaque "tree" row would hide every file the manifest
        # delivers, which is exactly what the panel is meant to display.
        return [
            {
                "name": str(unit.get("name") or ""),
                "target": str(unit.get("path") or unit.get("name") or ""),
                "title": str(unit.get("title") or unit.get("name") or ""),
            }
            for unit in declared
            if str(unit.get("name") or "")
        ]
    return [{"name": "tree", "target": "", "title": resource.title}]


def link_mode(path: str | Path | None) -> str:
    """Return how *path* is linked: ``symlink``, ``junction``, ``hardlink`` or ``""``.

    ``Path.is_symlink()`` is false for a Windows junction, and a junction is the
    link the desktop creates without administrator rights, so link state has to
    look at the reparse tag as well.
    """

    if not path:
        return ""
    try:
        info = os.lstat(path)
    except OSError:
        return ""
    if getattr(info, "st_reparse_tag", 0) == 0xA0000003:
        return "junction"
    if stat.S_ISLNK(info.st_mode):
        return "symlink"
    if stat.S_ISREG(info.st_mode) and info.st_nlink > 1:
        return "hardlink"
    return ""


# Explicit old-name aliases: the manifest asks for the released name while a
# host provisioned earlier still has the previous file name on disk.  Only
# content-equivalent pairs belong here; no prefix or suffix matching, because
# two databases that merely share a directory are not interchangeable.
FILE_ALIASES: dict[str, tuple[str, ...]] = {
    "pdb_seqres/pdb_seqres.txt": ("pdb_seqres/pdb_seqres_2022_09_28.fasta",),
    "pdb_seqres/pdb_seqres_2022_09_28.fasta": ("pdb_seqres/pdb_seqres.txt",),
}


def resolved_path(root: str | Path, name: str) -> Path:
    """Return the on-disk path for *name*, following the explicit alias table."""

    base = Path(root)
    direct = base / name
    if direct.exists():
        return direct
    for alias in FILE_ALIASES.get(str(name), ()):
        alternate = base / alias
        if alternate.exists():
            return alternate
    return direct


def file_exists(root: str | Path, name: str) -> bool:
    """Whether *name* (or one of its explicit aliases) exists under *root*."""

    return resolved_path(root, name).exists()


def _file_entry(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"present": False, "size_mb": 0.0, "linked": False, "target": "", "mode": ""}
    present = path.is_file()
    mode = link_mode(path)
    return {
        "present": present,
        "size_mb": round(path.stat().st_size / (1024 * 1024), 3) if present else 0.0,
        "linked": bool(mode),
        "target": str(Path(os.path.realpath(path))) if mode and mode != "hardlink" else (str(path) if mode else ""),
        "mode": mode,
    }


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


def _unit_state(check: dict[str, Any], name: str) -> str:
    if name == "tree":
        return str(check.get("state") or "missing")
    info = (check.get("files") or {}).get(name) or {}
    if info.get("linked") or check.get("root_linked"):
        return "linked" if info.get("present") or check.get("root_linked") else "missing"
    return "downloaded" if info.get("present") else "missing"


def link_state(resource: Resource) -> dict[str, Any]:
    """Receipt-backed view of a resource link plus live file presence."""

    check = check_resource(resource)
    receipt = read_receipt(resource) or {}
    units = dict(receipt.get("units") or {})
    linked = bool(check["root_linked"] or any(info.get("linked") for info in check["files"].values()))
    recorded = str(receipt.get("source") or "") or None
    if not recorded and units:
        recorded = str(next(iter(units.values())).get("source") or "") or None
    return {
        "linked": linked,
        "state": check["state"],
        "source": recorded,
        "mode": (
            str(receipt.get("mode") or "") or None
            if receipt
            else (str(check.get("root_mode") or "") or None)
        ),
        "created_at": str(receipt.get("created_at") or "") or None,
        "probe": str(receipt.get("probe") or "") or None,
        "present": bool(check["present"]),
        "root_linked": check["root_linked"],
        "root_target": check["root_target"],
        "units": [
            {
                "name": unit["name"],
                "target": unit["target"],
                "state": _unit_state(check, unit["name"]),
                "source": str((units.get(unit["name"]) or {}).get("source") or "") or None,
                "receipt": bool(units.get(unit["name"])),
            }
            for unit in check["units"]
        ],
    }


def component_of(resource: Resource, name: str) -> dict[str, Any] | None:
    """Return one declared official maintenance unit by name."""

    wanted = str(name or "").strip()
    for unit in getattr(resource, "components", ()) or ():
        if unit.get("name") == wanted:
            return unit
    return None


def resource_components(resource: Resource, resolved: str | Path | None = None) -> list[dict[str, Any]]:
    """Official maintenance units of one resource with their on-disk state."""

    root_path = Path(resolved) if resolved is not None else None
    rows: list[dict[str, Any]] = []
    for unit in getattr(resource, "components", ()) or ():
        files = list(unit.get("files") or [])
        prefix = str(unit.get("path") or "").strip("/")
        entries = [
            _file_entry(
                resolved_path(root_path, f"{prefix}/{name}" if prefix else name)
                if root_path is not None else None
            )
            for name in files
        ]
        present = [entry["present"] for entry in entries]
        if not entries:
            state = "unknown"
        elif all(present):
            state = "present"
        elif any(present):
            state = "partial"
        else:
            state = "missing"
        rows.append(
            {
                "name": unit["name"],
                "path": unit.get("path") or "",
                "mode": unit.get("mode") or "tree",
                "kind": unit.get("kind") or "",
                "bytes": int(unit.get("bytes") or 0),
                "url": unit.get("url") or "",
                "note": unit.get("note") or "",
                "state": state,
                "files": [{"name": name, **entry} for name, entry in zip(files, entries)],
                "missing": [name for name, entry in zip(files, entries) if not entry["present"]],
                "size_mb": round(sum(entry["size_mb"] for entry in entries), 3),
            }
        )
    return rows


def check_resource(resource: Resource, root: str | Path | None = None) -> dict[str, Any]:
    """Presence and size of every expected file of one resource."""

    resolved = resolve_root(resource, root)
    files: dict[str, dict[str, Any]] = {}
    for name in expected_files(resource):
        path = resolved_path(resolved, name) if resolved is not None else None
        files[name] = _file_entry(path)
        present = bool(files[name]["present"])
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
    root_path = Path(resolved) if resolved is not None else None
    root_mode = link_mode(root_path)
    root_linked = bool(root_path is not None and root_mode)
    root_target = str(Path(os.path.realpath(root_path))) if root_linked else ""
    if resolved is None:
        state = "missing"
    elif root_linked:
        state = "linked"
    elif missing:
        state = "partial"
    else:
        state = "downloaded"
    return {
        "id": resource.id,
        "title": resource.title,
        "kind": resource.kind,
        "status": status,
        "state": state,
        "units": link_units(resource),
        "link_unit": link_unit_of(resource),
        "root_linked": root_linked,
        "root_mode": root_mode,
        "root_target": root_target,
        "present": present,
        "root": str(resolved) if resolved is not None else "",
        "env": resource.env,
        "url": resource.url,
        "install": resource.install,
        "files": files,
        "components": resource_components(resource, resolved),
        "environments": list(getattr(resource, "environments", ()) or ()),
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
