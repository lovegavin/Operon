"""Download the real open datasets for T21 into input/.

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
  "name": "UCI Adult",
  "url": "https://archive.ics.uci.edu/ml/machine-learning-databases/adult/adult.data",
  "format": "CSV",
  "size": "4 MB",
  "license": "CC BY 4.0",
  "citation": "Dua 2019"
 },
 {
  "name": "UCI Wine",
  "url": "https://archive.ics.uci.edu/ml/machine-learning-databases/wine/wine.data",
  "format": "CSV",
  "size": "20 KB",
  "license": "CC BY 4.0",
  "citation": "Dua 2019"
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
