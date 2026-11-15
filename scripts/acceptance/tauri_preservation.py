"""Capture/compare production configuration around experimental host acceptance.

Read-only apart from the explicitly selected report. Uses only the standard library.
Does not read credentials or stop processes. Run under the same Windows user before
installation and after uninstall; a missing/inaccessible baseline is never a pass.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path


def file_record(path: Path) -> dict:
    if not path.exists():
        return {"path": str(path), "exists": False}
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"path": str(path), "exists": True, "sha256": digest}


def capture() -> dict:
    if os.name != "nt":
        raise RuntimeError("This acceptance probe requires Windows")
    import winreg

    desktop = Path.home() / "Desktop"
    shell_key = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, shell_key) as key:
        desktop = Path(os.path.expandvars(winreg.QueryValueEx(key, "Desktop")[0]))
    files = [Path.home() / name / "runtime.json" for name in (".biopipe", ".operon")]
    for directory in (desktop, Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs"):
        if directory.exists():
            files.extend(p for p in directory.rglob("*.lnk")
                         if any(n in p.name.lower() for n in ("operon", "biopipe"))
                         and "experimental" not in str(p).lower())
    entries = {}
    root = r"Software\Microsoft\Windows\CurrentVersion\Uninstall"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, root) as key:
        for i in range(winreg.QueryInfoKey(key)[0]):
            name = winreg.EnumKey(key, i)
            if not any(n in name.lower() for n in ("operon", "biopipe")) or "experimental" in name.lower():
                continue
            with winreg.OpenKey(key, name) as child:
                entries[name] = {str(k): [value, kind]
                                 for k, value, kind in (winreg.EnumValue(child, j)
                                                       for j in range(winreg.QueryInfoKey(child)[1]))}
    return {"schema": 1, "files": [file_record(p) for p in sorted(set(files))], "uninstall": entries}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--compare", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    current = capture()
    if not args.compare:
        # Never overwrite the original evidence on a rerun.
        with args.baseline.open("x", encoding="utf-8") as stream:
            json.dump(current, stream, indent=2, ensure_ascii=False)
        print("Production preservation baseline recorded")
        return 0
    baseline = json.loads(args.baseline.read_text(encoding="utf-8-sig"))
    matched = baseline == current
    result = {"passed": matched, "baseline": str(args.baseline), "current": current}
    if args.report:
        args.report.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Production preservation: " + ("PASS" if matched else "FAIL (see report)"))
    return 0 if matched else 1


if __name__ == "__main__":
    raise SystemExit(main())
