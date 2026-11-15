"""CA RMSD of each design prediction against the parent complex after superposing chain B."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

PARENT = Path(r"D:\OperonTest517rc7\workspace\design_loop\round3\complex_free_d1.pdb")


def ca_atoms(path: Path) -> dict[str, list[tuple[int, np.ndarray]]]:
    chains: dict[str, list[tuple[int, np.ndarray]]] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith("ATOM") or line[12:16].strip() != "CA":
            continue
        chain = line[21]
        resseq = int(line[22:26])
        xyz = np.array([float(line[30:38]), float(line[38:46]), float(line[46:54])])
        chains.setdefault(chain, []).append((resseq, xyz))
    return chains


def paired(a: list[tuple[int, np.ndarray]], b: list[tuple[int, np.ndarray]]) -> tuple[np.ndarray, np.ndarray]:
    bmap = {res: xyz for res, xyz in b}
    left, right = [], []
    for res, xyz in a:
        if res in bmap:
            left.append(xyz)
            right.append(bmap[res])
    return np.asarray(left), np.asarray(right)


def kabsch(mobile: np.ndarray, target: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    mc = mobile - mobile.mean(axis=0)
    tc = target - target.mean(axis=0)
    cov = mc.T @ tc
    u, _s, vt = np.linalg.svd(cov)
    d = np.sign(np.linalg.det(u @ vt))
    rot = u @ np.diag([1.0, 1.0, d]) @ vt
    rotated = mc @ rot
    rmsd = float(np.sqrt(((rotated - tc) ** 2).sum(axis=1).mean()))
    return rot, mobile.mean(axis=0) - target.mean(axis=0) @ rot.T, rmsd


def measure(child: Path, parent_chains: dict[str, list[tuple[int, np.ndarray]]]) -> dict[str, float]:
    chains = ca_atoms(child)
    pb, cb = paired(parent_chains["B"], chains.get("B", []))
    rot, _trans, rmsd_b = kabsch(cb, pb)
    pa, ca = paired(parent_chains["A"], chains.get("A", []))
    if len(ca):
        moved = (ca - ca.mean(axis=0)) @ rot
        target = pa - pa.mean(axis=0)
        rmsd_a = float(np.sqrt(((moved - target) ** 2).sum(axis=1).mean()))
    else:
        rmsd_a = float("nan")
    return {"rmsd_b": round(rmsd_b, 2), "rmsd_a": round(rmsd_a, 2), "n_b": len(pb), "n_a": len(ca)}


def stage_pdb(job_dir: Path) -> Path | None:
    for path in (job_dir / "runs").glob("*/steps/01_boltz_complex_confidence.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        files = data.get("result_files") or []
        if not files:
            return None
        raw = files[0].get("path") or ""
        cleaned = raw[4:] if raw.startswith("\\\\?\\") else raw
        pdb = Path(cleaned)
        return pdb if pdb.is_file() else None
    return None


def main(argv: list[str]) -> None:
    base = Path(argv[1])
    parent_chains = ca_atoms(PARENT)
    rows = []
    for job_dir in sorted((base / "results").glob("req-*")):
        pdb = stage_pdb(job_dir)
        if pdb is None:
            rows.append({"job": job_dir.name, "status": "no-pdb"})
            continue
        record = {"job": job_dir.name, **measure(pdb, parent_chains)}
        rows.append(record)
        print(json.dumps(record))
    out = base / (base.name + "_rmsd.json")
    out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print("wrote", out)


if __name__ == "__main__":
    main(sys.argv)
