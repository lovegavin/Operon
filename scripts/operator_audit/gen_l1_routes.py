"""Generate route templates from the L1 synthetic fixtures for operators that passed L1."""
import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "operator_audit"))
import l1_contract as L  # noqa: E402

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/l1routes")
RESULTS = Path(sys.argv[2] if len(sys.argv) > 2 else "/tmp/l1fix5/l1_contract.jsonl")
descriptors = {d["id"]: d for d in L.load_descriptors() if d.get("kind") == "operator"}
rows = [json.loads(line) for line in RESULTS.read_text().splitlines() if line.strip()]
passed = [r["id"] for r in rows if r["positive"] == "PASS"]
OUT.mkdir(parents=True, exist_ok=True)

made = 0
skipped = []
for op_id in passed:
    d = descriptors.get(op_id)
    if not d:
        continue
    contracts = (d.get("contracts") or {}).get("inputs") or []
    if not contracts or len(contracts) > 2:
        continue
    if any(str(f.get("logical_type", "")).startswith("file")
           for f in ((d.get("data_formats") or {}).get("inputs") or [])):
        continue
    props = ((d.get("parameters_schema") or {}).get("properties") or {})
    try:
        cls = L.import_class(d["entry_point"])
        module = importlib.import_module(cls.__module__)
        forms = [L.make_form(c, props, module=module) for c in contracts]
        params = L.make_params(d, props, forms, contracts)
    except Exception as exc:  # noqa: BLE001
        skipped.append((op_id, repr(exc)))
        continue
    if any(len(f.dims) > 2 or len(f.data.shape) > 2 for f in forms):
        continue
    folder = OUT / op_id
    inp = folder / "input"
    inp.mkdir(parents=True, exist_ok=True)
    sources = {}
    for index, form in enumerate(forms):
        name = "in%d" % index
        dims = list(form.dims)
        if len(dims) == 1:
            header = ["row"]
            lines = [",".join(header)]
            labels = list(form.labels.get(dims[0], {}).keys())
            for i in range(form.data.shape[0]):
                lines.append("%s,%.12g" % (labels[i] if i < len(labels) else i, form.data[i]))
            label_spec = {dims[0]: "builtin"}
        else:
            cols = list(form.labels.get(dims[1], {}).keys())
            ncol = form.data.shape[1]
            cols = (cols + ["c%d" % i for i in range(len(cols), ncol)])[:ncol]
            header = ["row"] + cols
            lines = [",".join(header)]
            rlabels = list(form.labels.get(dims[0], {}).keys())
            for i in range(form.data.shape[0]):
                rl = rlabels[i] if i < len(rlabels) else str(i)
                vals = ["%.12g" % v for v in form.data[i]]
                lines.append(",".join([rl] + vals))
            label_spec = {dims[0]: {dims[1]: 0}, dims[1]: "builtin"}
        (inp / (name + ".csv")).write_text("\n".join(lines) + "\n", encoding="utf-8")
        sources[name] = {"path": "input/%s.csv" % name, "dims": dims,
                         "labels": label_spec, "reader": "CsvReader"}
    out_param = d.get("output_parameter")
    if out_param:
        params[out_param] = "audit_out"
    steps = [{"name": op_id, "inputs": list(sources)}]
    steps.append({"name": "export_results", "inputs": ["audit_out"]})
    task = {"name": "audit route " + op_id, "sources": sources,
            "parameters_file": "parameters.json", "steps": steps}
    (folder / "task.yaml").write_text(json.dumps(task, indent=1), encoding="utf-8")
    parameters = {"format": "biopipe.task-parameters", "schema_version": 1,
                  "params": {}, "sources": {k: {} for k in sources},
                  "steps": [
                      {"name": op_id, "inputs": list(sources), "params": params,
                       "context_params": {}},
                      {"name": "export_results", "inputs": ["audit_out"],
                       "params": {"format": "csv", "filename": "out"},
                       "context_params": {}}]}
    (folder / "parameters.json").write_text(json.dumps(parameters, indent=1,
                                                       default=str), encoding="utf-8")
    made += 1

print(json.dumps({"made": made, "skipped": len(skipped), "out": str(OUT)}))
Path("/tmp/l1routes_skipped.json").write_text(json.dumps(skipped, indent=1))
