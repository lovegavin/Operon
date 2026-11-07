import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.peak_overlap_count import PeakOverlapCountStep
from src.task.step.steps.peak_density_profile import PeakDensityProfileStep
from src.task.step.steps.peak_tss_distance import PeakTssDistanceStep


class Ctx:
    def __init__(self, values):
        self.step_params = values
        self.values = {}

    def __getitem__(self, key):
        return self.values[key]

    def __setitem__(self, key, value):
        self.values[key] = value


class FakeEnc:
    def __init__(self, values):
        self.values = values

    def inverse(self, codes):
        return [self.values[int(c)] for c in codes]


def frame(rows, dim, cols, encoders=None):
    info = {"missing_code": np.nan}
    if encoders:
        info["encoders"] = {"field": encoders}
    return Form(
        data=np.asarray(rows, dtype=float),
        dims=[dim, "field"],
        labels={dim: {f"r{i}": i for i in range(len(rows))}, "field": {c: j for j, c in enumerate(cols)}},
        info=info,
    )


def peaks():
    return frame([[0, 0, 100], [0, 200, 300], [0, 1000, 1100]], "region", ["chrom", "start", "end"])


def genes():
    return frame(
        [[0, 0, 0, 50, 0], [0, 0, 900, 1200, 0]],
        "record",
        ["seqid", "type", "start", "end", "strand"],
        {"type": FakeEnc({0: "gene", 1: "exon"}), "seqid": FakeEnc({0: "0"})},
    )


def test_overlap_counts():
    ctx = Ctx({"output": "out"})
    PeakOverlapCountStep().run(ctx, [peaks(), genes()])
    out = ctx["out"]
    assert out.data[0, 0] == 3
    assert out.data[1, 0] == 2
    assert out.data[3, 0] == 150


def test_density_windows():
    ctx = Ctx({"output": "out", "window_bp": 1000})
    genome = frame([[2000]], "chrom", ["size"])
    genome.labels["chrom"] = {"0": 0}
    PeakDensityProfileStep().run(ctx, [peaks(), genome])
    out = ctx["out"]
    assert out.data.shape == (2, 3)
    assert out.data[0, 0] == 2
    assert out.data[0, 1] == 200
    assert out.data[1, 0] == 1


def test_tss_distance():
    ctx = Ctx({"output": "out"})
    PeakTssDistanceStep().run(ctx, [peaks(), genes()])
    out = ctx["out"]
    assert out.data[0, 0] == 3
    assert out.data[3, 0] == pytest.approx(150.0)
    assert out.data[5, 0] == 1.0
