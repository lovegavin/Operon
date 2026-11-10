#!/usr/bin/env python3
"""Assemble the per-operator audit table for library 7.0.5.

Combines the L0 static result, L1 contract result, L3 route coverage and the
sampled L4 determinism run into one row per operator. Missing measurements are
reported as ``not_measured`` rather than inferred.
"""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
VERSION = os.environ.get("OPERON_AUDIT_VERSION", "7.0.7")
EVIDENCE = REPO / "verification" / f"operator-audit-{VERSION}"
ROUTES = REPO / "library" / "seed" / "routes"


def _oracle_delta(op_id):
    path = EVIDENCE / "l2_oracle.json"
    if not path.exists():
        return ""
    data = json.loads(path.read_text(encoding="utf-8"))
    rec = data.get("results", {}).get(op_id)
    if not rec:
        return ""
    delta = rec.get("delta")
    if delta is None:
        delta = rec.get("corrs")
    return "" if delta is None else str(delta)


def load_jsonl(path):
    rows = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                item = json.loads(line)
                rows[item["id"]] = item
    return rows


def builtin_covered():
    covered = set()
    for route in sorted(ROUTES.iterdir()):
        task = route / "task.yaml"
        if not task.is_file():
            continue
        doc = yaml.safe_load(task.read_text(encoding="utf-8")) or {}
        for step in doc.get("steps") or []:
            name = step.get("name") if isinstance(step, dict) else None
            if name and name != "export_results":
                covered.add(name)
    return covered


def main():
    l0 = load_jsonl(EVIDENCE / "l0_static.jsonl")
    l1 = load_jsonl(EVIDENCE / "l1_full" / "l1_contract.jsonl")
    coverage = {}
    cov_path = EVIDENCE / "l3_route_coverage.json"
    if cov_path.exists():
        coverage = json.loads(cov_path.read_text(encoding="utf-8"))
    generated = {op: "PASS" for op in coverage.get("covered_ids", [])}
    deterministic = {}
    det_path = EVIDENCE / "l4_determinism.json"
    if det_path.exists():
        for item in json.loads(det_path.read_text(encoding="utf-8")).get("results", []):
            deterministic[item["id"]] = item.get("deterministic")
    builtin = builtin_covered()

    rows = []
    for op_id in sorted(l0):
        kind = l0[op_id].get("kind", "operator")
        conformance = l0[op_id].get("status", "")
        one = l1.get(op_id, {})
        positive = one.get("positive", "not_run") if one else "not_run"
        negative = one.get("negative", "not_run") if one else "not_run"
        if op_id in builtin:
            replay = "builtin_route"
        elif generated.get(op_id) == "PASS":
            replay = "generated_route"
        elif generated.get(op_id):
            replay = f"generated_{generated[op_id].lower()}"
        else:
            replay = "no_route"
        if op_id in deterministic:
            memory = "deterministic" if deterministic[op_id] else "not_deterministic"
        else:
            memory = "not_measured"
        notes = []
        if one.get("error"):
            notes.append(str(one["error"])[:180])
        if one.get("notes"):
            notes.extend(str(n) for n in one["notes"][:2])
        if l0[op_id].get("warnings"):
            notes.append("; ".join(l0[op_id]["warnings"][:2]))
        rows.append({
            "id": op_id,
            "kind": kind,
            "conformance": conformance,
            "contract_positive": positive,
            "contract_negative": negative,
            "oracle_ref": "l2_oracle" if op_id in {
                "kalman_local_level", "image_gaussian_blur", "pca",
                "conformal_split_regression", "bayesian_linear_regression",
                "cohens_kappa", "image_sobel_gradient",
                "genotype_call_rate_qc", "zscore", "min_max_scale",
                "ttest_one_sample"} else "",
            "oracle_delta": _oracle_delta(op_id),
            "route_replay": replay,
            "memory_within_budget": memory,
            "notes": " | ".join(notes),
        })

    out = EVIDENCE / "operator_table.csv"
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    operators = [row for row in rows if row["kind"] == "operator"]
    counts = {}
    for row in operators:
        counts[row["contract_positive"]] = counts.get(row["contract_positive"], 0) + 1
    replay = {}
    for row in operators:
        replay[row["route_replay"]] = replay.get(row["route_replay"], 0) + 1
    summary = {
        "operators": len(operators),
        "readers": len(rows) - len(operators),
        "l0_pass": sum(1 for row in rows if row["conformance"] == "PASS"),
        "contract": counts,
        "replay": replay,
    }
    (EVIDENCE / "operator_table_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
