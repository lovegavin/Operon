import json, pathlib, re, ast, shutil

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

root = pathlib.Path(str(REPO))
man = json.load(open(root / "library/seed/operon/builtin_packages.json"))
cov = json.load(open("/tmp/route_coverage.json"))
uncovered = set(cov["uncovered"])
by_id = {}
for pkg in man["packages"]:
    for d in pkg["descriptors"]:
        by_id[d["id"]] = d

STD = ["value", "response", "predictor", "group", "event", "time", "x", "y", "z",
       "mz", "intensity", "weight", "score", "label", "category", "sample", "feature"]

def strings_in(path):
    out = []
    try:
        tree = ast.parse(pathlib.Path(path).read_text())
    except Exception:
        return out
    for n in ast.walk(tree):
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and 1 <= len(n.value) <= 24:
            out.append(n.value)
    return list(dict.fromkeys(out))

def pick(cols, key):
    names = [c for c in cols if key in c.lower()]
    return names[0] if names else (cols[0] if cols else "value")

def fill_required(params, props, required, cols):
    for r in required:
        if r in params or r == "output":
            continue
        spec = props.get(r) or {}
        t = spec.get("type")
        if isinstance(t, list):
            t = next((x for x in t if x != "null"), None)
        if spec.get("enum"):
            params[r] = spec["enum"][0]
        elif t == "array":
            params[r] = [pick(cols, "value"), pick(cols, "response")]
        elif t == "boolean":
            params[r] = False
        elif t == "integer":
            params[r] = 1
        elif t == "number":
            params[r] = 0.05 if ("alpha" in r or "level" in r or "pvalue" in r) else 1.0
        elif t == "object":
            params[r] = {}
        elif r in ("group_label", "stratum_label"):
            params[r] = pick(cols, "group")
        elif r == "event_label":
            params[r] = pick(cols, "event")
        elif r == "time_label":
            params[r] = pick(cols, "time")
        elif r in ("predictors", "covariates", "regressor", "count_predictors"):
            params[r] = [pick(cols, "predictor")]
        elif "response" in r or r in ("y_label", "outcome_label", "true_label", "value_label"):
            params[r] = pick(cols, "response")
        else:
            params[r] = pick(cols, "value")

def make_csv(dims, cols, n=12):
    r = dims[0]
    import random
    rng = random.Random(7)
    rows = [f"{r}{i}," + ",".join(f"{rng.uniform(0.1, 3.0):.6f}" for _ in cols) for i in range(n)]
    return "name," + ",".join(cols) + "\n" + "\n".join(rows) + "\n"

def build(op_id):
    d = by_id[op_id]
    ins = (d.get("contracts") or {}).get("inputs") or []
    if len(ins) > 2:
        return None
    schema = d.get("parameters_schema") or {}
    props = schema.get("properties") or {}
    params = {}
    port_dims = []
    for ci, c in enumerate(ins):
        b = c.get("dims") or []
        if not isinstance(b, list) or len(b) != 2:
            return None
        dims = []
        for i, bind in enumerate(b):
            if not isinstance(bind, dict):
                return None
            p = bind.get("param")
            default = bind.get("default")
            if p in props and isinstance(props[p].get("default"), str):
                dim = props[p]["default"]
            elif isinstance(default, str) and not default.startswith("{"):
                dim = default
            else:
                dim = f"d{i}"
            dims.append(dim)
            if p and p not in params:
                params[p] = dim
        port_dims.append(dims)
    for k, v in props.items():
        if k != "output" and k not in params and "default" in v:
            params[k] = v["default"]
    out = "out_" + re.sub(r"[^a-z0-9_]", "_", op_id)
    params["output"] = out
    code = d.get("entry_point") or ""
    mod = code.rsplit(".", 1)[0] if "." in code else code
    src = root / "library/seed" / (mod.replace(".", "/") + ".py")
    consts = [x for x in strings_in(src) if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,23}", x)]
    for v in props.values():
        if isinstance(v.get("default"), str):
            consts.append(v["default"])
    cols = list(dict.fromkeys(STD + consts))[:120]
    for dims in port_dims:
        for dim in dims:
            if dim in cols:
                cols.remove(dim)
    fill_required(params, props, schema.get("required") or [], cols)
    return {"ports": port_dims, "params": params, "output": out,
            "csv": make_csv(port_dims[0], cols) if port_dims else "", "cols": cols}

def write_route(op_id, spec, base):
    rd = base / op_id
    (rd / "input").mkdir(parents=True, exist_ok=True)
    sources, srcparams, steps = {}, {}, []
    names = []
    for i, dims in enumerate(spec["ports"]):
        nm = f"x{i}"
        names.append(nm)
        (rd / "input" / f"{nm}.csv").write_text(spec["csv"])
        r, c = dims
        sources[nm] = {"path": f"input/{nm}.csv", "dims": dims,
                       "labels": {r: {c: 0}, c: "builtin"}, "reader": "CsvReader"}
        srcparams[nm] = {}
    steps.append({"name": op_id, "inputs": names})
    steps.append({"name": "export_results", "inputs": [spec["output"]]})
    (rd / "task.yaml").write_text(json.dumps({"name": op_id, "sources": sources,
                                               "parameters_file": "parameters.json", "steps": steps}, indent=2))
    (rd / "parameters.json").write_text(json.dumps({
        "format": "biopipe.task-parameters", "schema_version": 1, "params": {},
        "sources": srcparams,
        "steps": [{"name": op_id, "inputs": names, "params": spec["params"], "context_params": {}},
                  {"name": "export_results", "inputs": [spec["output"]],
                   "params": {"format": "csv", "filename": op_id}, "context_params": {}}]}, indent=2))

if __name__ == "__main__":
    base = pathlib.Path("/tmp/covroutes2")
    if base.exists():
        shutil.rmtree(base)
    base.mkdir()
    built = []
    for op in sorted(uncovered):
        spec = build(op)
        if not spec:
            continue
        write_route(op, spec, base)
        built.append(op)
    print("built", len(built))
    json.dump(built, open("/tmp/cov_built2.json", "w"), indent=1)
