#!/usr/bin/env python3
"""Build the per-operator L1-L5 coverage ledger.

Definitions used here are intentionally conservative:

L1  conformance/static checks from the 8.0.1 operator audit
L2  at least one of: independent oracle, dedicated unit-test reference, or a
    passing contract harness (marked SMOKE, not ORACLE)
L3  route evidence from the audit, a built-in route, or an archived route run
L4  measured memory result from the audit; otherwise NOT_MEASURED with the
    declared estimate recorded as supporting evidence
L5  descriptor installs in the tested application bundle; PASS_ROUTE when the
    operator is also part of a built-in route bundle

The ledger is a coverage map, not a claim that every layer executed every
operator.  Statuses keep the distinction visible.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_descriptors(root: Path) -> dict[str, dict]:
    manifest = json.loads((root / "library/seed/operon/builtin_packages.json").read_text())
    out = {}
    for package in manifest["packages"]:
        for descriptor in package["descriptors"]:
            out[descriptor["id"]] = descriptor
    return out


def load_builtin_routes(root: Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for task in sorted((root / "library/seed/routes").glob("*/task.yaml")):
        try:
            data = json.loads(task.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for step in data.get("steps", []):
            name = step.get("name")
            if name:
                mapping.setdefault(name, task.parent.name)
    return mapping


def load_test_tokens(root: Path) -> dict[str, set[str]]:
    """Map every token used in tests to the test files that use it."""
    refs: dict[str, set[str]] = defaultdict(set)
    for path in sorted((root / "tests").rglob("test_*.py")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for token in set(TOKEN.findall(text)):
            refs[token].add(path.name)
    return refs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", default="verification/coverage-8.0.1")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    out_root = root / args.output
    out_root.mkdir(parents=True, exist_ok=True)

    descriptors = load_descriptors(root)
    builtin = load_builtin_routes(root)
    test_refs = load_test_tokens(root)

    local = json.loads((out_root / "evidence" / "local_runs.json").read_text())["runs"]
    srv_path = out_root / "evidence" / "srv_runs.json"
    srv = json.loads(srv_path.read_text())["operators"] if srv_path.exists() else {}
    audit_rows = list(csv.DictReader((root / "verification/operator-audit-8.0.1/operator_table.csv").open()))
    audit = {row["id"]: row for row in audit_rows if row["kind"] == "operator"}

    rows = []
    for op in sorted(audit):
        row = audit[op]
        descriptor = descriptors.get(op, {})
        category = descriptor.get("category") or "uncategorized"
        resources = descriptor.get("resources") or {}
        estimate = resources.get("estimate") or ""
        local_run = local.get(op)
        route_name = builtin.get(op)

        l1 = "PASS" if row["conformance"] == "PASS" else row["conformance"]
        l1_ev = "verification/operator-audit-8.0.1/operator_table.csv"

        if row.get("oracle_ref"):
            l2, l2_ev = "ORACLE", f"operator_table.csv:{row['oracle_ref']}"
        elif op in test_refs:
            l2, l2_ev = "UNIT", "tests/" + ",".join(sorted(test_refs[op]))
        elif row["contract_positive"] == "PASS":
            l2, l2_ev = "SMOKE", "operator_table.csv:contract_positive"
        else:
            l2 = "SKIP"
            l2_ev = f"operator_table.csv:{row['contract_positive']}"

        srv_runs = srv.get(op, [])
        srv_ok = [run for run in srv_runs if any(e.get("size", 0) > 2 for e in run.get("exports", []))]
        op_src = root / "library/seed/src/task/step/steps" / f"{op}.py"
        local_sha = sha256(op_src) if op_src.exists() else None
        srv_match = [run for run in srv_ok if run.get("operator_source_sha256") == local_sha]
        if local_run and local_run.get("status") == "PASS":
            l3, l3_ev = "EXECUTED", f"verification/coverage-8.0.1/routes/{op}"
        elif srv_match:
            run = srv_match[0]
            l3 = "EXECUTED_SRV"
            l3_ev = f"srv:{run['route_dir']}/output/run_summary.json"
        elif srv_ok:
            run = srv_ok[0]
            l3 = "EXECUTED_SRV_DRIFT"
            l3_ev = f"srv:{run['route_dir']} (operator source differs)"
        elif row["route_replay"] in {"builtin_route", "generated_route"}:
            l3, l3_ev = "ROUTE", f"operator_table.csv:{row['route_replay']}"
        else:
            l3, l3_ev = "SKIP", "no route in audit, archive, or srv evidence"

        if row["memory_within_budget"] in {"deterministic", "not_deterministic"}:
            l4, l4_ev = "MEASURED", f"operator_table.csv:{row['memory_within_budget']}"
        elif estimate:
            l4, l4_ev = "ESTIMATE", f"definition resources.estimate={estimate}"
        else:
            l4, l4_ev = "SKIP", "no memory estimate"

        if route_name:
            l5, l5_ev = "ROUTE", f"library/seed/routes/{route_name}/task.yaml"
        elif descriptor:
            l5, l5_ev = "INSTALL", "8.0.1 bundle install (3.1.9/4.0.0)"
        else:
            l5, l5_ev = "SKIP", "no descriptor"

        gaps = [name for name, status in (("L2", l2), ("L3", l3), ("L4", l4), ("L5", l5))
                if status in {"SKIP", "NOT_MEASURED", "FAIL"}]
        if l2 == "SMOKE":
            gaps.append("L2_ORACLE")
        if l4 == "ESTIMATE":
            gaps.append("L4_MEASURED")

        rows.append({
            "id": op,
            "category": category,
            "l1": l1,
            "l1_evidence": l1_ev,
            "l2": l2,
            "l2_evidence": l2_ev,
            "l3": l3,
            "l3_evidence": l3_ev,
            "l4": l4,
            "l4_evidence": l4_ev,
            "l5": l5,
            "l5_evidence": l5_ev,
            "gaps": ",".join(gaps),
        })

    csv_path = out_root / "operator_coverage.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    def counts(key: str) -> dict[str, int]:
        return dict(sorted(Counter(row[key] for row in rows).items()))

    summary = {
        "operators": len(rows),
        "layers": {key: counts(key) for key in ("l1", "l2", "l3", "l4", "l5")},
        "gap_layers": dict(sorted(Counter(g for row in rows for g in row["gaps"].split(",") if g).items())),
        "fully_executed_layers": {
            "L1": sum(1 for row in rows if row["l1"] == "PASS"),
            "L2_oracle_or_unit": sum(1 for row in rows if row["l2"] in {"ORACLE", "UNIT"}),
            "L2_any": sum(1 for row in rows if row["l2"] in {"ORACLE", "UNIT", "SMOKE"}),
            "L3_executed": sum(1 for row in rows if row["l3"] in {"EXECUTED", "EXECUTED_SRV"}),
            "L3_route_or_executed": sum(1 for row in rows if row["l3"] in {"ROUTE", "EXECUTED", "EXECUTED_SRV"}),
            "L4_measured": sum(1 for row in rows if row["l4"] == "MEASURED"),
            "L4_measured_or_estimate": sum(1 for row in rows if row["l4"] in {"MEASURED", "ESTIMATE"}),
            "L5_installed": sum(1 for row in rows if row["l5"] in {"INSTALL", "ROUTE"}),
        },
        "gap_examples": {
            "L2": [row["id"] for row in rows if row["l2"] == "SKIP"][:20],
            "L3": [row["id"] for row in rows if row["l3"] == "SKIP"][:20],
            "L4": [row["id"] for row in rows if row["l4"] == "SKIP"][:20],
        },
    }
    (out_root / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
