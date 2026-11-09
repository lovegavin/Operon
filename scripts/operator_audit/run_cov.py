import json
import os
import sys, subprocess, pathlib, time

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

py = sys.executable
env = {"PYTHONPATH": str(REPO), "PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": os.environ.get("HOME", "/tmp")}
prev = {x["id"]: x["ok"] for x in json.load(open("/tmp/cov_check.json"))}
ids = [i for i in json.load(open("/tmp/cov_built.json")) if prev.get(i)]
base = pathlib.Path("/tmp/covroutes")
out = []
t0 = time.time()
for i, op in enumerate(ids):
    try:
        p = subprocess.run([py, "scripts/run.py", str(base / op)], cwd=str(REPO),
                           env=env, capture_output=True, text=True, timeout=180)
        ok = p.returncode == 0
        lines = [l for l in (p.stderr or p.stdout).strip().splitlines() if l.strip()]
        err = "" if ok else lines[-1][:200]
    except subprocess.TimeoutExpired:
        ok, err = False, "TIMEOUT"
    md5 = ""
    outdir = base / op / "output"
    if ok and outdir.exists():
        import hashlib
        files = sorted(outdir.glob("*.csv"))
        if files:
            md5 = hashlib.md5(files[0].read_bytes()).hexdigest()
    out.append({"id": op, "ok": ok, "err": err, "md5": md5})
    if (i + 1) % 50 == 0:
        print(i + 1, sum(1 for x in out if x["ok"]), f"{time.time()-t0:.0f}s", flush=True)
json.dump(out, open("/tmp/cov_run.json", "w"), indent=1)
print("done", len(out), "ok", sum(1 for x in out if x["ok"]))
