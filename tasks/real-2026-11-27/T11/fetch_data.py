"""Download the real open datasets for T11 into input/.

python fetch_data.py --dry-run | (no args) | --force
No synthetic substitution: failures are reported and the script exits non-zero.
"""
import argparse
import json
import pathlib
import sys
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
INPUT = HERE / "input"
DATASETS = [
 {
  "name": "PDB 1IEP",
  "url": "https://files.rcsb.org/download/1IEP.pdb",
  "format": "PDB",
  "size": "435 KB",
  "license": "PDB CC0",
  "citation": "Nagar 2002"
 },
 {
  "name": "ZINC250k",
  "url": "https://raw.githubusercontent.com/aspuru-guzik-group/chemical_vae/master/models/zinc/250k_rndm_zinc_drugs_clean_5.txt",
  "format": "SMILES",
  "size": "20 MB",
  "license": "ZINC academic",
  "citation": "Irwin 2005"
 },
 {
  "name": "RDKit 5k",
  "url": "https://raw.githubusercontent.com/rdkit/rdkit/master/Data/NCI/first_5K.smi",
  "format": "SMILES",
  "size": "190 KB",
  "license": "BSD-3",
  "citation": "RDKit"
 }
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    INPUT.mkdir(exist_ok=True)
    failed = 0
    for item in DATASETS:
        url = item["url"]
        name = url.rstrip("/").split("/")[-1].split("?")[0] or item["name"].replace(" ", "_")
        target = INPUT / name
        print(f"[{item['format']:10s}] {item['size']:10s} {item['name']}  <- {url}")
        if args.dry_run:
            continue
        if target.exists() and not args.force:
            print("   exists:", target.name, target.stat().st_size)
            continue
        try:
            with urllib.request.urlopen(url, timeout=300) as response, open(target, "wb") as handle:
                while chunk := response.read(1 << 20):
                    handle.write(chunk)
            print("   saved:", target.name, target.stat().st_size)
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print("   FAILED:", type(exc).__name__, exc)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
