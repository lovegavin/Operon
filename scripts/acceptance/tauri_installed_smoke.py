"""Exercise an installed experimental host's real frontend save/exit handshake.

This is a native-window automation check, NOT proof of double-click, menus or
manual canvas interaction. A timeout is left visible for diagnosis, never killed
by process name. Requires an explicit host/config; never discovers production.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=120)
    args = parser.parse_args()
    host, config = args.host.resolve(strict=True), args.config.resolve(strict=True)
    raw = json.loads(config.read_text(encoding="utf-8-sig"))
    profile = (config.parent / raw["profile"]).resolve()
    report_path = profile / "logs/native-smoke.json"
    args.evidence.mkdir(parents=True, exist_ok=True)
    output = args.evidence / "smoke-result.json"
    if output.exists():
        raise FileExistsError("Use a new evidence directory for each sample")
    if report_path.exists():
        (args.evidence / "previous-native-smoke.json").write_bytes(report_path.read_bytes())
        report_path.unlink()
    started = time.perf_counter()
    with (args.evidence / "host.stdout.log").open("wb") as stdout, (args.evidence / "host.stderr.log").open("wb") as stderr:
        process = subprocess.Popen([str(host), "--config", str(config), "--smoke-test"],
                                   cwd=host.parent, stdout=stdout, stderr=stderr)
        try:
            code = process.wait(timeout=args.timeout)
        except subprocess.TimeoutExpired:
            code = None
    smoke = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else None
    events = smoke.get("events", []) if isinstance(smoke, dict) else []
    names = [e.get("event") for e in events]
    passed = code == 0 and all(n in names for n in ("ready", "draft_saved", "exit"))
    result = {"passed": passed, "pid": process.pid, "exit_code": code,
              "seconds": round(time.perf_counter() - started, 3), "host": str(host),
              "host_sha256": hashlib.sha256(host.read_bytes()).hexdigest(),
              "config": str(config), "profile": str(profile), "native_smoke": smoke,
              "scope": "installed native frontend ready/save/exit; not manual UI acceptance"}
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("passed", "pid", "exit_code", "seconds")}))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
