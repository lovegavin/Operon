"""Shared interval helpers for peak panels."""
import numpy as np
from src.core import StepError, Form
from ._peak_common import decode_column, numeric_column, metric_form

def intervals(form):
    chrom = decode_column(form, "field", "chrom")
    start = numeric_column(form, "field", "start")
    end = numeric_column(form, "field", "end")
    return [(str(c), int(s), int(e)) for c, s, e in zip(chrom, start, end) if np.isfinite(s) and np.isfinite(e)]

def feature_rows(form, types=("gene",)):
    seq = decode_column(form, "field", "seqid") if "seqid" in form.labels.get("field", {}) else decode_column(form, "field", "chrom")
    typ = decode_column(form, "field", "type")
    start = numeric_column(form, "field", "start")
    end = numeric_column(form, "field", "end")
    strand = decode_column(form, "field", "strand")
    rows = []
    for i in range(form.data.shape[0]):
        if str(typ[i]) not in types:
            continue
        rows.append((str(seq[i]), int(start[i]), int(end[i]), str(strand[i])))
    return rows

def overlap(a, b):
    return a[0] == b[0] and a[1] < b[2] and b[1] < a[2]

def win_form(rows):
    if not rows:
        raise StepError("peak density: no windows")
    return Form(data=np.array([[float(x[2]), float(x[3]), float(x[4])] for x in rows]),
                dims=["window", "statistic"],
                labels={"window": {f"{x[0]}:{x[1]}": i for i, x in enumerate(rows)},
                        "statistic": {"n_peaks":0, "covered_bp":1, "density_per_mb":2}})

__all__ = ["intervals", "feature_rows", "overlap", "win_form", "metric_form", "decode_column", "numeric_column"]
