"""Generate ML classifier/cluster-agreement routes for uncovered operators."""
from __future__ import annotations
import json, random
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = Path("/tmp/mlroutes")
IDS = """ada_boost_classifier complement_nb_classifier decision_tree_classifier
extra_trees_classifier knn lda lda_classifier multinomial_nb_classifier qda
sgd_classifier svm_classifier calinski_harabasz davies_bouldin dunn_index
silhouette silhouette_samples silhouette_score mutual_information
adjusted_mutual_info adjusted_rand_index fowlkes_mallows
homogeneity_completeness_v_measure normalized_mutual_info pair_confusion_matrix
variation_of_information""".split()

desc = {}
bp = json.loads((REPO / "library/seed/operon/builtin_packages.json").read_text())
for pkg in bp["packages"]:
    for d in pkg.get("descriptors", []):
        desc.setdefault(d["id"], d)

random.seed(11)
classes = "ABC"
samples = [f"S{i:02d}" for i in range(1, 37)]
truth = []
for i in range(36):
    truth.append(classes[i // 12])

feat_lines = ["sample," + ",".join(f"f{i}" for i in range(1, 7))]
for i, s in enumerate(samples):
    base = {"A": 2.0, "B": 5.0, "C": 8.0}[truth[i]]
    vals = [f"{base + random.uniform(-0.8, 0.8):.6f}" for _ in range(6)]
    feat_lines.append(s + "," + ",".join(vals))

label_lines = ["sample,truth"] + [f"{s},{truth[i]}" for i, s in enumerate(samples)]
pred_lines = ["sample,pred"]
for i, s in enumerate(samples):
    t = truth[i]
    # 75% agreement
    if random.random() < 0.75:
        p = t
    else:
        p = random.choice([c for c in classes if c != t])
    pred_lines.append(f"{s},{p}")


def write_csv(path: Path, lines):
    path.write_text("\n".join(lines) + "\n")


for op in IDS:
    d = desc.get(op)
    if not d:
        print("MISSING", op)
        continue
    props = (d.get("parameters_schema") or {}).get("properties", {})
    params = {}
    for k, v in props.items():
        if "default" in v:
            params[k] = v["default"]
    params["output"] = op
    for k, v in (("sample_dim", "sample"), ("feature_dim", "feature"),
                 ("label_dim", "label"), ("target_label", "truth"),
                 ("label_a", "truth"), ("label_b", "pred")):
        if k in props:
            params[k] = v

    sources = {
        "features": {
            "path": "input/features.csv",
            "dims": ["sample", "feature"],
            "labels": {"sample": {"feature": 0}, "feature": "builtin"},
            "reader": "CsvReader",
        },
        "truth": {
            "path": "input/labels.csv",
            "dims": ["sample", "label"],
            "labels": {"sample": {"label": 0}, "label": "builtin"},
            "reader": "CsvReader",
        },
        "preds": {
            "path": "input/preds.csv",
            "dims": ["sample", "label"],
            "labels": {"sample": {"label": 0}, "label": "builtin"},
            "reader": "CsvReader",
        },
    }
    agreement = {"adjusted_mutual_info","adjusted_rand_index","fowlkes_mallows","homogeneity_completeness_v_measure","normalized_mutual_info","pair_confusion_matrix","variation_of_information"}
    inputs = ["truth", "preds"] if op in agreement else ["features", "truth"]
    steps = [{"name": op, "inputs": inputs, "params": params},
             {"name": "export_results", "inputs": [op], "params": {"filename": op}}]
    task = {"format": "operon.task", "version": 1, "name": op,
            "sources": sources, "steps": steps}
    par = {"format": "biopipe.task-parameters", "schema_version": 1,
           "params": {},
           "sources": {k: {} for k in sources},
           "steps": [
               {"name": op, "inputs": inputs, "params": params, "context_params": {}},
               {"name": "export_results", "inputs": [op], "params": {"filename": op}, "context_params": {}},
           ]}
    root = OUT / op
    (root / "input").mkdir(parents=True, exist_ok=True)
    write_csv(root / "input/features.csv", feat_lines)
    write_csv(root / "input/labels.csv", label_lines)
    write_csv(root / "input/preds.csv", pred_lines)
    (root / "task.yaml").write_text(json.dumps(task, indent=2) + "\n")
    (root / "parameters.json").write_text(json.dumps(par, indent=2) + "\n")
    print("WROTE", op)
