#!/usr/bin/env python3
"""Archive route-level coverage evidence into the repository.

The goal is to preserve reproducible test code (task.yaml / parameters.json),
input and output manifests, run summaries and logs while avoiding committing
large binary artifacts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def file_manifest(root: Path) -> list[dict]:
    if not root.exists():
        return []
    out = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        out.append({
            "path": path.relative_to(root).as_posix(),
            "size": path.stat().st_size,
            "sha256": sha256(path),
        })
    return out


def copy_text(src: Path, dst: Path, limit: int = 2 * 1024 * 1024) -> bool:
    if not src.exists() or not src.is_file() or src.stat().st_size > limit:
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


def archive_one(op: str, item: dict, out_root: Path) -> dict:
    route = Path(item["route"])
    dst = out_root / "routes" / op
    dst.mkdir(parents=True, exist_ok=True)

    copied = []
    for name in ("task.yaml", "parameters.json"):
        src = route / name
        if src.exists():
            shutil.copy2(src, dst / name)
            copied.append(name)

    inputs = file_manifest(route / "input")
    outputs = file_manifest(route / "output" / "artifacts")
    (dst / "input_manifest.json").write_text(
        json.dumps({"root": str(route / "input"), "files": inputs}, indent=2) + "\n",
        encoding="utf-8",
    )
    (dst / "output_manifest.json").write_text(
        json.dumps({"root": str(route / "output" / "artifacts"), "files": outputs}, indent=2) + "\n",
        encoding="utf-8",
    )

    summary = route / "output" / "run_summary.json"
    if summary.exists():
        shutil.copy2(summary, dst / "run_summary.json")
    steps = route / "output" / "steps"
    if steps.exists():
        (dst / "steps").mkdir(parents=True, exist_ok=True)
        for path in sorted(steps.glob("*.json")):
            shutil.copy2(path, dst / "steps" / path.name)

    log_path = item.get("log")
    if log_path:
        copy_text(Path(log_path), dst / "run.log")
    copy_text(route / "output" / "run_summary.txt", dst / "run_summary.txt")

    return {
        "operator": op,
        "status": item.get("status"),
        "route": str(route),
        "command": item.get("command"),
        "seconds": item.get("seconds"),
        "error": item.get("error", ""),
        "export": item.get("export"),
        "export_rows": item.get("export_rows"),
        "inputs": inputs,
        "artifacts": outputs,
        "archived_files": copied,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="verification/coverage-8.0.1")
    parser.add_argument(
        "--evidence",
        nargs="+",
        default=[
            "/tmp/verify_stats.json",
            "/tmp/verify_omics.json",
            "/tmp/verify_sequence.json",
            "/tmp/verify_mltab.json",
            "/tmp/verify_structure.json",
        ],
    )
    args = parser.parse_args()

    out_root = Path(args.output)
    (out_root / "evidence").mkdir(parents=True, exist_ok=True)
    (out_root / "routes").mkdir(parents=True, exist_ok=True)

    runs: dict[str, dict] = {}
    sources = []
    for raw in args.evidence:
        path = Path(raw)
        if not path.exists():
            sources.append({"path": str(path), "status": "MISSING"})
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        sources.append({"path": str(path), "status": "READ", "count": len(data)})
        for op, item in data.items():
            runs[op] = archive_one(op, item, out_root)

    (out_root / "evidence" / "local_runs.json").write_text(
        json.dumps({"sources": sources, "runs": runs}, indent=2) + "\n",
        encoding="utf-8",
    )
    passed = sum(1 for r in runs.values() if r["status"] == "PASS")
    print(f"archived {len(runs)} routes ({passed} PASS) -> {out_root}")


if __name__ == "__main__":
    main()
