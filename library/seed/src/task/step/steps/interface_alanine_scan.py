"""Computational alanine scanning on a protein interface with MM/GBSA."""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step import Step
from src.task.step.steps.interface_mmgbsa_delta import mmgbsa_terms, parse_chains
from src.task.step.steps.structure_openmm_energy import write_pdb

_BACKBONE = {"N", "CA", "C", "O", "OXT", "CB"}


def interface_contacts(
    pdb_path: Path,
    binder: tuple[str, ...],
    target: tuple[str, ...],
    cutoff: float,
    mutation_side: str = "target",
) -> list[tuple[str, int]]:
    """Return interface residues to mutate on the requested side."""

    from openmm.app import PDBFile

    pdb = PDBFile(str(pdb_path))
    positions = np.asarray(pdb.positions.value_in_unit(pdb.positions.unit), dtype=np.float64) * 10.0
    atoms = list(pdb.topology.atoms())
    heavy = [atom.element.symbol != "H" for atom in atoms]
    binder_rows = [
        index
        for index, atom in enumerate(atoms)
        if heavy[index] and atom.residue.chain.id in binder
    ]
    target_rows = [
        index
        for index, atom in enumerate(atoms)
        if heavy[index] and atom.residue.chain.id in target
    ]
    if not binder_rows:
        raise StepError("interface_alanine_scan: the binder side has no heavy atoms")
    if not target_rows:
        raise StepError("interface_alanine_scan: the target side has no heavy atoms")

    hits: set[tuple[str, int]] = set()

    def collect(query, reference) -> None:
        reference_positions = positions[np.asarray(reference, dtype=np.int64)]
        for index in query:
            distances = np.linalg.norm(reference_positions - positions[index], axis=1)
            if np.any(distances <= cutoff):
                atom = atoms[index]
                hits.add((atom.residue.chain.id, atom.residue.index))

    if mutation_side in ("target", "both"):
        collect(target_rows, binder_rows)
    if mutation_side in ("binder", "both"):
        collect(binder_rows, target_rows)

    labels: list[tuple[str, int]] = []
    for atom in atoms:
        key = (atom.residue.chain.id, atom.residue.index)
        if key in hits and key not in labels:
            labels.append(key)
    return labels


def residue_label(atoms, residue_index: int) -> tuple[str, str, int]:
    for atom in atoms:
        if atom.residue.index == residue_index:
            return atom.residue.chain.id, atom.residue.name, int(atom.residue.id)
    raise StepError(f"interface_alanine_scan: residue index {residue_index} is not in the topology")


def mutate_to_alanine(text: str, chain: str, number: int) -> str:
    """Truncate one residue to ALA (N/CA/C/O/CB) and drop its hydrogens."""

    output: list[str] = []
    changed = False
    for line in text.splitlines():
        if line.startswith(("ATOM", "HETATM")) and line[21] == chain and line[22:26].strip() == str(number):
            name = line[12:16].strip()
            element = line[76:78].strip().upper() or name[:1].upper()
            if element == "H":
                continue
            if name not in _BACKBONE:
                continue
            changed = True
            line = f"{line[:17]}ALA{line[20:]}"
        output.append(line)
    if not changed:
        raise StepError(f"interface_alanine_scan: residue {chain}:{number} is not in the structure file")
    return "\n".join(output) + "\n"


def scan_residues(pdb_path: Path, text: str, binder: tuple[str, ...], target: tuple[str, ...], cutoff: float, max_residues: int, ph: float, forcefield: str, implicit: str, mutation_side: str = "target") -> list[dict]:
    from openmm.app import PDBFile

    pdb = PDBFile(str(pdb_path))
    atoms = list(pdb.topology.atoms())
    contacts = interface_contacts(pdb_path, binder, target, cutoff, mutation_side)
    scored = []
    seen: set[tuple[str, int]] = set()
    for chain, residue_index in contacts:
        key = (chain, residue_index)
        if key in seen:
            continue
        seen.add(key)
        residue_chain, name, number = residue_label(atoms, residue_index)
        if name == "ALA":
            continue
        side = "binder" if residue_chain in binder else "target"
        scored.append((number, residue_chain, name, side))
    scored.sort(key=lambda item: (item[0], item[1]))
    scored = scored[:max_residues]
    if not scored:
        raise StepError("interface_alanine_scan: no non-alanine residue lies within the interface cutoff")

    workdir = Path(tempfile.mkdtemp(prefix="alanine_"))
    wt = mmgbsa_terms(pdb_path, forcefield_name=forcefield, implicit=implicit, ph=ph, binder=binder, target=target)
    wt_delta = wt["complex"]["total"] - wt["binder"]["total"] - wt["target"]["total"]
    results: list[dict] = []
    for position, (number, chain, name, side) in enumerate(scored, start=1):
        mutant_text = mutate_to_alanine(text, chain, number)
        mutant_path = workdir / f"mutant_{chain}{number}.pdb"
        mutant_path.write_text(mutant_text)
        mutant = mmgbsa_terms(mutant_path, forcefield_name=forcefield, implicit=implicit, ph=ph, binder=binder, target=target)
        mutant_delta = mutant["complex"]["total"] - mutant["binder"]["total"] - mutant["target"]["total"]
        gly_to_ala = name == "GLY"
        results.append(
            {
                "chain": chain,
                "number": number,
                "residue": name,
                "side": side,
                "wt_delta": wt_delta,
                "mutant_delta": mutant_delta,
                "delta_delta": mutant_delta - wt_delta,
                "flag": "gly_to_ala" if gly_to_ala else "",
                "excluded_reason": "Glycine has no side chain; the Ala mutation introduces a methyl group "
                "that can clash at a packed interface and is not a comparable alanine substitution."
                if gly_to_ala
                else "",
                "excluded_from_ranking": bool(gly_to_ala),
            }
        )
    return results



def _rank(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    position = 0
    while position < len(order):
        end = position
        while end + 1 < len(order) and values[order[end + 1]] == values[order[position]]:
            end += 1
        average = (position + end) / 2.0 + 1.0
        for index in order[position : end + 1]:
            ranks[index] = average
        position = end + 1
    return ranks


def _spearman(left: list[float], right: list[float]) -> float:
    x = _rank(left)
    y = _rank(right)
    mx = sum(x) / len(x)
    my = sum(y) / len(y)
    numerator = sum((a - mx) * (b - my) for a, b in zip(x, y))
    denominator = (
        sum((a - mx) ** 2 for a in x) * sum((b - my) ** 2 for b in y)
    ) ** 0.5
    return numerator / denominator if denominator else 0.0


def copy_replicate_quality(rows: list[dict]) -> tuple[dict, list[str]]:
    """Compare the same residue numbering across crystal copies, when present."""

    warnings: list[str] = []
    pairs: list[dict] = []
    by_side: dict[str, list[dict]] = {}
    for row in rows:
        by_side.setdefault(str(row["side"]), []).append(row)
    for side, side_rows in by_side.items():
        chains = sorted({str(row["chain"]) for row in side_rows})
        if len(chains) < 2:
            continue
        values = {
            chain: {int(row["number"]): float(row["delta_delta"]) for row in side_rows if row["chain"] == chain}
            for chain in chains
        }
        for first, second in zip(chains, chains[1:]):
            common = sorted(set(values[first]) & set(values[second]))
            if len(common) < 3:
                continue
            left = [values[first][number] for number in common]
            right = [values[second][number] for number in common]
            rho = _spearman(left, right)
            nonzero = [(a, b) for a, b in zip(left, right) if a != 0.0 and b != 0.0]
            conflict = sum(1 for a, b in nonzero if (a > 0.0) != (b > 0.0)) / len(nonzero) if nonzero else 1.0
            report = {
                "side": side,
                "chains": [first, second],
                "n_common": len(common),
                "spearman": rho,
                "sign_conflict_fraction": conflict,
                "warning": rho < 0.5 or conflict > 0.2,
            }
            pairs.append(report)
            if report["warning"]:
                warnings.append(
                    f"Copy-replicate disagreement on the {side} side ({first} vs {second}): "
                    f"Spearman {rho:.3f}, sign conflict {conflict:.1%}; do not report hotspots."
                )
    if not pairs:
        return {
            "available": False,
            "reason": "Fewer than two chains with at least three common residue numbers were scored.",
            "pairs": [],
        }, warnings
    return {"available": True, "pairs": pairs}, warnings


class InterfaceAlanineScanStep(Step):
    provider = "operon-core"
    parameters_file = "interface_alanine_scan.InterfaceAlanineScanStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "interface_alanine_scan",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Interface alanine scan",
        "description": "Computational alanine scanning of interface residues with single-point MM/GBSA energy differences.",
        "category": "Structure",
        "icon": "BatteryFull",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [{"param": "atom_dim"}, {"param": "field_dim"}],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                }
            ],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "dims": [{"param": "mutation_dim", "default": "mutation"}, "statistic"], "info_open": True, "axis_info_open": False, "labels": {"statistic": ["wt_delta_kj", "mutant_delta_kj", "delta_delta_kj"]}}},
            "outputs": [],
        },
        "resources": {"memory_modes": ["full"], "environment": "openmm81", "estimate": "estimate_memory"},
        "dependencies": ["openmm==8.1.1", "numpy==1.26.4"],
        "dependency_imports": ["openmm"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs):
        params = ctx.step_params
        binder = parse_chains(params.get("binder_chains", ""), "binder_chains")
        target = parse_chains(params.get("target_chains", ""), "target_chains")
        overlap = set(binder) & set(target)
        if overlap:
            raise StepError(f"interface_alanine_scan: chain(s) {sorted(overlap)} are in both sides")
        form = inputs[0]
        if form.data.size == 0:
            raise StepError("interface_alanine_scan: the structure form is empty")
        cutoff = float(params.get("cutoff", 4.5))
        if not 1.0 <= cutoff <= 12.0:
            raise StepError("interface_alanine_scan: cutoff must be between 1 and 12 angstrom")
        mutation_side = str(params.get("mutation_side", "target")).strip().lower()
        if mutation_side not in ("target", "binder", "both"):
            raise StepError("interface_alanine_scan: mutation_side must be target, binder or both")
        max_residues = int(params.get("max_residues", 10))
        if max_residues < 1:
            raise StepError("interface_alanine_scan: max_residues must be at least 1")
        ph = float(params.get("ph", 7.0))
        if not 0.0 < ph < 14.0:
            raise StepError("interface_alanine_scan: ph must be between 0 and 14")
        workdir = Path(tempfile.mkdtemp(prefix="alanine_scan_"))
        pdb_path = workdir / "complex.pdb"
        write_pdb(form, str(params.get("atom_dim", "atom")), str(params.get("field_dim", "field")), pdb_path)
        text = pdb_path.read_text()
        rows = scan_residues(
            pdb_path,
            text,
            binder,
            target,
            cutoff,
            max_residues,
            ph,
            str(params.get("forcefield", "amber14-all.xml")),
            str(params.get("implicit_model", "implicit/gbn2.xml")),
            mutation_side,
        )
        mutation_dim = str(params.get("mutation_dim", "mutation"))
        data = np.array(
            [[row["wt_delta"], row["mutant_delta"], row["delta_delta"]] for row in rows],
            dtype=np.float32,
        )
        labels = {f"{row['chain']}:{row['number']}:{row['residue']}": index for index, row in enumerate(rows)}
        copy_replicates, copy_warnings = copy_replicate_quality(rows)
        excluded = [row for row in rows if row.get("excluded_from_ranking")]
        excluded_note = []
        if excluded:
            excluded_note = [
                f"{row['chain']}:{row['number']}:{row['residue']} (Gly to Ala) is excluded from ranking: "
                "glycine has no side chain and the mutation is not a comparable alanine substitution."
                for row in excluded
            ]
        info = {
            "n_mutations": len(rows),
            "wt_delta_kj": rows[0]["wt_delta"],
            "binder_chains": list(binder),
            "target_chains": list(target),
            "cutoff": cutoff,
            "max_residues": max_residues,
            "mutation_side": mutation_side,
            "protocol": {
                "single_point": True,
                "entropy_included": False,
                "ensemble": False,
                "calibrated": False,
                "energy_units": "kJ/mol",
                "delta_delta_sign": "mutant - wild_type",
            },
            "copy_replicates": copy_replicates,
            "quality": {
                "single_point": True,
                "entropy_included": False,
                "ensemble": False,
                "calibrated": False,
                "gly_to_ala_excluded": len(excluded),
            },
            "warnings": [
                "Single-point MM/GBSA without entropy, ensemble averaging or calibration; "
                "values are not calibrated binding affinities and must not be reported as hotspots.",
                *excluded_note,
                *copy_warnings,
            ],
            "mutations": [
                {key: row[key] for key in ("chain", "number", "residue", "side", "delta_delta",
                                           "flag", "excluded_reason", "excluded_from_ranking")}
                for row in rows
            ],
        }
        output = Form(
            data=data,
            dims=[mutation_dim, "statistic"],
            labels={mutation_dim: labels, "statistic": {"wt_delta_kj": 0, "mutant_delta_kj": 1, "delta_delta_kj": 2}},
            info={"missing_code": np.nan, **info},
        )
        ctx[str(params.get("output", "scan"))] = output
        self._export_summary = {
            "dims": list(output.dims),
            "labels": {name: dict(mapping) for name, mapping in output.labels.items()},
            "info": info,
        }
