"""Owned acceptance fixture: JSON numbers -> scaled one-column TSV."""
import argparse
import csv
import json
import math
import os

from operon.bytecode import io_path


parser = argparse.ArgumentParser()
parser.add_argument("--in-data", required=True)
parser.add_argument("--out-result", required=True)
args = parser.parse_args()
params = json.loads(io_path(os.environ["OPERON_PARAMETERS_FILE"]).read_text(encoding="utf-8"))
assert set(params) == {"factor"}
assert type(params["factor"]) in (int, float) and math.isfinite(params["factor"])
assert int(os.environ["OPERON_MEMORY_BYTES"]) > 0
assert int(os.environ["OMP_NUM_THREADS"]) > 0
values = json.loads(io_path(args.in_data).read_text(encoding="utf-8"))["values"]
assert values and all(type(value) in (int, float) and math.isfinite(value) for value in values)
with io_path(args.out_result).open("w", encoding="utf-8", newline="") as stream:
    writer = csv.writer(stream, delimiter="\t", lineterminator="\n")
    writer.writerow(["value"])
    for value in values:
        scaled = value * params["factor"]
        assert math.isfinite(scaled)
        writer.writerow([scaled])
