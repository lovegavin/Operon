import json, pathlib, re, ast, sys

root = pathlib.Path("/home/gavin/Operon")
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
    if names:
        return names[0]
    return cols[0] if cols else "value"

def fill_required(params, props, required, cols):
    for r in required:
        if r in params or r == "output":
            continue
        spec = props.get(r) or {}
        t = spec.get("type")
        if isinstance(t, list):
            t = next((x for x in t if x != "null"), None)
        if "enum" in spec and spec["enum"]:
            params[r] = spec["enum"][0]
        elif t == "array":
            key = "predictor" if "predict" in r or r in ("covariates", "regressor", "count_predictors") else "value"
            c0 = pick(cols, key)
            c1 = cols[1] if len(cols) > 1 and cols[1] != c0 else cols[0]
            params[r] = [c0, c1]
        elif t == "boolean":
            params[r] = False
        elif t == "integer":
            params[r] = 1
        elif t == "number":
            params[r] = 0.05 if ("alpha" in r or "level" in r or "pvalue" in r) else 1.0
        elif t == "object":
            params[r] = {}
        else:
            if r in ("group_label", "stratum_label"):
                params[r] = pick(cols, "group")
            elif r in ("event_label",):
                params[r] = pick(cols, "event")
            elif r in ("time_label",):
                params[r] = pick(cols, "time")
            elif r in ("predictors", "covariates", "regressor", "count_predictors"):
                params[r] = [cols[0]]
            elif "response" in r or r in ("y_label", "outcome_label", "true_label", "value_label"):
                params[r] = pick(cols, "response")
            else:
                params[r] = pick(cols, "value")

def dims_of(d):
    return (d.get("contracts") or {}).get("inputs") or []

def build(op_id):
    d = by_id[op_id]
    ins = dims_of(d)
    if len(ins) != 1:
        return None
    b = ins[0].get("dims") or []
    if not isinstance(b, list) or len(b) != 2:
        return None
    schema = d.get("parameters_schema") or {}
    props = schema.get("properties") or {}
    params = {}
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
        if p:
            params[p] = dim
    for k, v in props.items():
        if k != "output" and "default" in v:
            params[k] = v["default"]
    out = "out_" + re.sub(r"[^a-z0-9_]", "_", op_id)
    params["output"] = out
    code = d.get("entry_point") or ""
    mod = code.rsplit(".", 1)[0] if "." in code else code
    src = root / "library/seed" / (mod.replace(".", "/") + ".py")
    consts = [x for x in strings_in(src) if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,23}", x)]
    cols = list(dict.fromkeys(STD + consts))[:80]
    r, c = dims
    if c in cols:
        cols.remove(c)
    if r in cols:
        cols.remove(r)
    fill_required(params, props, schema.get("required") or [], cols)
    n = 12
    rows = []
    for i in range(n):
        vals = [f"{(0.1 + 0.05 * i + 0.01 * j):.6f}" for j in range(len(cols))]
        rows.append(f"{r}{i}," + ",".join(vals))
    csv = "name," + ",".join(cols) + "\n" + "\n".join(rows) + "\n"
    return {"dims": dims, "params": params, "output": out, "csv": csv, "cols": cols}

def write_route(op_id, spec, base):
    rd = base / op_id
    (rd / "input").mkdir(parents=True, exist_ok=True)
    (rd / "input/x.csv").write_text(spec["csv"])
    r, c = spec["dims"]
    task = {"name": op_id,
            "sources": {"x": {"path": "input/x.csv", "dims": spec["dims"],
                              "labels": {r: {c: 0}, c: "builtin"}, "reader": "CsvReader"}},
            "parameters_file": "parameters.json",
            "steps": [{"name": op_id, "inputs": ["x"]},
                      {"name": "export_results", "inputs": [spec["output"]]}]}
    (rd / "task.yaml").write_text(json.dumps(task, indent=2))
    params = {"format": "biopipe.task-parameters", "schema_version": 1, "params": {},
              "sources": {"x": {}},
              "steps": [{"name": op_id, "inputs": ["x"], "params": spec["params"], "context_params": {}},
                        {"name": "export_results", "inputs": [spec["output"]],
                         "params": {"format": "csv", "filename": op_id}, "context_params": {}}]}
    (rd / "parameters.json").write_text(json.dumps(params, indent=2))

if __name__ == "__main__":
    base = pathlib.Path("/tmp/covroutes")
    if base.exists():
        import shutil
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
    json.dump(built, open("/tmp/cov_built.json", "w"), indent=1)
