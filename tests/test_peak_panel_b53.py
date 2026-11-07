import numpy as np
import pandas as pd
import pytest

from src.reader.readers._table_common import table_form
from src.task.step.steps.peak_gap_stats import PeakGapStatsStep
from src.task.step.steps.peak_signal_stats import PeakSignalStatsStep
from src.task.step.steps.peak_summit_offset import PeakSummitOffsetStep
from src.task.step.steps.peak_width_stats import PeakWidthStatsStep

COLUMNS = [
    "chrom",
    "start",
    "end",
    "name",
    "score",
    "strand",
    "signalValue",
    "pValue",
    "qValue",
    "peak",
]

ROWS = [
    ["chr1", 100, 200, "p1", 100, ".", 10, 1, 5, 50],
    ["chr1", 300, 500, "p2", 200, ".", 20, 2, 15, 100],
    ["chr1", 600, 650, "p3", 300, ".", 30, 3, 25, 0],
    ["chr2", 1000, 1200, "p4", 400, ".", 40, 4, 35, -1],
    ["chr2", 1300, 1400, "p5", 500, ".", 50, 5, 45, 50],
]


class Ctx:
    def __init__(self, params):
        self.step_params = params
        self._values = {}

    def __setitem__(self, key, value):
        self._values[key] = value

    def __getitem__(self, key):
        return self._values[key]


def peak_form(rows=None):
    frame = pd.DataFrame(rows or ROWS, columns=COLUMNS)
    return table_form(
        frame,
        ["region", "field"],
        {"region": "auto", "field": "builtin"},
        "narrowPeak",
        {},
    )


def run(step_cls, params=None):
    step = step_cls()
    step.name = step_cls.definition["id"]
    ctx = Ctx(dict(params or {}, output=step.name))
    step.run(ctx, [peak_form()])
    return ctx[step.name]


def metric(out, name):
    return float(out.data[out.labels["metric"][name], 0])


def test_peak_width_stats():
    out = run(PeakWidthStatsStep)
    assert metric(out, "n_peaks") == 5
    assert metric(out, "mean_width") == pytest.approx(130.0)
    assert metric(out, "median_width") == pytest.approx(100.0)
    assert metric(out, "min_width") == 50
    assert metric(out, "max_width") == 200
    assert metric(out, "total_bp") == 650
    assert metric(out, "sd_width") == pytest.approx(67.0820, rel=1e-4)


def test_peak_summit_offset():
    out = run(PeakSummitOffsetStep)
    assert metric(out, "n_peaks") == 5
    assert metric(out, "n_summit_valid") == 4
    assert metric(out, "mean_offset") == pytest.approx(50.0)
    assert metric(out, "mean_center_deviation") == pytest.approx(6.5)
    assert metric(out, "frac_centered_50") == pytest.approx(1.0)


def test_peak_gap_stats():
    out = run(PeakGapStatsStep)
    assert metric(out, "n_gaps") == 3
    assert metric(out, "mean_gap") == pytest.approx(100.0)
    assert metric(out, "max_gap") == pytest.approx(100.0)
    assert metric(out, "frac_gap_lt_1000") == pytest.approx(1.0)
    assert metric(out, "n_overlaps") == 0


def test_peak_signal_stats():
    out = run(PeakSignalStatsStep)
    assert metric(out, "n_peaks") == 5
    assert metric(out, "mean_signal") == pytest.approx(30.0)
    assert metric(out, "median_signal") == pytest.approx(30.0)
    assert metric(out, "max_signal") == 50
    assert metric(out, "mean_pvalue") == pytest.approx(3.0)
    assert metric(out, "mean_qvalue") == pytest.approx(25.0)
    assert metric(out, "frac_q_gt_10") == pytest.approx(0.8)
    assert metric(out, "frac_q_gt_20") == pytest.approx(0.6)
