import numpy as np
import pandas as pd
from src.reader.readers._table_common import table_form
from src.task.context import Context
from src.task.step.steps.core_genome_size import CoreGenomeSizeStep
from src.task.step.steps.pangenome_curve import PangenomeCurveStep
from src.task.step.steps.ortholog_cluster import OrthologClusterStep


class Ctx(Context):
    def __init__(self, params):
        self.step_params = params
        self._values = {}
        self.metadata = {}

    def __setitem__(self, key, value):
        self._values[key] = value

    def __getitem__(self, key):
        return self._values[key]


def form():
    df = pd.DataFrame([
        [1, 1, 1, 0, 1, 0, 1, 0],
        [1, 1, 1, 0, 0, 1, 1, 0],
        [1, 1, 0, 1, 0, 1, 1, 0],
        [1, 1, 0, 1, 0, 0, 0, 1],
        [1, 1, 0, 1, 0, 0, 0, 1],
    ], columns=[f"gene{i}" for i in range(1, 9)], index=list("ABCDE"))
    return table_form(df, dims=["genome", "gene"], labels={"gene": "builtin"},
                      format_name="table", encoders_cfg={}, row_labels=list("ABCDE"))


def run(step, params):
    step.name = step.definition["id"]
    ctx = Ctx(dict(params))
    step.run(ctx, [form()])
    return ctx[params["output"]]


def test_core_genome_fractions():
    out = run(CoreGenomeSizeStep(), {"output": "core"})
    assert out.data[0].tolist() == [5.0, 2.0, 3.0, 0.4]
    assert out.data[3].tolist() == [4.0, 2.0, 2.0, 0.5]


def test_pangenome_curve_is_monotone():
    out = run(PangenomeCurveStep(), {"output": "curve", "permutations": 10})
    values = out.data[:, 1]
    assert values[-1] == 8.0
    assert np.all(np.diff(values) >= 0)


def test_ortholog_clusters_merge_identical_patterns():
    out = run(OrthologClusterStep(), {"output": "clusters", "min_jaccard": 0.8})
    first = out.data[0].tolist()
    assert first == [2.0, 0.4]
