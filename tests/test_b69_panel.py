import numpy as np
import pandas as pd
import pytest

from src.core import Form
from src.core.encoding import LabelEncoder
from src.reader.readers._table_common import table_form
from src.task.context import Context
from src.task.step.steps.bcr_clonotype import BcrClonotypeStep
from src.task.step.steps.tcr_diversity import TcrDiversityStep
from src.task.step.steps.cdr3_properties import Cdr3PropertiesStep


class Ctx(Context):
    def __init__(self, params):
        self.step_params = params
        self._values = {}
        self.metadata = {}

    def __setitem__(self, key, value):
        self._values[key] = value

    def __getitem__(self, key):
        return self._values[key]


def make_form(rows):
    df = pd.DataFrame(rows, columns=["cdr3_aa", "v_gene", "count"])
    enc = {"cdr3_aa": LabelEncoder().fit_transform(df["cdr3_aa"].tolist()),
           "v_gene": LabelEncoder().fit_transform(df["v_gene"].tolist())}
    return table_form(df, dims=["sequence", "field"], labels={"field": "builtin"},
                      format_name="table", encoders_cfg={}, row_labels=[f"s{i}" for i in range(len(df))])


def run(step, form, params):
    step.name = step.definition["id"]
    ctx = Ctx(dict(params))
    step.run(ctx, [form])
    return ctx[params["output"]]


def test_bcr_clonotype_groups_and_expands():
    form = make_form([
        ("CASSLGQAYEQYF", "TRBV5-1", 40),
        ("CASSLGQAYEQYF", "TRBV5-1", 10),
        ("CASSQEVGTGYTF", "TRBV7-9", 25),
        ("CSARDRTGNGYTF", "TRBV12-3", 3),
    ])
    out = run(BcrClonotypeStep(), form, {"output": "clones"})
    assert list(out.dims) == ["entry", "statistic"]
    assert out.data.shape == (3, 3)
    assert out.data[0, 0] == 50.0
    assert abs(out.data[0, 1] - 50 / 78) < 1e-12
    assert out.info["n_expanded"] == 3


def test_tcr_diversity_matches_hand_numbers():
    form = make_form([("A", "V1", 4), ("B", "V1", 2), ("C", "V2", 1), ("D", "V2", 1)])
    out = run(TcrDiversityStep(), form, {"output": "div"})
    n = 8.0
    p = np.array([4, 2, 1, 1]) / n
    assert out.data[0, 0] == 4.0
    assert abs(out.data[0, 1] - (-(p * np.log(p)).sum())) < 1e-12
    assert abs(out.data[0, 2] - (1 - (p ** 2).sum())) < 1e-12


def test_cdr3_properties_counts_residues():
    form = make_form([("CASSK", "V1", 1), ("FWY", "V1", 1)])
    out = run(Cdr3PropertiesStep(), form, {"output": "props"})
    assert out.data[1, 0] == 3.0
    assert out.data[1, 1] == 0.0
    assert out.data[1, 2] == 1.0
    assert out.data[1, 3] == 0.0
    assert out.data[1, 4] == 1.0
