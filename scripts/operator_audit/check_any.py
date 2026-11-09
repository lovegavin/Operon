import json, subprocess, sys, pathlib, re

py = "/home/gavin/bp-numpy21/bin/python"
env = {"PYTHONPATH": "/home/gavin/Operon", "PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": "/home/gavin"}
base = pathlib.Path(sys.argv[1])
ids = json.load(open(sys.argv[2]))
mode = sys.argv[3] if len(sys.argv) > 3 else "check"
out = []
for i, op in enumerate(ids):
    cmd = [py, "scripts/run.py", str(base / op)] + (["--check"] if mode == "check" else [])
    try:
        p = subprocess.run(cmd, cwd="/home/gavin/Operon", env=env, capture_output=True, text=True, timeout=180)
        ok = p.returncode == 0
        err = ""
        if not ok:
            text = (p.stderr or "") + "\n" + (p.stdout or "")
            msgs = re.findall(r'"message"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
            err = " | ".join(msgs[:3])[:300] if msgs else text.strip().splitlines()[-1][:200]
    except subprocess.TimeoutExpired:
        ok, err = False, "TIMEOUT"
    out.append({"id": op, "ok": ok, "err": err})
    if (i + 1) % 50 == 0:
        print(i + 1, sum(1 for x in out if x["ok"]), flush=True)
json.dump(out, open(f"/tmp/{base.name}_{mode}.json", "w"), indent=1)
print("done", len(out), "ok", sum(1 for x in out if x["ok"]))
