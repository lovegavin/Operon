import json
import os
import sys, subprocess, pathlib, time, hashlib

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

py = sys.executable
env = {"PYTHONPATH": str(REPO), "PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": os.environ.get("HOME", "/tmp"),
       "TMPDIR": "/tmp"}
base = REPO / "library/seed/routes"
out = []
t0 = time.time()
for i, d in enumerate(sorted(base.iterdir())):
    if not (d / "task.yaml").exists():
        continue
    try:
        p = subprocess.run([py, "scripts/run.py", str(d)], cwd=str(REPO), env=env,
                           capture_output=True, text=True, timeout=300)
        ok = p.returncode == 0
        lines = [l for l in (p.stderr or p.stdout).strip().splitlines() if l.strip()]
        err = "" if ok else " | ".join(lines[-3:])[:300]
    except subprocess.TimeoutExpired:
        ok, err = False, "TIMEOUT"
    out.append({"route": d.name, "ok": ok, "err": err})
    print(i, d.name, ok, flush=True)
json.dump(out, open("/tmp/route_replay.json", "w"), indent=1)
print("done", len(out), "ok", sum(1 for x in out if x["ok"]), f"{time.time()-t0:.0f}s")
