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
# Emitters that stay `file_artifact`, each with the reason its product cannot be
# a lossless form.  A new emitter must be classified here or in CONVERTED, or the
# generator aborts, so the rule cannot drift silently.
KEEP_EMIT: dict[str, str] = {
    "align_reads": "BAM alignment; fifteen downstream operators open it by path and BAM is a streaming binary container",
    "build_contacts": "Hi-C contact store in cool/hic; `analyze_contacts` reads the binary container",
    "coding_variant_filter": "VCF interchange: headers, FILTER/INFO/FORMAT and phasing; twenty file consumers",
    "liftover_variants": "VCF interchange: headers, FILTER/INFO/FORMAT and phasing; twenty file consumers",
    "pileup_variants": "VCF interchange: headers, FILTER/INFO/FORMAT and phasing; twenty file consumers",
    "variant_consequence": "VCF interchange: headers, INFO and FORMAT; twenty file consumers",
    "vcf_concat": "VCF interchange; chained into merge by the `vcf_normalization` route",
    "vcf_filter": "VCF interchange: headers, FILTER/INFO/FORMAT and phasing; twenty file consumers",
    "vcf_merge": "VCF interchange; terminal step of the `vcf_normalization` route before export",
    "vcf_normalize": "VCF interchange; the `vcf_normalization` route feeds its output to merge",
    "consensus_sequence": "computed reference genome; `pileup_variants`, `variant_consequence` and `vcf_normalize` take a reference FASTA as a file, and genomes can exceed form memory",
    "liftover_intervals": "one input produces two BEDs (mapped/unmapped); one form port cannot carry the split, and BED rows carry per-row chromosome names",
    "alphafold2_predict": "multi-model PDB/mmCIF bundle; `export_results` has no PDB writer, so a form could not be exported back",
    "alphafold2_rank_models": "ranked copies of the same PDB bundle; no PDB writer on export",
    "alphafold2_msa_search": "A3M alignment is the deliverable for external AF2/ColabFold tooling; insertion columns have no numeric form encoding",
    "alphafold2_batch_predict": "heterogeneous summary table (names, status, paths, error text) over a prediction tree; no lossless numeric form",
}
# Emitters that no longer declare a file output.  Kept explicit so the generator
# can prove every emitter has a verdict.
CONVERTED = {"msa_trim"}


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
    add(f"| Operators still emitting `file_artifact` | {len(emitters)} |")
    add(f"| Emitters converted to `form` | {len(CONVERTED)} |")
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
    add("An emitter keeps `file_artifact` only where its product cannot be a lossless")
    add("form. `msa_trim` was the single violation and now emits a form; the other")
    add("sixteen keep a file output for the reason recorded per row.")
    add("")
    add("| Operator | Output ports | Action | Reason |")
    add("| --- | --- | --- | --- |")
    for name in sorted(emitters):
        row = emitters[name]
        if name in CONVERTED:
            raise SystemExit(f"converted emitter still declares a file output: {name}")
        if name not in KEEP_EMIT:
            raise SystemExit(f"unclassified file_artifact emitter: {name}")
        add(f"| `{name}` | {row['arity']} in / file out | keep `file_artifact` | {KEEP_EMIT[name]} |")
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
    if zero_input:
        add("These are third-path violations: `inputs_arity: 0` while run data arrives")
        add("through a parameter. Each needs a real port.")
        add("")
        add("| Operator | Data parameters | Planned ports | Target arity |")
        add("| --- | --- | --- | ---: |")
        for name in sorted(zero_input):
            row = zero_input[name]
            params = [p for p in row["paths"] if category(p) == "data"]
            planned = "; ".join(f"`{p}` -> {planned_kind(p)}" for p in params)
            arity = max(len(params), row["arity"] or 0)
            add(f"| `{name}` | {', '.join(f'`{p}`' for p in params)} | {planned} | {arity} |")
    else:
        add("None remain. Batch 4 gave every operator that carried run data by path a")
        add("declared port, so no operator relies on the retired third path.")
    add("")

    add("## Ported operators with a data path override")
    add("")
    add("These declare a port and still accept the same data as a bare path. The")
    add("override stays as an optional entrance for direct API calls and existing")
    add("tests; a workflow transports the data through the port. Removing it is a")
    add("documented follow-up, kept separate because 170 test references and several")
    add("shipped route templates still set the parameter.")
    add("")
    add("| Operator | Inputs arity | Data parameters kept as an optional override |")
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
    add("VcfFile. A generic `FileReader` supplies a file source for formats without a")
    add("typed reader (MD trajectories, PDBQT, result bundles); after batch 4 the reader")
    add("count is 110.")
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
    add("`operon/port_rules.py` enforces these rules in `registry build` and")
    add("`registry check`; a violation keeps the operator out of the catalog.")
    add("")
    add("1. An operator output may be `file_artifact` only when the operator is listed")
    add("   above with a reason; every other operator output is `form` or empty, and a")
    add("   listed emitter that stops emitting fails the check.")
    add("2. A converted emitter (`msa_trim`) may not declare a file output again.")
    add("3. Every `*_path` parameter must be classified in `operon/port_rules.py` as")
    add("   `tool`, `weights`, `resource` or `output`; an unknown name fails.")
    add("4. A run-data path (`structure_path`, `fasta_path`, `trajectory_path`, ...)")
    add("   requires at least one input port on the same operator.")
    add("5. A reader declares no inputs and no input arity.")
    add("")

    stale_keep = sorted(set(KEEP_EMIT) - set(emitters))
    if stale_keep:
        raise SystemExit(f"stale KEEP_EMIT entries: {stale_keep}")
    still_emitting = sorted(CONVERTED & set(emitters))
    if still_emitting:
        raise SystemExit(f"converted emitters still declare a file output: {still_emitting}")
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
