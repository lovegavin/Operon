"""Owned acceptance fixture: join main/branch TSV totals into JSON."""
import argparse
import csv
import json
import math
import os

from operon.bytecode import io_path


parser = argparse.ArgumentParser()
parser.add_argument("--in-main", required=True)
parser.add_argument("--in-branch", required=True)
parser.add_argument("--out-report", required=True)
args = parser.parse_args()
params = json.loads(io_path(os.environ["OPERON_PARAMETERS_FILE"]).read_text(encoding="utf-8"))
assert set(params) == {"bias"}
assert type(params["bias"]) in (int, float) and math.isfinite(params["bias"])
assert int(os.environ["OPERON_MEMORY_BYTES"]) > 0


def values(path):
    with io_path(path).open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        assert reader.fieldnames == ["value"]
        result = [float(row["value"]) for row in reader]
    assert result and all(math.isfinite(value) for value in result)
    return result


main, branch = values(args.in_main), values(args.in_branch)
assert len(main) == len(branch)
report = {"main": main, "branch": branch, "main_sum": sum(main), "branch_sum": sum(branch),
          "total": sum(main) + sum(branch) + params["bias"], "count": len(main)}
io_path(args.out_report).write_text(json.dumps(report, allow_nan=False), encoding="utf-8")
