import numpy as np
import pandas as pd

from src.core import Form
from src.reader.readers._table_common import table_form
from src.task.step.steps.nucleosome_positioning import NucleosomePositioningStep
from src.task.step.steps.motif_enrichment import MotifEnrichmentStep
from src.task.step.steps.peak_peak_distance import PeakPeakDistanceStep


class Ctx(dict):
    def __init__(self, **params):
        super().__init__()
        self.step_params = params


def table(columns, rows, name):
    df = pd.DataFrame(rows, columns=columns)
    return table_form(df, [name, "field"], labels={"field": "builtin"},
                      format_name="table", encoders_cfg={})


def out_rows(form):
    labels = form.labels[form.dims[0]]
    inv = {v: k for k, v in labels.items()}
    return [inv[i] for i in range(form.data.shape[0])]


def test_peak_distance():
    f = table(["start", "end"], [[0, 10], [100, 110], [1000, 1010]], "peak")
    ctx = Ctx(output="out")
    PeakPeakDistanceStep().run(ctx, [f])
    out = ctx["out"]
    d = np.asarray(out.data)
    assert list(out.dims) == ["row", "statistic"]
    assert d[:, 0].tolist() == [100.0, 100.0, 900.0]
    assert d[:, 1].tolist() == [1, 0, 1]


def test_nucleosome_period():
    vals = [1.0 if (i % 10) < 5 else 0.0 for i in range(30)]
    f = table(["pos", "signal"], [[i * 10, v] for i, v in enumerate(vals)], "pos")
    ctx = Ctx(output="out", step_bp=10.0, min_lag=5, max_lag=15)
    NucleosomePositioningStep().run(ctx, [f])
    out = dict((r, float(v)) for r, v in zip(out_rows(ctx["out"]), np.asarray(ctx["out"].data)[:, 0]))
    assert out["period_bp"] == 100.0
    assert out["n_lags"] == 11.0
    assert out["best_lag"] == 10.0


def test_motif_enrichment():
    fg = table(["seq"], [["AAACGTTGCAAA"], ["CCACGTTGCACC"], ["GGGGCCCCAAAA"]], "fg")
    bg = table(["seq"], [["AAACGTTGCAAA"], ["GGGGCCCCAAAA"], ["TTTTTTTTTTTT"]], "bg")
    ctx = Ctx(output="out", motif="ACGTTGCA")
    MotifEnrichmentStep().run(ctx, [fg, bg])
    d = dict((r, float(v)) for r, v in zip(out_rows(ctx["out"]), np.asarray(ctx["out"].data)[:, 0]))
    assert d["motif_count_fg"] == 2.0
    assert d["motif_count_bg"] == 1.0
    assert abs(d["fold"] - 2.0) < 1e-9
    assert 0.0 < d["p_value"] <= 1.0
