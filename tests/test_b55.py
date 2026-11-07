import numpy as np
import pandas as pd

from src.reader.readers._table_common import table_form
from src.task.context import Context
from src.task.step.steps.effective_population_size import EffectivePopulationSizeStep
from src.task.step.steps.haplotype_blocks import HaplotypeBlocksStep
from src.task.step.steps.ibd_segments import IbdSegmentsStep
from src.task.step.steps.ihs_selection import IhsSelectionStep
from src.task.step.steps.roh_detect import RohDetectStep


class Ctx(Context):
    def __init__(self, params):
        self.step_params = params
        self._values = {}

    def __getitem__(self, key):
        return self._values[key]

    def __setitem__(self, key, value):
        self._values[key] = value


def form(columns, rows, row_dim, keep_first=False):
    df = pd.DataFrame(rows, columns=columns)
    if not keep_first:
        df = df.drop(columns=[columns[0]])
        row_labels = [r[0] for r in rows]
    else:
        row_labels = [str(i) for i in range(len(rows))]
    labels = {"field": {c: i for i, c in enumerate(df.columns)}}
    return table_form(df, [row_dim, "field"], labels, "table", encoders_cfg={},
                      row_labels=row_labels)


def run(step, params, f):
    ctx = Ctx(params)
    step.run(ctx, [f])
    return ctx[params["output"]]


def test_effective_population_size():
    f = form(["variant", "p0", "p1", "generations"],
             [["v1", 0.2, 0.4, 10], ["v2", 0.5, 0.5, 10]], "variant")
    out = run(EffectivePopulationSizeStep(), {"output": "o"}, f)
    assert abs(out.data[0, 0] - 0.19047619) < 1e-8
    assert abs(out.data[0, 1] - 26.25) < 1e-6
    assert np.isnan(out.data[1, 1])


def test_haplotype_blocks():
    f = form(["variant", "pos", "r2_prev"],
             [["v1", 100, 1.0], ["v2", 200, 0.8], ["v3", 300, 0.9],
              ["v4", 400, 0.2], ["v5", 500, 0.7]], "variant")
    out = run(HaplotypeBlocksStep(), {"output": "o"}, f)
    assert int(out.data[0, 2]) == 3
    assert int(out.data[1, 2]) == 2
    assert abs(out.data[0, 3] - 0.9) < 1e-9


def test_ibd_segments():
    f = form(["pair", "variant", "pos", "ibs"],
             [["p1", "v1", 100, 2], ["p1", "v2", 200, 2], ["p1", "v3", 300, 2],
              ["p2", "v1", 100, 1], ["p2", "v2", 200, 2]], "row", keep_first=True)
    out = run(IbdSegmentsStep(), {"output": "o", "min_variants": 3}, f)
    rows = {n: out.data[i] for n, i in out.labels["entry"].items()}
    assert len(rows) == 2
    p1 = [v for k, v in rows.items() if k.startswith("p1")][0]
    assert p1[0] == 1 and p1[1] == 200 and p1[2] == 200


def test_roh_detect():
    f = form(["sample", "variant", "pos", "genotype"],
             [["s1", "v1", 100, 0], ["s1", "v2", 200, 2], ["s1", "v3", 300, 0],
              ["s2", "v1", 100, 0], ["s2", "v2", 200, 2], ["s2", "v3", 300, 1]], "row",
             keep_first=True)
    out = run(RohDetectStep(), {"output": "o", "min_variants": 3}, f)
    rows = {n: out.data[i] for n, i in out.labels["entry"].items()}
    s1 = [v for k, v in rows.items() if k.startswith("s1")][0]
    s2 = [v for k, v in rows.items() if k.startswith("s2")][0]
    assert s1[0] == 1 and s1[1] == 200
    assert s2[0] == 0


def test_ihs_selection():
    f = form(["variant", "pos", "h1", "h2", "h3", "h4"],
             [["v2", 200, 0, 0, 1, 1], ["v3", 300, 0, 1, 1, 1],
              ["v4", 400, 0, 0, 1, 0]], "variant")
    out = run(IhsSelectionStep(), {"output": "o"}, f)
    assert out.data.shape == (3, 6)
    assert out.data[1, 4] == 3 and out.data[1, 5] == 1
    assert np.isnan(out.data[0, 1]) and np.isnan(out.data[2, 1])
