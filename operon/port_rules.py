"""Port contract rules the registry enforces for SDK v3 operators and readers.

Run data moves through declared ports.  A ``*_path`` parameter may still name
an executable, model weights, a reference database or an output directory, but
it may not be the only way run data enters an operator.  Operators emit
``file_artifact`` only when a form would lose information; every exception
carries its reason here, so the whitelist cannot drift silently.
"""
from __future__ import annotations

# Path parameters that name an external executable or its runner script.
TOOL = frozenset({
    "mkdssp_path", "dssp_path", "vina_path", "proteinmpnn_path", "ligandmpnn_path",
    "foldseek_path", "rnafold_path", "rnasubopt_path", "rnaduplex_path", "rnacofold_path",
    "hmmscan_path", "cmscan_path", "minimap2_path", "fpocket_path", "pdb2pqr_path",
    "prodigal_path", "amrfinder_path", "antismash_path", "colabfold_path", "openfold_path",
    "rfdiffusion_path", "mmseqs_path", "flye_path", "trnascan_path", "quast_path", "minced_path", "runner_path",
})
# Model weights or parameter files shipped as resources.
WEIGHTS = frozenset({"weights_path", "model_path", "params_path"})
# Reference databases and annotation bundles shipped as resources.
RESOURCE = frozenset({"hmm_path", "obo_path", "gaf_path", "database_path"})
# Directory a step writes into; never an input.
OUTPUT = frozenset({"output_path", "flex_output_path"})
# Run data: the parameters that must not be the transport channel.
DATA = frozenset({
    "structure_path", "fasta_path", "trajectory_path", "topology_path", "query_path",
    "target_path", "reference_path", "native_path", "complex_path", "ligand_path",
    "pose_path", "affinity_path", "boltz_path", "flex_path", "receptor_path",
})
# Data that cannot be represented as a form: binary trajectories, docked poses,
# YAML/JSON result bundles.  Everything else in DATA becomes a form port.
FILE_DATA = frozenset({
    "trajectory_path", "topology_path", "affinity_path", "boltz_path", "complex_path",
    "ligand_path", "pose_path", "flex_path", "receptor_path",
})
# Emitters that stay `file_artifact` because their product cannot be a lossless
# form.  An operator that emits a file must be listed here, with its reason.
FILE_EMITTER_REASONS: dict[str, str] = {
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
# Emitters that no longer declare a file output.  Kept explicit so a converted
# operator cannot quietly start emitting files again.
CONVERTED_EMITTERS = frozenset({"msa_trim"})


def path_role(name: str) -> str:
    """Classify a ``*_path`` parameter by the role it plays."""
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


def is_file_port(entry: dict) -> bool:
    """True when a data-format entry carries a file rather than a form."""
    logical = str(entry.get("logical_type") or "")
    reps = [str(r) for r in (entry.get("representations") or [])]
    return "file" in logical or any("file" in r for r in reps)


def path_parameters(descriptor: dict) -> list[str]:
    schema = descriptor.get("parameters_schema") or {}
    properties = schema.get("properties") or {}
    return sorted(name for name in properties if name.endswith("_path"))


def check_descriptor(descriptor: dict) -> list[str]:
    """Return the port-contract violations of one compiled descriptor."""
    issues: list[str] = []
    identifier = str(descriptor.get("id") or "<unnamed>")
    formats = descriptor.get("data_formats") or {}
    kind = descriptor.get("kind")
    inputs = formats.get("inputs") or []
    outputs = formats.get("outputs") or []
    arity = descriptor.get("inputs_arity")
    if kind == "reader":
        if inputs:
            issues.append(f"reader {identifier} declares inputs; a reader starts a chain and must declare none")
        if arity not in (None, 0):
            issues.append(f"reader {identifier} declares inputs_arity={arity}; readers take no inputs")
        return issues
    emits_file = any(is_file_port(entry) for entry in outputs)
    if emits_file and identifier not in FILE_EMITTER_REASONS:
        issues.append(
            f"operator {identifier} emits file_artifact without a recorded necessity; "
            "add it to operon/port_rules.py FILE_EMITTER_REASONS or emit a form"
        )
    if identifier in FILE_EMITTER_REASONS and not emits_file:
        issues.append(
            f"operator {identifier} is listed as a file emitter but no longer emits file_artifact; "
            "drop it from FILE_EMITTER_REASONS"
        )
    if identifier in CONVERTED_EMITTERS and emits_file:
        issues.append(f"operator {identifier} was converted to a form output but emits file_artifact again")
    for name in path_parameters(descriptor):
        role = path_role(name)
        if role == "unknown":
            issues.append(
                f"operator {identifier} declares unclassified path parameter {name!r}; "
                "classify it in operon/port_rules.py"
            )
            continue
        if role != "data":
            continue
        if not arity:
            issues.append(
                f"operator {identifier} carries run data in {name!r} but declares no input port; "
                "give it a form or file_artifact port"
            )
    return issues
