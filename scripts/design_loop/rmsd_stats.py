"""Correlate iPTM with fold retention (chain-B CA RMSD) across the 16 children."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

ROOT = Path(r"D:\OperonTest517rc7\workspace\design_loop")
SCORES = {
    "round3": {
        "req-f1692f642fb99427b37411b1": 0.1131, "req-ce728273e1de036cc335b751": 0.0644,
        "req-140369776c4ab577cbcaa53a": 0.1027, "req-3d5ca43bda102a583f65108c": 0.0763,
        "req-9277c07cb5da99925e5a1c08": 0.1270, "req-bbb15a53cab273b37d2d54a2": 0.0591,
        "req-83aeb72a62a30ec82022a11d": 0.0699, "req-59f8cabf6fa8621c8fa4aeae": 0.0556,
    },
    "round4": {
        "req-c577c7bd58587ccae4cef9a3": 0.1022, "req-c5b3b1b86e202066bbaead6c": 0.0572,
        "req-df3e9ff05896ad2589f13345": 0.9037, "req-c5acbf6aab15b640f68f2dcd": 0.8865,
        "req-c28a51891d9590c4b571e509": 0.1174, "req-f2d1c4f2d4314eeed1f29c01": 0.0846,
        "req-73ffb8be6ff61d6600bf7e02": 0.1028, "req-232c9eb50eb53a01f4b74b8d": 0.0637,
    },
}


def spearman(x: np.ndarray, y: np.ndarray) -> float:
    rx = np.argsort(np.argsort(x)).astype(float)
    ry = np.argsort(np.argsort(y)).astype(float)
    return float(np.corrcoef(rx, ry)[0, 1])


def main() -> None:
    rows = []
    for rnd, scores in SCORES.items():
        data = json.loads((ROOT / rnd / "complexes" / "complexes_rmsd.json").read_text(encoding="utf-8"))
        for record in data:
            job = record.get("job")
            if job in scores:
                rows.append({"round": rnd, "job": job, "iptm": scores[job],
                             "rmsd_b": record["rmsd_b"], "rmsd_a": record["rmsd_a"]})
    iptm = np.array([r["iptm"] for r in rows])
    rmsd_b = np.array([r["rmsd_b"] for r in rows])
    rmsd_a = np.array([r["rmsd_a"] for r in rows])
    print(f"n={len(rows)} pearson(iptm,rmsdB)={np.corrcoef(iptm, rmsd_b)[0,1]:.3f} "
          f"spearman={spearman(iptm, rmsd_b):.3f}")
    print(f"pearson(iptm,rmsdA)={np.corrcoef(iptm, rmsd_a)[0,1]:.3f} spearman={spearman(iptm, rmsd_a):.3f}")
    for rnd in ("round3", "round4"):
        subset = [r for r in rows if r["round"] == rnd]
        bs = [r["rmsd_b"] for r in subset]
        print(f"{rnd}: n={len(subset)} rmsd_b min={min(bs):.2f} mean={sum(bs)/len(bs):.2f} max={max(bs):.2f}")
    below = [r for r in rows if r["rmsd_b"] < 3.0]
    print("designs within 3 A of the parent fold:", [(r['round'], r['job'], r['rmsd_b'], r['iptm']) for r in below])
    (ROOT / "rmsd_summary.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
