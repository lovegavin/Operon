#!/usr/bin/env python3
"""T02 GLP-1R VHH task: pure-stdlib geometry / complexity helpers.

Subcommands
-----------
  models  <pdb>              list MODEL blocks, chains and residue counts
  geom    <pdb>              coordinate stats + CA-CA statistics (per model)
  complex <pdb>              inter-chain heavy-atom minimum distance, interface
                             residues (default 8 A), heavy-atom pairs, per model
  seq     <fasta>            length / max residue fraction / longest homopolymer run
  fasta1  <out> <name> <seq> write a single-record FASTA
  fasta2  <out> <n1> <s1> <n2> <s2>   write a two-record FASTA

All output is JSON on stdout.
"""
import json
import math
import sys
from collections import Counter, OrderedDict

WATER = {"HOH", "WAT", "DOD"}
HYDROGEN_LIKE = {"H", "D"}


def read_models(path):
    models = []
    cur = None
    with open(path, "r", errors="replace") as fh:
        for line in fh:
            rec = line[:6]
            if rec.startswith("MODEL"):
                parts = line.split()
                cur = {"model": int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else len(models) + 1,
                       "atoms": []}
            elif rec.startswith("ENDMDL"):
                if cur is not None:
                    models.append(cur)
                    cur = None
            elif rec.startswith("ATOM") or rec.startswith("HETATM"):
                if cur is None:
                    cur = {"model": 1, "atoms": []}
                try:
                    name = line[12:16].strip()
                    alt = line[16]
                    resn = line[17:20].strip()
                    chain = line[21]
                    resi = int(line[22:26])
                    icode = line[26].strip()
                    x = float(line[30:38])
                    y = float(line[38:46])
                    z = float(line[46:54])
                except (ValueError, IndexError):
                    continue
                if alt not in (" ", "A", ""):
                    continue
                if resn in WATER:
                    continue
                elem = line[76:78].strip().upper() or name[0].upper()
                cur["atoms"].append({
                    "name": name, "resn": resn, "chain": chain, "resi": resi,
                    "icode": icode, "xyz": (x, y, z), "elem": elem,
                    "het": rec.startswith("HETATM"),
                })
    if cur is not None:
        models.append(cur)
    return models


def heavy(atoms):
    return [a for a in atoms if a["elem"] not in HYDROGEN_LIKE]


def chain_map(atoms):
    out = OrderedDict()
    for a in atoms:
        out.setdefault(a["chain"], []).append(a)
    return out


def coord_stats(atoms):
    xs = [a["xyz"][0] for a in atoms]
    ys = [a["xyz"][1] for a in atoms]
    zs = [a["xyz"][2] for a in atoms]
    return {
        "n_atoms": len(atoms),
        "min": [min(xs), min(ys), min(zs)],
        "max": [max(xs), max(ys), max(zs)],
        "range": [max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)],
    }


def ca_residues(atoms):
    cas = []
    for a in atoms:
        if a["name"] == "CA":
            cas.append(a)
    return cas


def consec_ca_stats(atoms):
    cas = ca_residues(atoms)
    ds = []
    for a, b in zip(cas, cas[1:]):
        if a["chain"] != b["chain"]:
            continue
        d = dist(a["xyz"], b["xyz"])
        ds.append(d)
    if not ds:
        return {"n": 0}
    return {"n": len(ds), "mean": sum(ds) / len(ds), "min": min(ds), "max": max(ds)}


def dist(p, q):
    return math.sqrt((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 + (p[2] - q[2]) ** 2)


def interface(atoms_a, atoms_b, cutoff):
    """Return min distance, pair count and interface residues (>=1 pair within cutoff)."""
    best = float("inf")
    best_pair = None
    pairs = 0
    res_a, res_b = {}, {}
    for a in atoms_a:
        ax, ay, az = a["xyz"]
        for b in atoms_b:
            bx, by, bz = b["xyz"]
            dx = ax - bx
            dy = ay - by
            dz = az - bz
            d2 = dx * dx + dy * dy + dz * dz
            if d2 < best:
                best = d2
                best_pair = (a, b)
            if d2 <= cutoff * cutoff:
                pairs += 1
                ra = (a["chain"], a["resi"], a["resn"])
                rb = (b["chain"], b["resi"], b["resn"])
                res_a.setdefault(ra, set()).add(rb)
                res_b.setdefault(rb, set()).add(ra)
    out = {
        "min_distance": math.sqrt(best) if best < float("inf") else None,
        "min_pair": None,
        "heavy_atom_pairs_within_cutoff": pairs,
        "cutoff": cutoff,
        "n_iface_res_a": len(res_a),
        "n_iface_res_b": len(res_b),
        "iface_res_a": ["%s%s%s" % (k[0], k[1], "" if k[2] == "UNK" else "") for k in sorted(res_a)],
        "iface_res_b": ["%s%s" % (k[0], k[1]) for k in sorted(res_b)],
        "iface_res_a_detail": [{"chain": k[0], "resi": k[1], "resn": k[2],
                                "n_partners": len(v)} for k, v in sorted(res_a.items())],
        "iface_res_b_detail": [{"chain": k[0], "resi": k[1], "resn": k[2],
                                "n_partners": len(v)} for k, v in sorted(res_b.items())],
    }
    if best_pair:
        a, b = best_pair
        out["min_pair"] = {"a": {"chain": a["chain"], "resi": a["resi"], "resn": a["resn"], "name": a["name"]},
                           "b": {"chain": b["chain"], "resi": b["resi"], "resn": b["resn"], "name": b["name"]}}
    return out


def cmd_models(path):
    models = read_models(path)
    out = []
    for m in models:
        cm = chain_map(m["atoms"])
        out.append({"model": m["model"], "n_atoms": len(m["atoms"]),
                    "chains": {c: {"n_atoms": len(v),
                                   "n_res": len({(a["resi"], a["icode"]) for a in v}),
                                   "res_range": [min(a["resi"] for a in v), max(a["resi"] for a in v)]}
                               for c, v in cm.items()}})
    return {"path": path, "n_models": len(models), "models": out}


def cmd_geom(path):
    models = read_models(path)
    out = []
    for m in models:
        hv = heavy(m["atoms"])
        cm = chain_map(hv)
        out.append({
            "model": m["model"],
            "coord": coord_stats(hv),
            "ca_consecutive": {c: consec_ca_stats(v) for c, v in cm.items()},
            "n_res": {c: len({(a["resi"], a["icode"]) for a in v}) for c, v in cm.items()},
        })
    return {"path": path, "n_models": len(models), "models": out}


def cmd_complex(path, cutoff=8.0):
    models = read_models(path)
    out = []
    for m in models:
        hv = heavy(m["atoms"])
        cm = chain_map(hv)
        chains = sorted(cm)
        entry = {"model": m["model"], "chains": {c: len({(a["resi"], a["icode"]) for a in v}) for c, v in cm.items()}}
        if len(chains) < 2:
            entry["error"] = "fewer than two chains"
            out.append(entry)
            continue
        # larger chain = target (101 res), smaller = binder (58 res)
        chains_sorted = sorted(chains, key=lambda c: -len({(a["resi"], a["icode"]) for a in cm[c]}))
        target, binder = chains_sorted[0], chains_sorted[1]
        entry["target_chain"] = target
        entry["binder_chain"] = binder
        entry["target_n_res"] = len({(a["resi"], a["icode"]) for a in cm[target]})
        entry["binder_n_res"] = len({(a["resi"], a["icode"]) for a in cm[binder]})
        entry["binder_minus_target"] = interface(cm[target], cm[binder], cutoff)
        entry["binder_ca_consecutive"] = consec_ca_stats(cm[binder])
        entry["target_ca_consecutive"] = consec_ca_stats(cm[target])
        out.append(entry)
    mins = [e["binder_minus_target"]["min_distance"] for e in out if "binder_minus_target" in e]
    return {"path": path, "n_models": len(models), "cutoff": cutoff,
            "min_distance_overall": min(mins) if mins else None, "models": out}


def complexity(seq):
    n = len(seq)
    if n == 0:
        return {"length": 0}
    top = Counter(seq).most_common(1)[0]
    best = run = 1
    for a, b in zip(seq, seq[1:]):
        if a == b:
            run += 1
            best = max(best, run)
        else:
            run = 1
    return {"length": n, "top_residue": top[0], "top_count": top[1],
            "top_fraction": round(top[1] / n, 4), "longest_run": best,
            "low_complexity": bool(top[1] / n > 0.35 or best >= 8)}


def read_fasta(path):
    recs = []
    name, chunks = None, []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if name is not None:
                    recs.append((name, "".join(chunks)))
                name, chunks = line[1:].strip(), []
            else:
                chunks.append(line)
    if name is not None:
        recs.append((name, "".join(chunks)))
    return recs


def cmd_seq(path):
    recs = read_fasta(path)
    return {"path": path, "n_records": len(recs),
            "records": [dict(name=n, **complexity(s)) for n, s in recs]}


def main(argv):
    cmd = argv[1]
    if cmd == "models":
        print(json.dumps(cmd_models(argv[2]), indent=2))
    elif cmd == "geom":
        print(json.dumps(cmd_geom(argv[2]), indent=2))
    elif cmd == "complex":
        cutoff = float(argv[3]) if len(argv) > 3 else 8.0
        print(json.dumps(cmd_complex(argv[2], cutoff), indent=2))
    elif cmd == "seq":
        print(json.dumps(cmd_seq(argv[2]), indent=2))
    elif cmd == "fasta1":
        out, name, seq = argv[2], argv[3], argv[4]
        with open(out, "w") as fh:
            fh.write(">%s\n" % name)
            for i in range(0, len(seq), 60):
                fh.write(seq[i:i + 60] + "\n")
        print(json.dumps({"written": out, "length": len(seq)}))
    elif cmd == "fasta2":
        out = argv[2]
        pair = argv[3:]
        with open(out, "w") as fh:
            for name, seq in zip(pair[0::2], pair[1::2]):
                fh.write(">%s\n" % name)
                for i in range(0, len(seq), 60):
                    fh.write(seq[i:i + 60] + "\n")
        print(json.dumps({"written": out, "records": pair[0::2]}))
    else:
        raise SystemExit("unknown command: %s" % cmd)


if __name__ == "__main__":
    main(sys.argv)
