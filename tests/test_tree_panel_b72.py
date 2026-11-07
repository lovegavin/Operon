import numpy as np
import pandas as pd

from src.core import Form
from src.reader.readers._table_common import table_form
from src.task.context import Context
from src.task.step.steps.tree_mrca import TreeMrcaStep
from src.task.step.steps.tree_parsimony_score import TreeParsimonyScoreStep
from src.task.step.steps.tree_ultrametric import TreeUltrametricStep

TREE = "(A:1,B:2,(C:1,D:3):1);"


class Ctx(Context):
    def __init__(self, params):
        self.step_params = params
        self._values = {}

    def __setitem__(self, key, value):
        self._values[key] = value

    def __getitem__(self, key):
        return self._values[key]


def traits():
    df = pd.DataFrame({"c1": [0, 0, 1, 1], "c2": [0, 0, 0, 1],
                       "c3": [1, 1, 1, 1], "c4": [0, 1, 0, 0]})
    return table_form(df, ["taxon", "field"], {"taxon": "builtin", "field": "builtin"},
                      "traits", encoders_cfg={}, row_labels=["A", "B", "C", "D"])


def test_parsimony_fitch():
    step = TreeParsimonyScoreStep()
    step.name = "p"
    ctx = Ctx({"output": "out", "newick": TREE, "taxon_dim": "taxon", "character_dim": "field"})
    step.run(ctx, [traits()])
    data = ctx["out"].data
    assert data[0, 0] == 3.0
    assert data[0, 1] == 4.0
    assert data[0, 2] == 1.0


def test_mrca_height_and_distance():
    step = TreeMrcaStep()
    step.name = "m"
    ctx = Ctx({"output": "out", "newick": TREE, "taxon_a": "A", "taxon_b": "C"})
    step.run(ctx, [])
    data = ctx["out"].data
    assert data[0, 0] == 0.0
    assert data[0, 1] == 3.0
    assert data[0, 2] == 4.0
    assert data[0, 3] == 3.0


def test_ultrametric():
    step = TreeUltrametricStep()
    step.name = "u"
    ctx = Ctx({"output": "out", "newick": "(A:1,B:1);", "tolerance": 1e-6})
    step.run(ctx, [])
    assert ctx["out"].data[0, 0] == 1.0
    ctx2 = Ctx({"output": "out", "newick": TREE, "tolerance": 1e-6})
    step.run(ctx2, [])
    assert ctx2["out"].data[0, 0] == 0.0
    assert ctx2["out"].data[0, 1] == 3.0
