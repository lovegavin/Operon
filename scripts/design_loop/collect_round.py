"""Collect Boltz complex-confidence scores for any design round."""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

THREE = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C", "GLN": "Q",
    "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I", "LEU": "L", "LYS": "K",
    "MET": "M", "PHE": "F", "PRO": "P", "SER": "S", "THR": "T", "TRP": "W",
    "TYR": "Y", "VAL": "V", "MSE": "M", "SEC": "U", "PYL": "O",
}


def interface_residues(pdb: Path, cutoff: float = 8.0) -> tuple[int, float]:
    atoms = []
    for line in pdb.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith("ATOM"):
            continue
        atoms.append((
            line[21],
            int(line[22:26]),
            (float(line[30:38]), float(line[38:46]), float(line[46:54])),
        ))
    a_atoms = [x for x in atoms if x[0] == "A"]
    b_atoms = [x for x in atoms if x[0] == "B"]
    if not a_atoms or not b_atoms:
        return 0, 0.0
    limit = cutoff * cutoff
    near_a: set[tuple[str, int]] = set()
    near_b: set[tuple[str, int]] = set()
    for chain_a, res_a, (x1, y1, z1) in a_atoms:
        for chain_b, res_b, (x2, y2, z2) in b_atoms:
            dx, dy, dz = x1 - x2, y1 - y2, z1 - z2
            if dx * dx + dy * dy + dz * dz <= limit:
                near_a.add((chain_a, res_a))
                near_b.add((chain_b, res_b))
    return len(near_a) + len(near_b), 0.0


def main(argv: list[str]) -> None:
    base = Path(argv[1])
    out = Path(argv[2])
    rows = []
    for job_dir in sorted((base / "results").glob("req-*")):
        fasta = job_dir / "input" / "files"
        design = job_dir.name
        stage = None
        for path in (job_dir / "runs").glob("*/steps/01_boltz_complex_confidence.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            stage = data
            break
        record = {
            "job": design,
            "status": "complete" if stage else "pending",
            "iptm": stage.get("iptm") if stage else None,
            "n_interface": stage.get("n_interface") if stage else None,
            "mean_interface_plddt": stage.get("mean_interface_plddt") if stage else None,
            "pdb": None,
            "pdb_bytes": None,
            "contacts": None,
        }
        if stage:
            files = stage.get("result_files") or []
            if files:
                raw = files[0].get("path") or ""
                cleaned = raw[4:] if raw.startswith("\\\\?\\") else raw
                pdb = Path(cleaned)
                record["pdb"] = str(pdb)
                record["pdb_bytes"] = pdb.stat().st_size if pdb.is_file() else None
                if pdb.is_file():
                    contacts, _ = interface_residues(pdb)
                    record["contacts"] = contacts
        rows.append(record)
        print(json.dumps(record, ensure_ascii=False))
    if rows:
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        print("wrote", out)


if __name__ == "__main__":
    main(sys.argv)
