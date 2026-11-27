"""Download the real open datasets for T07 into input/.

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
  "name": "1000G chr22 VCF",
  "url": "https://ftp.1000genomes.ebi.ac.uk/vol1/ftp/release/20130502/ALL.chr22.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz",
  "format": "VCF",
  "size": "1.1 GB",
  "license": "1000G open",
  "citation": "Auton 2015"
 },
 {
  "name": "GIANT height",
  "url": "https://portals.broadinstitute.org/collaboration/giant/images/c/c8/GIANT_HEIGHT_Wood_et_al_2014_publicrelease_HapMapCeuFreq.txt.gz",
  "format": "TSV",
  "size": "10 MB",
  "license": "academic use",
  "citation": "Wood 2014"
 },
 {
  "name": "1000G panel",
  "url": "https://ftp.1000genomes.ebi.ac.uk/vol1/ftp/release/20130502/integrated_call_samples_v3.20130502.ALL.panel",
  "format": "TSV",
  "size": "100 KB",
  "license": "1000G open",
  "citation": "1000G"
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
