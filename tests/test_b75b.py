import numpy as np
import pandas as pd

from src.core import Form
from src.core.encoding import LabelEncoder
from src.reader.readers._table_common import table_form
from src.task.context import Context
from src.task.step.steps.pedigree_inbreeding import PedigreeInbreedingStep
from src.task.step.steps.rt_alignment import RtAlignmentStep
from src.task.step.steps.selection_index import SelectionIndexStep


class Ctx(Context):
    def __init__(self, params):
        self.step_params = params
        self._values = {}

    def __getitem__(self, key):
        return self._values[key]

    def __setitem__(self, key, value):
        self._values[key] = value


def form(columns, rows, row_dim):
    df = pd.DataFrame(rows, columns=columns).drop(columns=[columns[0]])
    labels = {"field": {c: i for i, c in enumerate(df.columns)}}
    return table_form(df, [row_dim, "field"], labels, "table", encoders_cfg={},
                      row_labels=[r[0] for r in rows])


def run(step, params, f):
    ctx = Ctx(params)
    step.run(ctx, [f])
    return ctx[params["output"]]


def test_rt_alignment():
    f = form(["feature", "run_a", "run_b"], [["f1", 1.0, 1.4], ["f2", 2.0, 3.0]], "feature")
    out = run(RtAlignmentStep(), {"output": "o"}, f)
    assert abs(out.info["median_shift"] - 0.7) < 1e-9
    assert abs(out.data[1, 2] - 2.3) < 1e-9


def test_selection_index_rank():
    f = form(["variant", "fst", "ihs", "xpehh"],
             [["v1", 0.1, -0.2, 0.0], ["v2", 0.4, 2.0, 1.5], ["v3", 0.2, 0.5, 0.3]], "variant")
    out = run(SelectionIndexStep(), {"output": "o"}, f)
    assert out.data[1, 3] > out.data[0, 3]
    assert out.data[1, 4] == 1.0


def test_pedigree_inbreeding():
    f = form(["individual", "sire_index", "dam_index"],
             [["i0", -1, -1], ["i1", -1, -1], ["i2", -1, -1],
              ["i3", 0, 1], ["i4", 0, 2], ["i5", 3, 4]], "individual")
    out = run(PedigreeInbreedingStep(), {"output": "o"}, f)
    assert abs(out.data[5, 0] - 0.125) < 1e-9
    assert out.data[0, 0] == 0.0
