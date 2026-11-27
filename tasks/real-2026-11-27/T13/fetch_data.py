"""Download the real open datasets for T13 into input/.

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
  "name": "GENCODE v49 GTF",
  "url": "https://ftp.ebi.ac.uk/pub/databases/gencode/Gencode_human/release_49/gencode.v49.annotation.gtf.gz",
  "format": "GTF",
  "size": "50 MB",
  "license": "GENCODE open",
  "citation": "Frankish 2019"
 },
 {
  "name": "RefSeq GFF3",
  "url": "https://ftp.ncbi.nlm.nih.gov/refseq/H_sapiens/annotation/GRCh38_latest_genomic.gff.gz",
  "format": "GFF3",
  "size": "90 MB",
  "license": "NCBI public domain",
  "citation": "O'Leary 2016"
 },
 {
  "name": "GO basic OBO",
  "url": "https://release.geneontology.org/2024-11-01/ontology/go-basic.obo",
  "format": "OBO",
  "size": "35 MB",
  "license": "CC BY 4.0",
  "citation": "GO Consortium"
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
