import subprocess, os, json, sys
from pathlib import Path
repo=Path(__file__).resolve().parents[2]; env=dict(os.environ, PYTHONPATH=str(repo))
base=Path('/tmp/regstats'); results=[]
mode=sys.argv[1] if len(sys.argv)>1 else 'check'
for d in sorted(base.iterdir()):
    if not d.is_dir(): continue
    cmd=[sys.executable, str(repo/'scripts/run.py'), str(d)] + (['--check'] if mode=='check' else [])
    try:
        p=subprocess.run(cmd,cwd=repo,env=env,capture_output=True,text=True,timeout=120)
        results.append((d.name,p.returncode,(p.stdout+p.stderr).strip().splitlines()[-1] if (p.stdout+p.stderr).strip() else ''))
    except subprocess.TimeoutExpired:
        results.append((d.name,124,'TIMEOUT'))
Path(f'/tmp/regstats_{mode}.json').write_text(json.dumps(results,indent=2))
ok=sum(1 for r in results if r[1]==0)
print(mode,'ok',ok,'/',len(results))
for n,rc,last in results:
    if rc!=0: print(n,rc,last[:160])
