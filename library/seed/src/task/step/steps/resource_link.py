"""Link an existing external copy as a library resource.

The manifest declares where a resource must appear (:func:`._resources_common.
resolve_root`, ``<base>/<id>``).  When the same files already exist elsewhere on
the machine, :func:`link` connects them in place instead of copying
multi-gigabyte weights: a directory junction on Windows (``mklink /J``, no
administrator rights and works across volumes), a symbolic link on POSIX, or a
hard link for a single file when the source and the target share a volume.

A ``receipt-<id>.json`` file inside the resource root records how the link was
made, so :func:`unlink` removes only the link (never the source) and
:func:`._resources_common.link_state` can report the link without guessing.

The module is importable without the application: it uses the standard library
plus the adjacent manifest helper only.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import _resources_common as common

__all__ = ["link", "unlink"]

_PROBE_BYTES = 64
_RECEIPT_KIND = "linked"
_JUNCTION_TAG = 0xA0000003  # IO_REPARSE_TAG_MOUNT_POINT
_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


def _on_windows() -> bool:
    """Separate hook so the junction branch is testable on any platform."""

    return os.name == "nt"


def _is_junction(path: Path) -> bool:
    """True for an NTFS directory junction on any supported Python.

    ``Path.is_junction`` only exists from Python 3.12 onwards and ``os.stat``
    follows the reparse point, so the fallback inspects ``os.lstat`` instead.
    """

    probe = getattr(path, "is_junction", None)
    if probe is not None:
        try:
            return bool(probe())
        except OSError:
            return False
    if os.name != "nt":
        return False
    try:
        info = os.lstat(path)
    except OSError:
        return False
    tag = getattr(info, "st_reparse_tag", 0)
    if tag:
        return tag == _JUNCTION_TAG
    return bool(getattr(info, "st_file_attributes", 0) & _REPARSE_POINT)


def _is_link(path: Path) -> bool:
    return path.is_symlink() or _is_junction(path)


def _real(path: Path) -> Path:
    return Path(os.path.realpath(str(path)))


def _readlink(path: Path) -> Path | None:
    """Read a symlink or junction target, dropping Windows device prefixes."""

    try:
        target = os.readlink(path)
    except OSError:
        return None
    if target.startswith("\\\\?\\UNC\\"):
        target = "\\\\" + target[8:]
    elif target.startswith(("\\\\?\\", "\\??\\")):
        target = target[4:]
    return Path(target)


def _root(resource: common.Resource) -> Path:
    """Resource root directory: resolved root, env override, or first default."""

    resolved = common.resolve_root(resource)
    if resolved is not None:
        return resolved
    if resource.env and os.environ.get(resource.env):
        return Path(str(os.environ[resource.env])).expanduser()
    if resource.roots:
        return Path(resource.roots[0]).expanduser()
    return Path.home() / ".local" / "share" / "operon" / "resources" / resource.id


def _target(resource: common.Resource, source: Path | None = None) -> Path:
    """Path the link occupies.

    A directory source becomes the resource root itself (``<base>/<id>``).  A
    single-file source is linked under the root at its expected file name
    (``<base>/<id>/<file>``) so the ordinary presence check still applies.
    """

    root = _root(resource)
    if source is not None and source.is_file():
        expected = common.expected_files(resource)
        if len(expected) == 1:
            return root / expected[0]
        return root / source.name
    return root


def _safe_source(source: str | Path) -> Path:
    raw = str(source).strip()
    if not raw:
        raise ValueError("source must be a non-empty path")
    candidate = Path(os.path.expanduser(raw))
    if not candidate.is_absolute():
        raise ValueError(f"source must be an absolute path: {raw!r}")
    if ".." in Path(raw).parts:
        raise ValueError(f"source must not contain '..': {raw!r}")
    candidate = Path(os.path.normpath(candidate))
    if not candidate.exists():
        raise ValueError(f"source does not exist: {candidate}")
    return candidate


def _allowed_roots(
    resource: common.Resource, allowed_roots: Any = None
) -> tuple[Path, ...]:
    raw: list[Any] = list(common.link_roots(resource))
    if allowed_roots is not None:
        raw.extend(list(allowed_roots))
    roots: list[Path] = []
    for value in raw:
        text = os.path.expanduser(str(value).strip())
        if not text:
            continue
        path = Path(text)
        if not path.is_absolute():
            path = Path(os.path.abspath(path))
        if path not in roots:
            roots.append(path)
    return tuple(roots)


def _display_roots(resource: common.Resource, allowed_roots: Any = None) -> list[str]:
    """Roots as the manifest wrote them, so a message never rewrites a POSIX path."""
    raw: list[Any] = list(common.link_roots(resource))
    if allowed_roots is not None:
        raw.extend(list(allowed_roots))
    shown: list[str] = []
    for value in raw:
        text = str(value).strip()
        if text and text not in shown:
            shown.append(text)
    return shown


def _inside(path: Path, root: Path) -> bool:
    real_path = _real(path)
    real_root = _real(root)
    return real_path == real_root or real_path.is_relative_to(real_root)


def _points_to(target: Path, real_source: Path) -> bool:
    """True when ``target`` is a symlink/junction that resolves to the source."""

    if not _is_link(target):
        return False
    pointed = _readlink(target)
    if pointed is None:
        return False
    if not pointed.is_absolute():
        pointed = target.parent / pointed
    return _real(pointed) == real_source


def _same_file(target: Path, source: Path) -> bool:
    try:
        return target.is_file() and os.path.samefile(target, source)
    except OSError:
        return False


def _existing_mode(path: Path) -> str:
    if path.is_symlink():
        return "symlink"
    if _is_junction(path):
        return "junction"
    if path.is_file():
        return "hardlink"
    return "directory"


def _link_directory(source: Path, target: Path) -> str:
    if _on_windows():
        completed = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(target), str(source)],
            capture_output=True,
            text=False,
            check=False,
        )
        if completed.returncode != 0:
            raw = completed.stderr or completed.stdout or b""
            detail = raw.decode("utf-8", "replace").strip()
            raise ValueError(
                f"could not create a junction at {target}: {detail or completed.returncode}"
            )
        return "junction"
    try:
        os.symlink(source, target, target_is_directory=True)
    except OSError as exc:
        raise ValueError(f"could not create a symlink at {target}: {exc}") from exc
    return "symlink"


def _link_file(source: Path, target: Path) -> str:
    try:
        os.link(source, target)
        return "hardlink"
    except OSError as hardlink_error:
        try:
            os.symlink(source, target)
            return "symlink"
        except OSError as symlink_error:
            detail = (
                f"hardlink failed ({hardlink_error}); "
                f"symlink failed ({symlink_error})"
            )
            if _on_windows():
                raise ValueError(
                    f"could not link {target} to {source}: {detail}; "
                    "copy the file into place instead"
                ) from symlink_error
            raise ValueError(f"could not link {target} to {source}: {detail}") from symlink_error


def _locate(root: Path, relative: str) -> Path | None:
    """Resolve one expected file, allowing one folder of unit nesting.

    Upstream bundles such as the AlphaFold-2 ``afdb`` tree keep every unit in
    its own directory, so ``uniref90/uniref90.fasta`` must match the declared
    ``uniref90.fasta`` without declaring the folder twice.
    """

    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        return None
    direct = root / relative
    if direct.is_file():
        return direct
    name = candidate.name
    try:
        children = list(root.iterdir())
    except OSError:
        return None
    for child in children:
        if not child.is_dir():
            continue
        nested = child / name
        if nested.is_file():
            return nested
    return None


def _present_files(resource: common.Resource, source: Path) -> list[str]:
    """Expected file names that already exist in the source tree."""

    expected = common.expected_files(resource)
    if source.is_file():
        return [source.name] if source.name in expected else []
    names: list[str] = []
    for relative in expected:
        located = _locate(source, relative)
        if located is not None:
            try:
                names.append(str(located.relative_to(source)))
            except ValueError:
                names.append(str(relative))
    return names


def _probe(resource: common.Resource, source: Path, target: Path) -> tuple[str, int]:
    """Read the first expected file through the link (``probe`` + byte count)."""

    expected = common.expected_files(resource)
    probe = ""
    handle_path: Path | None = None
    if target.is_file():
        probe = target.name
        handle_path = target
    else:
        for relative in expected:
            candidate = Path(relative)
            if candidate.is_absolute() or ".." in candidate.parts:
                raise ValueError(
                    f"resource '{resource.id}' expected file is not a safe relative path: {relative!r}"
                )
            located = _locate(source, relative)
            if located is not None:
                probe = str(located.relative_to(source))
                handle_path = target / probe
                break
    if handle_path is None:
        listed = ", ".join(expected) or "(none declared)"
        raise ValueError(
            f"source does not contain any expected file of '{resource.id}': {listed}"
        )
    try:
        with handle_path.open("rb") as handle:
            payload = handle.read(_PROBE_BYTES)
    except OSError as exc:
        raise ValueError(f"linked resource is not readable at {handle_path}: {exc}") from exc
    return probe, len(payload)


def _remove_link(path: Path) -> bool:
    """Remove a symlink or junction itself; return False for real entries."""

    if path.is_symlink():
        path.unlink()
        return True
    if _is_junction(path):
        try:
            os.rmdir(path)
        except OSError:
            shutil.rmtree(path)
        return True
    return False


def _remove_target(path: Path) -> None:
    if _remove_link(path):
        return
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def _replace_target(target: Path, receipt: dict[str, Any]) -> None:
    """Remove ``target`` for ``replace=True`` without deleting unmanaged data."""

    if _remove_link(target):
        return
    if target.is_dir():
        try:
            populated = any(True for _ in target.iterdir())
        except OSError:
            populated = False
        managed = bool(receipt) and str(receipt.get("target") or "") == str(target)
        if populated and not managed:
            raise ValueError(
                f"target holds existing data; remove it explicitly: {target}"
            )
        shutil.rmtree(target)
    elif target.exists():
        target.unlink()


def _drop_receipt(resource: common.Resource, file: Path | None = None) -> None:
    try:
        path = file if file is not None else common.receipt_path(resource)
        if path.is_file():
            path.unlink()
    except OSError:
        pass


def _merge_links(source: Path, target: Path, expected: list[str]) -> list[str]:
    """Link only the declared files that are missing from a populated target."""

    linked: list[str] = []
    for relative in expected:
        destination = target / relative
        if destination.exists() or destination.is_symlink() or _is_junction(destination):
            continue
        candidate = source / relative
        if not candidate.exists():
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        if candidate.is_dir():
            _link_directory(candidate, destination)
        else:
            _link_file(candidate, destination)
        linked.append(relative)
    return linked


def link(
    resource: common.Resource,
    source: str | Path,
    *,
    replace: bool = False,
    allowed_roots: Any = None,
    unit: str | None = None,
) -> dict[str, Any]:
    """Connect ``source`` to the resource root; never copy the payload.

    ``unit`` selects the official maintenance unit that is being linked. A
    resource uses one tree (``unit='tree'``, the default) when upstream ships a
    single directory, or one unit per expected file when upstream keeps the
    pieces apart. Passing ``allowed_roots`` restores the optional allow-list
    check; by default any readable absolute path may be linked.
    """

    src = _safe_source(source)
    real = _real(src)
    if allowed_roots is not None:
        roots = _allowed_roots(resource, allowed_roots)
        if not any(_inside(real, root) for root in roots):
            listed = ", ".join(_display_roots(resource, allowed_roots)) or "(none)"
            raise ValueError(f"source is outside the allowed link roots: {src}; allowed: {listed}")

    root = _root(resource)
    expected = [str(name) for name in common.expected_files(resource)]
    key = (unit or 'tree').strip() or 'tree'
    if key in {'tree', '.', ''}:
        key = 'tree'
        target = _target(resource, src)
    else:
        component = common.component_of(resource, key)
        if component is not None:
            relative = str(component.get("path") or "").strip()
            target = root / relative if relative else root
        elif expected and key not in expected:
            choices = ', '.join(['tree', *expected]) or 'tree'
            raise ValueError(f"unknown link unit: {key}; expected one of {choices}")
        else:
            target = root / key

    if _is_link(target) and _points_to(target, real):
        receipt = common.read_receipt(resource) or {}
        recorded = (receipt.get("units") or {}).get(key) or {}
        return {
            "status": "already_linked",
            "name": resource.id,
            "unit": key,
            "target": str(target),
            "root": str(root),
            "source": str(recorded.get("source") or receipt.get("source") or src),
            "mode": str(recorded.get("mode") or receipt.get("mode") or _existing_mode(target)),
            "files": _present_files(resource, src),
        }
    # ``realpath`` follows an existing junction, so a linked root would look
    # like the source itself; compare against the un-followed root instead.
    real_root = Path(os.path.abspath(str(root)))
    if (
        real == real_root
        or real.is_relative_to(real_root)
        or real_root.is_relative_to(real)
    ):
        raise ValueError(
            f"source must not be the resource root or contain it: {src} (root: {root})"
        )
    if _same_file(target, src):
        return {
            "status": "already_linked",
            "name": resource.id,
            "unit": key,
            "target": str(target),
            "root": str(root),
            "source": str(src),
            "mode": "hardlink",
            "files": _present_files(resource, src),
        }
    merged: list[str] = []
    receipt_now = common.read_receipt(resource) or {}
    if target.exists() or _is_link(target):
        if not replace:
            raise ValueError(f"target already exists: {target}")
        managed = bool(receipt_now) and str(receipt_now.get("target") or "") == str(target)
        if not managed and key == 'tree' and src.is_dir() and expected:
            merged = _merge_links(src, target, expected)
            if not merged:
                listed = ', '.join(expected) or '(none declared)'
                raise ValueError(
                    "target holds existing data and none of the declared files are missing: "
                    f"{target}; declared: {listed}"
                )
        else:
            _replace_target(target, receipt_now)

    created = False
    if merged:
        mode = 'merge'
        probe, probe_bytes = _probe(resource, src, target)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            if src.is_dir():
                mode = _link_directory(src, target)
            else:
                mode = _link_file(src, target)
            created = True
            probe, probe_bytes = _probe(resource, src, target)
        except Exception:
            if created:
                _remove_target(target)
            raise

    created_at = (
        datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    )
    receipt = common.read_receipt(resource) or {}
    units = dict(receipt.get("units") or {})
    units[key] = {
        "source": str(src),
        "target": str(target),
        "mode": mode,
        "created_at": created_at,
        "probe": probe,
        "probe_bytes": probe_bytes,
        "linked_files": list(merged),
    }
    receipt.update(
        {
            "kind": _RECEIPT_KIND,
            "id": resource.id,
            "name": resource.id,
            "source": str(src),
            "target": str(target),
            "mode": mode,
            "created_at": created_at,
            "probe": probe,
            "probe_bytes": probe_bytes,
            "created_by": "resource_link",
            "unit": key,
            "units": units,
        }
    )
    common.write_receipt(resource, receipt)
    return {
        "status": "merged" if merged else "linked",
        "name": resource.id,
        "unit": key,
        "linked_files": list(merged),
        "target": str(target),
        "root": str(root),
        "source": str(src),
        "mode": mode,
        "probe": probe,
        "probe_bytes": probe_bytes,
        "files": _present_files(resource, src),
    }


def _forget_unit(
    resource: common.Resource,
    receipt: dict[str, Any],
    units: dict[str, Any],
    key: str,
) -> None:
    if key == 'tree':
        _drop_receipt(resource, common.receipt_path(resource))
        return
    units.pop(key, None)
    if not units:
        _drop_receipt(resource, common.receipt_path(resource))
        return
    receipt = dict(receipt)
    receipt['units'] = units
    receipt['unit'] = sorted(units)[0]
    first = units[receipt['unit']]
    for field in ('source', 'target', 'mode', 'created_at', 'probe', 'probe_bytes'):
        receipt[field] = first.get(field)
    common.write_receipt(resource, receipt)


def unlink(resource: common.Resource, unit: str | None = None) -> dict[str, Any]:
    """Remove only the link recorded for ``resource``; the source is untouched."""

    receipt = common.read_receipt(resource) or {}
    key = (unit or 'tree').strip() or 'tree'
    units = dict(receipt.get("units") or {})
    entry = units.get(key) or {}
    recorded = str(entry.get("target") or "").strip()
    if key in {'tree', '.', ''}:
        key = 'tree'
        target = Path(recorded) if recorded else _target(resource)
    else:
        target = Path(recorded) if recorded else _root(resource) / key
    # The receipt sits beside the resource root, never inside the linked tree.
    receipt_file = common.receipt_path(resource)
    mode = str(receipt.get("mode") or "") or None
    if not target.exists() and not _is_link(target):
        _forget_unit(resource, receipt, units, key)
        return {
            "status": "unlinked",
            "name": resource.id,
            "unit": key,
            "target": str(target),
            "root": str(_root(resource)),
            "mode": mode,
        }
    mode = mode or _existing_mode(target)
    if not _remove_link(target):
        if mode == "hardlink" and target.is_file():
            target.unlink()
        else:
            raise ValueError(
                f"target is not a link; refusing to delete it: {target}"
            )
    _forget_unit(resource, receipt, units, key)
    return {
        "status": "unlinked",
        "name": resource.id,
        "unit": key,
        "target": str(target),
        "root": str(_root(resource)),
        "mode": mode,
    }
