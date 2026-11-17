"""Download the files declared by the library-owned large-resource manifest."""

from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step
from src.task.step.steps._resources_common import (
    Resource,
    load_resources,
    resolve_root,
)

_CHUNK = 1024 * 1024
_TIMEOUT = 120
_STATISTICS = ("downloaded", "bytes")


def _target_root(resource: Resource, root: str | None) -> Path:
    """Root to write into: explicit argument, env override, or first manifest root."""

    if root:
        return Path(root).expanduser()
    if resource.env and os.environ.get(resource.env):
        return Path(str(os.environ[resource.env])).expanduser()
    if resource.roots:
        return Path(resource.roots[0]).expanduser()
    return Path.home() / ".local" / "share" / "operon" / "resources" / resource.id


def _safe_destination(root: Path, relative: str) -> Path:
    candidate = Path(relative)
    if not relative or candidate.is_absolute() or ".." in candidate.parts:
        raise StepError(f"download path is not a safe relative path: {relative!r}")
    root_resolved = root.resolve()
    destination = (root_resolved / candidate).resolve()
    if destination != root_resolved and root_resolved not in destination.parents:
        raise StepError(f"download path escapes the resource root: {relative!r}")
    if destination.is_symlink():
        raise StepError(f"refusing to replace a symlink: {destination}")
    return destination


def _open_url(url: str, token_env: str = "") -> Any:
    headers = {"User-Agent": "operon-resource-fetch/1.0"}
    if token_env and os.environ.get(token_env):
        headers["Authorization"] = f"Bearer {os.environ[token_env]}"
    request = urllib.request.Request(url, headers=headers)
    return urllib.request.urlopen(request, timeout=_TIMEOUT)


def _download_one(
    entry: dict[str, Any],
    root: Path,
    *,
    overwrite: bool,
    opener: Any = None,
) -> dict[str, Any]:
    url = str(entry["url"])
    if not url.startswith("https://"):
        raise StepError(f"only https:// downloads are allowed: {url!r}")
    relative = str(entry["path"])
    destination = _safe_destination(root, relative)
    expected_bytes = int(entry.get("bytes") or 0)
    expected_sha = str(entry.get("sha256") or "").lower()
    token_env = str(entry.get("token_env") or "")

    if destination.is_file() and not overwrite:
        actual = destination.stat().st_size
        if expected_bytes and actual != expected_bytes:
            raise StepError(
                f"{destination} exists with {actual} bytes, expected {expected_bytes}; "
                "set overwrite=true to replace it"
            )
        if expected_sha:
            digest = _sha256(destination)
            if digest != expected_sha:
                raise StepError(
                    f"{destination} exists but its sha256 is {digest}, expected {expected_sha}; "
                    "set overwrite=true to replace it"
                )
        return {"path": relative, "downloaded": False, "bytes": actual, "status": "existing"}

    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".part")
    hasher = hashlib.sha256()
    written = 0
    open_url = opener or _open_url
    try:
        with open_url(url, token_env) as response, partial.open("wb") as handle:
            while True:
                chunk = response.read(_CHUNK)
                if not chunk:
                    break
                hasher.update(chunk)
                handle.write(chunk)
                written += len(chunk)
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        raise StepError(f"download failed for {url}: {exc}") from exc

    if expected_bytes and written != expected_bytes:
        raise StepError(
            f"download size mismatch for {relative}: got {written} bytes, expected {expected_bytes}"
        )
    digest = hasher.hexdigest()
    if expected_sha and digest != expected_sha:
        raise StepError(
            f"download sha256 mismatch for {relative}: got {digest}, expected {expected_sha}"
        )
    os.replace(partial, destination)
    return {
        "path": relative,
        "downloaded": True,
        "bytes": written,
        "sha256": digest,
        "status": "downloaded",
    }


def _sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


class ResourceFetchStep(Step):
    """Download the files of one declared large resource into its resource root."""

    provider = "operon-core"

    parameters_file = "resource_fetch.ResourceFetchStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {
            'inputs': [],
            'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
        },
        "protocol_version": 3,
        "id": "resource_fetch",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Fetch large-resource files",
        "description": (
            "Download the files declared by src/task/step/steps/resources.json for one "
            "resource. Files are streamed to a .part file, checked when size or sha256 "
            "are declared, and then moved into place atomically."
        ),
        "category": "Data",
        "icon": "Database",
        "contracts": {
            "version": 1,
            "inputs": [],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
            },
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": ["numpy"],
        "inputs_arity": 0,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs) -> None:
        params = ctx.step_params
        identifier = str(params.get("resource") or "").strip()
        if not identifier:
            raise StepError("resource_fetch: the 'resource' parameter is required")
        root_argument = str(params.get("root") or "").strip() or None
        overwrite = bool(params.get("overwrite") if params.get("overwrite") is not None else False)
        out_name = str(params.get("output") or "fetched")

        resource = load_resources().get(identifier)
        if resource is None:
            raise StepError(
                f"resource_fetch: unknown resource '{identifier}'; "
                f"known resources: {', '.join(sorted(load_resources()))}"
            )
        if not resource.downloads:
            raise StepError(
                f"resource_fetch: resource '{identifier}' has no downloads metadata; "
                f"install manually: {resource.install or resource.url or 'no install instruction'}"
            )

        root = _target_root(resource, root_argument)
        root.mkdir(parents=True, exist_ok=True)

        labels: list[str] = []
        rows: list[tuple[float, float]] = []
        outcomes: dict[str, str] = {}
        failures: list[str] = []
        for entry in resource.downloads:
            path = str(entry["path"])
            try:
                result = _download_one(entry, root, overwrite=overwrite)
            except StepError as exc:
                failures.append(f"{path}: {exc}")
                outcomes[path] = "failed"
                labels.append(path)
                rows.append((0.0, 0.0))
                continue
            labels.append(path)
            rows.append((1.0 if result["downloaded"] else 1.0, float(result["bytes"])))
            outcomes[path] = str(result["status"])

        receipt = {
            "resource": identifier,
            "root": str(root),
            "at": datetime.now(timezone.utc).isoformat(),
            "files": outcomes,
            "failed": failures,
        }
        receipt_path = root / f"receipt-{identifier}.json"
        receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")

        if failures:
            raise StepError(
                "resource_fetch: one or more files failed: " + "; ".join(failures)
            )

        data = np.asarray(rows, dtype=np.float32) if rows else np.zeros((0, 2), dtype=np.float32)
        out = Form(
            data=data,
            dims=["file", "statistic"],
            labels={
                "file": {label: index for index, label in enumerate(labels)},
                "statistic": {name: position for position, name in enumerate(_STATISTICS)},
            },
            info={
                "resource": identifier,
                "root": str(root),
                "n_files": len(labels),
                "n_downloaded": sum(1 for row in rows if row[0] > 0),
                "statuses": outcomes,
                "receipt": str(receipt_path),
                "missing_code": np.nan,
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "resource": identifier,
            "root": str(root),
            "n_files": len(labels),
            "n_downloaded": sum(1 for row in rows if row[0] > 0),
        }
        print(f"[resource_fetch] {identifier}: {len(labels)} files under {root}")

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
