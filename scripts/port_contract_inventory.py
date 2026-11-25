"""Generate the port-contract inventory for the 5.8.2 form/file_artifact rule.

Reads every operator sidecar and its step module, classifies each ``*_path``
parameter by role (data, tool, weights, resource, output), and writes
``docs/design/port_contract_inventory.md``.  The document freezes the counts
and name lists the registry checks are derived from; regenerate it instead of
editing it by hand.

Unknown path-parameter names abort the run so a new parameter cannot silently
land in the wrong role.
"""
from __future__ import annotations

import argparse
import ast
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STEPS = ROOT / "library" / "seed" / "src" / "task" / "step" / "steps"
DEFAULT_OUT = ROOT / "docs" / "design" / "port_contract_inventory.md"

# Path parameters that name an external executable or its runner script.
TOOL = {
    "mkdssp_path", "dssp_path", "vina_path", "proteinmpnn_path", "ligandmpnn_path",
    "foldseek_path", "rnafold_path", "rnasubopt_path", "rnaduplex_path", "rnacofold_path",
    "hmmscan_path", "cmscan_path", "minimap2_path", "fpocket_path", "pdb2pqr_path",
    "prodigal_path", "amrfinder_path", "antismash_path", "colabfold_path", "openfold_path",
    "rfdiffusion_path", "flye_path", "trnascan_path", "quast_path", "minced_path", "runner_path",
}
# Model weights or parameter files shipped as resources.
WEIGHTS = {"weights_path", "model_path", "params_path"}
# Reference databases and annotation bundles shipped as resources.
RESOURCE = {"hmm_path", "obo_path", "gaf_path", "database_path"}
# Directory a step writes into; never an input.
OUTPUT = {"output_path", "flex_output_path"}
# Run data: the parameters the rule forbids as a transport channel.
DATA = {
    "structure_path", "fasta_path", "trajectory_path", "topology_path", "query_path",
    "target_path", "reference_path", "native_path", "complex_path", "ligand_path",
    "pose_path", "affinity_path", "boltz_path", "flex_path", "receptor_path",
}
# Data that cannot be represented as a form: binary trajectories, docked poses,
# YAML/JSON result bundles.  Everything else in DATA becomes a form port.
FILE_DATA = {
    "trajectory_path", "topology_path", "affinity_path", "boltz_path", "complex_path",
    "ligand_path", "pose_path", "flex_path", "receptor_path",
}
# Emitters that stay file_artifact because their product cannot be a form.
KEEP_EMIT = {"align_reads", "build_contacts", "result_report"}


def category(name: str) -> str:
    for role, names in (
        ("tool", TOOL),
        ("weights", WEIGHTS),
        ("resource", RESOURCE),
        ("output", OUTPUT),
        ("data", DATA),
    ):
        if name in names:
            return role
    return "unknown"


def fileish(entry: dict) -> bool:
    logical = str(entry.get("logical_type") or "")
    reps = [str(r) for r in (entry.get("representations") or [])]
    return "file" in logical or "file_artifact" in logical or any("file" in r for r in reps)


def find_definition(tree: ast.AST) -> dict | None:
    best = None
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "definition":
                try:
                    value = ast.literal_eval(node.value)
                except Exception:
                    continue
                if isinstance(value, dict) and "data_formats" in value:
                    best = value
    return best


def load_rows() -> tuple[list[dict], list[str]]:
    rows: list[dict] = []
    unparsed: list[str] = []
    for side in sorted(STEPS.glob("*.parameters.json")):
        base = side.name[: -len(".parameters.json")]
        module = base.split(".")[0]
        src = STEPS / (module + ".py")
        if not src.exists():
            unparsed.append(base + " (no module)")
            continue
        tree = ast.parse(src.read_text(encoding="utf-8"), filename=str(src))
        definition = find_definition(tree)
        if definition is None:
            unparsed.append(base + " (no definition)")
            continue
        formats = definition.get("data_formats") or {}
        props = json.loads(side.read_text(encoding="utf-8")).get("properties", {})
        paths = [name for name in props if name.endswith("_path")]
        rows.append(
            {
                "name": str(definition.get("id") or module),
                "module": module,
                "arity": definition.get("inputs_arity"),
                "in_file": any(fileish(item) for item in (formats.get("inputs") or [])),
                "in_form": any(
                    str(item.get("logical_type") or "") == "form"
                    or "form" in [str(r) for r in (item.get("representations") or [])]
                    for item in (formats.get("inputs") or [])
                ),
                "out_file": any(fileish(item) for item in (formats.get("outputs") or [])),
                "paths": paths,
            }
        )
    return rows, unparsed


def planned_kind(param: str) -> str:
    return "file_artifact" if param in FILE_DATA else "form"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    rows, unparsed = load_rows()
    by_name = {row["name"]: row for row in rows}
    if len(by_name) != len(rows):
        print("duplicate operator ids in sidecars")
        return 2

    role_params: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    unknown: list[str] = []
    for row in rows:
        for param in row["paths"]:
            role = category(param)
            if role == "unknown":
                unknown.append(f"{row['name']}.{param}")
                continue
            role_params[role][param].append(row["name"])
    if unknown:
        print("unknown *_path parameters (add them to a role set):")
        for item in sorted(unknown):
            print("  " + item)
        return 2

    counts = Counter()
    for role, params in role_params.items():
        counts[role] = sum(len(ops) for ops in params.values())

    data_ops = {name: row for name, row in by_name.items() if any(category(p) == "data" for p in row["paths"])}
    zero_input = {name: row for name, row in data_ops.items() if row["arity"] == 0}
    overrides = {name: row for name, row in data_ops.items() if row["arity"] not in (0, None)}
    emitters = {name: row for name, row in by_name.items() if row["out_file"]}
    consumers = {name: row for name, row in by_name.items() if row["in_file"]}

    lines: list[str] = []
    add = lines.append
    add("# Port contract inventory (application 5.8.2, library 1.2.1)")
    add("")
    add("Frozen inventory behind the 5.8.2 port rule. The rule itself is recorded in")
    add("`HANDOVER-2026-11-25.md`: ports carry only `form` or `file_artifact`, and an")
    add("operator must not transport run data through a bare path parameter. Tool,")
    add("weights, resource and output paths stay as parameters and are annotated with a")
    add("role instead of being rejected.")
    add("")
    add("Generated by `scripts/port_contract_inventory.py`; regenerate it rather than")
    add("editing by hand. Path roles are declared by name in that script, so an unknown")
    add("`*_path` name fails the run instead of silently joining the wrong role.")
    add("")
    add("## Summary")
    add("")
    add("| Quantity | Count |")
    add("| --- | ---: |")
    add(f"| Operator sidecars scanned | {len(rows) + len(unparsed)} |")
    add(f"| Definitions parsed | {len(rows)} |")
    add(f"| Definitions built indirectly (manual review) | {len(unparsed)} |")
    add(f"| Operators emitting `file_artifact` | {len(emitters)} |")
    add(f"| Operators consuming `file_artifact` | {len(consumers)} |")
    add(f"| Operators with data path parameters | {len(data_ops)} |")
    add(f"| Zero-input operators carrying run data by path | {len(zero_input)} |")
    add(f"| Ported operators still carrying a data path override | {len(overrides)} |")
    for role in ("tool", "weights", "resource", "output"):
        add(f"| `{role}` path parameters (occurrences) | {counts[role]} |")
    add(f"| Run-data path parameters (occurrences) | {counts['data']} |")
    add("")

    add("## Emitting operators")
    add("")
    add("Only `align_reads`, `build_contacts` and `result_report` keep a `file_artifact`")
    add("output: a BAM, a Hi-C contact store and a report cannot be represented as a form")
    add("without losing their content. The other fifteen move to form outputs.")
    add("")
    add("| Operator | Output ports | Action |")
    add("| --- | --- | --- |")
    for name in sorted(emitters):
        row = emitters[name]
        action = "keep (whitelisted terminal)" if name in KEEP_EMIT else "convert to form"
        add(f"| `{name}` | {row['arity']} in / file out | {action} |")
    add("")

    add("## Consuming operators")
    add("")
    add("These keep `file_artifact` inputs: they open the file with a streaming library")
    add("or hand it to an external tool, and materialising it as a form would defeat the")
    add("point. Their outputs are forms.")
    add("")
    add("| Operator | Inputs arity | Also takes form |")
    add("| --- | ---: | --- |")
    for name in sorted(consumers):
        row = consumers[name]
        arity = row["arity"] if row["arity"] is not None else "n/a"
        add(f"| `{name}` | {arity} | {'yes' if row['in_form'] else 'no'} |")
    add("")

    add("## Zero-input operators carrying run data by path")
    add("")
    add("These are the third-path violations: `inputs_arity: 0` and the data arrives")
    add("through a parameter. Each gets real ports; the data path parameter is removed.")
    add("")
    add("| Operator | Data parameters | Planned ports | Target arity |")
    add("| --- | --- | --- | ---: |")
    for name in sorted(zero_input):
        row = zero_input[name]
        params = [p for p in row["paths"] if category(p) == "data"]
        planned = "; ".join(f"`{p}` -> {planned_kind(p)}" for p in params)
        arity = max(len(params), row["arity"] or 0)
        add(f"| `{name}` | {', '.join(f'`{p}`' for p in params)} | {planned} | {arity} |")
    add("")

    add("## Ported operators with a data path override")
    add("")
    add("These already take a port but still accept the same data as a bare path. The")
    add("override is removed so the port is the only entrance.")
    add("")
    add("| Operator | Inputs arity | Data parameters to remove |")
    add("| --- | ---: | --- |")
    for name in sorted(overrides):
        row = overrides[name]
        params = [p for p in row["paths"] if category(p) == "data"]
        add(f"| `{name}` | {row['arity']} | {', '.join(f'`{p}`' for p in params)} |")
    add("")

    add("## Preserved path parameters")
    add("")
    add("Executable, weights, resource and output paths are legitimate parameters. They")
    add("are annotated with `x-operon-role` in the sidecar (batch 5) and are exempt from")
    add("the transport check.")
    add("")
    for role in ("tool", "weights", "resource", "output"):
        params = role_params[role]
        add(f"### `{role}` ({counts[role]} occurrences, {len(params)} distinct names)")
        add("")
        add("| Parameter | Operators |")
        add("| --- | --- |")
        for param in sorted(params):
            ops = params[param]
            sample = ", ".join(f"`{n}`" for n in ops[:4])
            more = "" if len(ops) <= 4 else f" (+{len(ops) - 4} more)"
            add(f"| `{param}` | {sample}{more} |")
        add("")

    add("## Readers")
    add("")
    add("Eleven readers emit `file_artifact` and declare no inputs: Alignment, BamFile,")
    add("ChainFile, Cooler, FastaFile, Fastq, GffFile, Pairs, SbmlFile, TsvFile and")
    add("VcfFile. A generic `FileReader` is added in batch 4 so that formats without a")
    add("typed reader (MD trajectories, PDBQT, result bundles) have a file source; the")
    add("reader count moves from 109 to 110 because of it.")
    add("")

    add("## Manual review")
    add("")
    add("These sidecars build their definition indirectly, so the port scan cannot read")
    add("them with `ast.literal_eval`. Each is inspected by hand in the batch that")
    add("touches it:")
    add("")
    for item in unparsed:
        add(f"- {item}")
    add("")

    add("## Registry checks derived from this inventory")
    add("")
    add("1. An operator output may be `file_artifact` only for the three whitelisted")
    add("   terminals; every other operator output is `form` or empty.")
    add("2. Every remaining `*_path` parameter carries `x-operon-role` with one of")
    add("   `tool`, `weights`, `resource`, `output`; a run-data path is an error.")
    add("3. A reader declares no inputs.")
    add("")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {args.out.relative_to(ROOT)}")
    print(
        "operators={ops} parsed={parsed} unparsed={unparsed} emit_file={emit} "
        "consume_file={consume} data_ops={data} zero_input={zero} overrides={over} "
        "tool={tool} weights={weights} resource={resource} output={output} data={data_params}".format(
            ops=len(rows) + len(unparsed),
            parsed=len(rows),
            unparsed=len(unparsed),
            emit=len(emitters),
            consume=len(consumers),
            data=len(data_ops),
            zero=len(zero_input),
            over=len(overrides),
            tool=counts["tool"],
            weights=counts["weights"],
            resource=counts["resource"],
            output=counts["output"],
            data_params=counts["data"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
