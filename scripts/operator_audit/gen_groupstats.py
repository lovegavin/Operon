"""Generate group-comparison statistics routes for uncovered operators."""
from __future__ import annotations
import json, os, shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = Path("/tmp/groupstats")
IDS = """anova kruskal welch_anova levene bartlett fligner_kruskal dunn_test tukey_hsd
games_howell scheffe_test conover_test mann_whitney brunner_munzel cliffs_delta
rank_biserial mood_median eta_squared ttest_paired wilcoxon sign_test hotelling_t2
ks_2samp var_test tost_equivalence yuen_test""".split()

desc = {}
for p in sorted((REPO / "library/seed/operon").glob("package_*_descriptors.json")):
    for d in json.loads(p.read_text()):
        desc[d["id"]] = d
# also builtin bundle
bp = json.loads((REPO / "library/seed/operon/builtin_packages.json").read_text())
for pkg in bp["packages"]:
    for d in pkg.get("descriptors", []):
        desc.setdefault(d["id"], d)

rng_seed = 7
import random
random.seed(rng_seed)

samples = [f"S{i:02d}" for i in range(1, 25)]
THREE = {"anova","kruskal","welch_anova","levene","bartlett","fligner_kruskal","dunn_test","tukey_hsd","games_howell","scheffe_test","conover_test","eta_squared"}
groups = ["A"] * 12 + ["B"] * 12
features = [f"f{i}" for i in range(1, 9)]

def num_row(fi, si):
    base = 1.0 + 0.5 * fi
    delta = 1.6 if groups[si] == "A" else 0.0
    return f"{base + delta + random.uniform(-0.25, 0.25):.6f}"

data_lines = ["feature," + ",".join(samples)]
for fi, fname in enumerate(features):
    data_lines.append(fname + "," + ",".join(num_row(fi, si) for si in range(len(samples))))


for op in IDS:
    groups = (["A"]*8 + ["B"]*8 + ["C"]*8) if op in THREE else (["A"]*12 + ["B"]*12)
    d = desc.get(op)
    if not d:
        print("MISSING", op); continue
    schema = d.get("parameters_schema") or {}
    props = schema.get("properties", {})
    params = {}
    for k, v in props.items():
        if "default" in v:
            params[k] = v["default"]
    params.setdefault("output", op)
    params["feature_dim"] = "feature"
    params["sample_dim"] = "sample"
    params["group_dim"] = "sample"
    params["group_label"] = "group"
    if "group_a" in props: params["group_a"] = "A"
    if "group_b" in props: params["group_b"] = "B"
    if op == "tost_equivalence":
        params.setdefault("margin", 0.5)
    task = {
        "format": "operon.task",
        "version": 1,
        "name": op,
        "sources": {
            "data": {
                "path": "input/data.csv",
                "dims": ["feature", "sample"],
                "labels": {"feature": {"sample": 0}, "sample": "builtin"},
                "reader": "CsvReader",
            },
            "meta": {
                "path": "input/meta.csv",
                "dims": ["sample", "feature"],
                "labels": {"sample": {"feature": 0}, "feature": "builtin"},
                "reader": "CsvReader",
            },
        },
        "steps": [
            {"name": op, "inputs": ["data", "meta"], "params": params},
            {"name": "export_results", "inputs": [op], "params": {"filename": op}},
        ],
    }
    par = {
        "format": "biopipe.task-parameters",
        "schema_version": 1,
        "params": {},
        "sources": {"data": {}, "meta": {}},
        "steps": [
            {"name": op, "inputs": ["data", "meta"], "params": params, "context_params": {}},
            {"name": "export_results", "inputs": [op], "params": {"filename": op}, "context_params": {}},
        ],
    }
    meta_lines = ["sample,group"]
    for si, s in enumerate(samples):
        meta_lines.append(f"{s},{groups[si]}")
    root = OUT / op
    (root / "input").mkdir(parents=True, exist_ok=True)
    (root / "input/data.csv").write_text("\n".join(data_lines) + "\n")
    (root / "input/meta.csv").write_text("\n".join(meta_lines) + "\n")
    (root / "task.yaml").write_text(json.dumps(task, indent=2) + "\n")
    (root / "parameters.json").write_text(json.dumps(par, indent=2) + "\n")
    print("WROTE", op)
