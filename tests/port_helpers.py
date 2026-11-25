"""Test bridge: satisfy the declared input ports from legacy path parameters.

Operators converted for 5.9.0 declare ``form`` or ``file_artifact`` ports. Older
tests passed the same data through a path parameter, which the port rule retires.
``run_legacy`` builds the port values from those parameters (Form for structure
and FASTA ports, FileArtifact for file ports), registers them on the context and
runs the real runner, so the operator sees the port it now declares.

The map below is generated from docs/design/port_contract_inventory.md by
scripts/gen_port_helpers.py (same table the registry checks use).
"""
from __future__ import annotations

from pathlib import Path

from src.core import FileArtifact

PORT_PARAMS: dict[str, list[tuple[str, str]]] = {
    'alphafold2_msa_search': [('fasta', 'fasta_path')],
    'alphafold2_predict': [('fasta', 'fasta_path')],
    'antibody_cdr_redesign': [('structure', 'structure_path')],
    'antifold_design': [('structure', 'structure_path')],
    'antifold_score': [('structure', 'structure_path')],
    'boltz_affinity_summary': [('file', 'affinity_path')],
    'esm3_inverse_folding': [('structure', 'structure_path')],
    'foldseek_align': [('structure', 'query_path'), ('structure', 'target_path')],
    'ligandmpnn_active_site_design': [('structure', 'structure_path')],
    'ligandmpnn_design': [('structure', 'structure_path')],
    'ligandmpnn_score': [('structure', 'structure_path')],
    'ligandmpnn_side_chain_packing': [('structure', 'structure_path')],
    'proteinmpnn_bias_matrix': [('structure', 'structure_path')],
    'proteinmpnn_bias_scan': [('structure', 'structure_path')],
    'proteinmpnn_design': [('structure', 'structure_path')],
    'proteinmpnn_design_cluster': [('structure', 'structure_path')],
    'proteinmpnn_design_diversity': [('structure', 'structure_path')],
    'proteinmpnn_design_profile': [('structure', 'structure_path')],
    'proteinmpnn_ensemble_score': [('structure', 'structure_path'), ('fasta', 'fasta_path')],
    'proteinmpnn_interface_design': [('structure', 'structure_path')],
    'proteinmpnn_interface_redesign': [('structure', 'structure_path')],
    'proteinmpnn_multi_model_consensus': [('structure', 'structure_path')],
    'proteinmpnn_native_recovery_scan': [('structure', 'structure_path')],
    'proteinmpnn_noise_robustness': [('structure', 'structure_path')],
    'proteinmpnn_omit_design': [('structure', 'structure_path')],
    'proteinmpnn_perplexity': [('structure', 'structure_path')],
    'proteinmpnn_position_entropy': [('structure', 'structure_path')],
    'proteinmpnn_probability_profile': [('structure', 'structure_path')],
    'proteinmpnn_score': [('structure', 'structure_path'), ('fasta', 'fasta_path')],
    'proteinmpnn_temperature_ladder': [('structure', 'structure_path')],
    'proteinmpnn_tied_design': [('structure', 'structure_path')],
    'rfdiffusion_design': [('structure', 'structure_path')],
    'structure_interface_residue_energy': [('structure', 'structure_path')],
    'structure_ligand_redock_qc': [('file', 'complex_path'), ('file', 'ligand_path'), ('file', 'pose_path')],
    'structure_md_communication_path': [('file', 'trajectory_path'), ('file', 'topology_path')],
    'structure_md_conformational_clusters': [('file', 'trajectory_path'), ('file', 'topology_path')],
    'structure_md_contact_occupancy': [('file', 'trajectory_path'), ('file', 'topology_path')],
    'structure_md_dihedral_occupancy': [('file', 'trajectory_path'), ('file', 'topology_path')],
    'structure_md_dssp_transitions': [('file', 'trajectory_path'), ('file', 'topology_path')],
    'structure_md_free_energy_landscape': [('file', 'trajectory_path'), ('file', 'topology_path')],
    'structure_md_hbond_lifetime': [('file', 'trajectory_path'), ('file', 'topology_path')],
    'structure_md_hbond_occupancy': [('file', 'trajectory_path'), ('file', 'topology_path')],
    'structure_md_interface_occupancy': [('file', 'trajectory_path'), ('file', 'topology_path')],
    'structure_md_ligand_rmsd': [('file', 'trajectory_path'), ('file', 'topology_path')],
    'structure_md_markov_states': [('file', 'trajectory_path'), ('file', 'topology_path')],
    'structure_md_pca': [('file', 'trajectory_path'), ('file', 'topology_path')],
    'structure_md_quasiharmonic_entropy': [('file', 'trajectory_path'), ('file', 'topology_path')],
    'structure_md_rotamer_states': [('file', 'trajectory_path'), ('file', 'topology_path')],
    'structure_md_salt_bridge_occupancy': [('file', 'trajectory_path'), ('file', 'topology_path')],
    'structure_md_sasa_occupancy': [('file', 'trajectory_path'), ('file', 'topology_path')],
    'structure_md_ss_occupancy': [('file', 'trajectory_path'), ('file', 'topology_path')],
    'structure_md_tica': [('file', 'trajectory_path'), ('file', 'topology_path')],
    'vina_dock': [('file', 'receptor_path'), ('file', 'ligand_path')],
    'vina_dock_batch': [('file', 'receptor_path')],
}


def _structure_form(path: Path):
    from src.reader.readers.pdb_reader import PdbReader

    return PdbReader().read(path, dims=["atom", "field"], labels={}, encoders={})


def _fasta_form(path: Path):
    from src.reader.readers.fasta_reader import FastaReader

    return FastaReader().read(path, ["sequence", "position"], {})


def _file_value(path: Path):
    return FileArtifact(path.suffix.lstrip(".").lower() or "data", {"data": str(path)}, {})


def port_values(op: str, params: dict):
    """Build port values for ``op`` from the legacy parameters, in port order."""
    values = []
    for kind, param in PORT_PARAMS.get(op, []):
        raw = params.get(param)
        if raw in (None, ""):
            return None
        path = Path(str(raw))
        if kind == "structure":
            values.append(_structure_form(path))
        elif kind == "fasta":
            values.append(_fasta_form(path))
        else:
            values.append(_file_value(path))
    return values or None


def with_ports(ctx, steps):
    """Return step specs whose empty ``inputs`` are filled from their parameters."""
    enriched = []
    for spec in steps:
        if spec.get("inputs"):
            enriched.append(spec)
            continue
        values = port_values(spec["name"], spec.get("params", {}))
        if not values:
            enriched.append(spec)
            continue
        names = []
        for index, value in enumerate(values):
            name = f"__port_{spec['name']}_{index}"
            ctx[name] = value
            names.append(name)
        enriched.append(dict(spec, inputs=names))
    return enriched


def run_legacy(ctx, steps):
    """Run a legacy params-only step list after materialising its declared ports."""
    from src.task.runner import run

    run(ctx, with_ports(ctx, steps))
