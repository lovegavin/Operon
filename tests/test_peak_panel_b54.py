"""Tests for the b54 narrowPeak panel."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.core.encoding import LabelEncoder
from src.core.forms.form import Form
from src.reader.readers._table_common import table_form
from src.task.step.steps.peak_chrom_summary import PeakChromSummaryStep
from src.task.step.steps.peak_strand_bias import PeakStrandBiasStep
from src.task.step.steps.peak_width_signal_correlation import PeakWidthSignalCorrelationStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params
        self.name = params["output"]


def peaks_form():
    frame = pd.DataFrame(
        {
            "chrom": ["chr1", "chr1", "chr1", "chr1", "chr2", "chr2"],
            "start": [100, 200, 300, 400, 500, 600],
            "end": [150, 260, 370, 480, 590, 700],
            "name": [".", ".", ".", ".", ".", "."],
            "score": [0, 0, 0, 0, 0, 0],
            "strand": ["+", "-", ".", "+", "-", "+"],
            "signalValue": [10.0, 20.0, 30.0, 40.0, 50.0, 60.0],
            "pValue": [5.0, 5.0, 5.0, 5.0, 5.0, 5.0],
            "qValue": [1.0, 5.0, 10.0, 15.0, 20.0, 25.0],
            "peak": [25, 30, 35, 40, 45, 50],
        }
    )
    return table_form(
        frame,
        ["region", "field"],
        {"region": "auto", "field": "builtin"},
        "narrowpeak",
        encoders_cfg={"field": {"chrom": LabelEncoder(), "strand": LabelEncoder(), "name": LabelEncoder()}},
        row_labels=[f"peak{i}" for i in range(len(frame))],
    )


def run(step, form, **params):
    payload = {"output": "out", "region_dim": "region", "field_dim": "field"}
    payload.update(params)
    ctx = Ctx(payload)
    step.name = "out"
    step.run(ctx, [form])
    return ctx["out"]


def test_strand_bias_counts():
    out = run(PeakStrandBiasStep(), peaks_form())
    assert out.data.shape == (6, 1)
    assert list(out.labels["metric"]) == [
        "n_peaks",
        "n_plus",
        "n_minus",
        "n_unknown",
        "fraction_plus",
        "plus_minus_ratio",
    ]
    assert out.data[0, 0] == 6
    assert out.data[1, 0] == 3
    assert out.data[2, 0] == 2
    assert out.data[3, 0] == 1
    assert abs(out.data[4, 0] - 0.5) < 1e-12
    assert abs(out.data[5, 0] - 1.5) < 1e-12


def test_width_signal_is_perfect_linear():
    out = run(PeakWidthSignalCorrelationStep(), peaks_form())
    assert abs(out.data[1, 0] - 1.0) < 1e-12
    assert abs(out.data[2, 0] - 1.0) < 1e-12
    assert abs(out.data[3, 0] - 1.0) < 1e-9
    assert abs(out.data[4, 0] - 40.0) < 1e-9


def test_chrom_concentration():
    out = run(PeakChromSummaryStep(), peaks_form())
    assert out.data[1, 0] == 2
    assert out.data[2, 0] == 4
    assert abs(out.data[5, 0] - 4 / 6) < 1e-12
    assert out.data[6, 0] == 1.0
