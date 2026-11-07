import numpy as np
import pytest
import pandas as pd

from src.core.encoding import LabelEncoder
from src.reader.readers._table_common import table_form
from src.task.context import Context
from src.task.step.steps.peak_annotate import PeakAnnotateStep
from src.task.step.steps.peak_overlap_matrix import PeakOverlapMatrixStep
from src.task.step.steps.peak_tss_enrichment import PeakTssEnrichmentStep
from src.task.step.steps.motif_scan_pwm import MotifScanPwmStep
from src.task.step.steps.chromatin_state_segmentation import ChromatinStateSegmentationStep


class Ctx(Context):
    def __init__(self, params):
        self.step_params = params
        self._values = {}
        self.metadata = {}

    def __setitem__(self, key, value):
        self._values[key] = value

    def __getitem__(self, key):
        return self._values[key]


def form(columns, rows, enc_cols=(), names=None):
    df = pd.DataFrame(rows, columns=columns)
    cfg = {}
    return table_form(df, dims=["row", "field"], labels={"field": "builtin"},
                      format_name="table", encoders_cfg=cfg,
                      row_labels=names or ["r%d" % i for i in range(len(df))])


def run(step, inputs, params):
    step.name = step.definition["id"]
    ctx = Ctx(dict(params))
    step.run(ctx, inputs)
    return ctx[params["output"]]


def test_peak_annotate_nearest_gene():
    peaks = form(["start", "end", "chrom"],
                 [[1000, 1500, "chr1"], [3000, 3600, "chr1"]], enc_cols=("chrom",), names=["p1", "p2"])
    genes = form(["tss", "chrom"], [[1200, "chr1"], [4000, "chr1"]], enc_cols=("chrom",), names=["g1", "g2"])
    out = run(PeakAnnotateStep(), [peaks, genes], {"output": "o", "region_dim": "row", "gene_dim": "row", "field_dim": "field"})
    assert out.data.shape == (2, 4)
    assert out.data[0, 0] == 0 and out.data[0, 1] == -50   # centre 1250 -> 1200
    assert out.data[1, 0] == 1 and out.data[1, 1] == 700    # centre 3300 -> 4000


def test_peak_overlap_respects_chrom():
    peaks = form(["start", "end", "chrom"],
                 [[1000, 1500, "chr1"], [1400, 2100, "chr1"], [800, 1400, "chr2"]],
                 enc_cols=("chrom",), names=["p1", "p2", "p3"])
    out = run(PeakOverlapMatrixStep(), [peaks], {"output": "o", "region_dim": "row", "field_dim": "field"})
    assert out.data.shape == (3, 3)
    assert out.data[0, 1] == 100 and out.data[0, 2] == 0
    assert out.data[0, 0] == 500 and out.data[2, 2] == 600


def test_peak_tss_enrichment_bins():
    peaks = form(["start", "end", "chrom"], [[1000, 1400, "chr1"], [9000, 9400, "chr1"]],
                 enc_cols=("chrom",), names=["p1", "p2"])
    genes = form(["tss", "chrom"], [[1200, "chr1"]], enc_cols=("chrom",), names=["g1"])
    out = run(PeakTssEnrichmentStep(), [peaks, genes],
              {"output": "o", "region_dim": "row", "gene_dim": "row", "field_dim": "field", "bin_size": 1000, "max_bins": 10})
    counts = {int(r[0]): r[1] for r in out.data}
    assert counts[0] == 1 and counts[8000] == 1 and sum(counts.values()) == 2


def test_motif_scan_pwm():
    seqs = form(["seq"], [["ACGTT"]], enc_cols=("seq",), names=["s1"])
    pwm_rows = [[0.9, 0.1, 0.1], [0.1, 0.8, 0.1], [0.1, 0.1, 0.8], [0.0, 0.05, 0.05]]
    pwm = form(["p0", "p1", "p2"], pwm_rows)
    out = run(MotifScanPwmStep(), [seqs, pwm], {"output": "o", "seq_dim": "row", "motif_dim": "row", "field_dim": "field"})
    assert out.data[0, 0] == pytest.approx(2.5) and int(out.data[0, 1]) == 0


def test_chromatin_state_segmentation():
    track = form(["pos", "signal"], [[100, 0.2], [200, 0.4], [300, 1.5], [400, 1.6], [500, 0.1]])
    out = run(ChromatinStateSegmentationStep(), [track],
              {"output": "o", "region_dim": "row", "field_dim": "field", "min_signal": 1.0})
    assert out.data.shape[0] == 2
    assert out.data[1, 0] == 300 and out.data[1, 1] == 400
    assert out.data[1, 4] == 1  # state on


