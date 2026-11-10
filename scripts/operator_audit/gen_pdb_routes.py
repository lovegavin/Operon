import json, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path("/tmp/pdbroutes")
PDB = ROOT / "library/seed/routes/vhh_cdr_quantification/input/vhh_1mel.pdb"

rep = json.load(open(ROOT / "library/seed/operon/builtin_packages.json"))
desc = {}
for p in rep["packages"]:
    for d in p["descriptors"]:
        if d.get("kind") == "operator":
            desc[d["id"]] = d
cov = json.load(open(ROOT / "verification/operator-audit-7.0.9/l3_route_coverage.json"))
uncovered = set(cov["uncovered_ids"])

def defaults(d):
    props = d["parameters_schema"].get("properties", {})
    out = {}
    for k, s in props.items():
        if isinstance(s, dict) and "default" in s and not isinstance(s["default"], (dict, list)):
            out[k] = s["default"]
    return out

def dim_params(d):
    out = {}
    for port in d.get("contracts", {}).get("inputs", []):
        for b in port.get("dims", []) or []:
            if isinstance(b, dict) and isinstance(b.get("param"), str):
                default = b.get("default")
                if default in ("atom", "field"):
                    out[b["param"]] = default
                elif "field" in b["param"]:
                    out[b["param"]] = "field"
                else:
                    out[b["param"]] = "atom"
    return out

def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    ids = []
    for i in sorted(uncovered):
        d = desc.get(i)
        if not d or d.get("category") != "Structure" or d.get("inputs_arity") != 1:
            continue
        ids.append(i)
        rd = OUT / i
        (rd / "input").mkdir(parents=True)
        shutil.copy(PDB, rd / "input" / "s.pdb")
        task = {
            "format": "operon.task", "version": 1, "name": i,
            "sources": {"pdb": {"reader": "PdbReader", "path": "input/s.pdb",
                                "dims": ["atom", "field"], "labels": {}}},
            "parameters_file": "parameters.json",
            "steps": [{"name": i, "inputs": ["pdb"]},
                      {"name": "export_results", "inputs": ["audit_out"]}],
        }
        params = defaults(d)
        params.update(dim_params(d))
        if "binder_chains" in (d["parameters_schema"].get("properties") or {}):
            params["binder_chains"] = "A"
        if "target_chains" in (d["parameters_schema"].get("properties") or {}):
            params["target_chains"] = "L"
        params["output"] = "audit_out"
        outdir = "verification/operator-audit-7.0.9/pdb/" + i
        par = {
            "format": "biopipe.task-parameters", "schema_version": 1,
            "params": {"task": {}, "sources": {"pdb": {}}},
            "sources": {"pdb": {}},
            "steps": [
                {"name": i, "inputs": ["pdb"], "params": params, "context_params": {}},
                {"name": "export_results", "inputs": ["audit_out"],
                 "params": {"format": "csv", "filename": "result"}, "context_params": {}},
            ],
        }
        (rd / "task.yaml").write_text(json.dumps(task, indent=1) + "\n")
        (rd / "parameters.json").write_text(json.dumps(par, indent=1) + "\n")
    print(len(ids))
    for i in ids:
        print(i)

main()
