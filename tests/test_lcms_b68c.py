import numpy as np
import pandas as pd
from src.reader.readers._table_common import table_form
from src.task.context import Context
from src.task.step.steps.metabolite_adduct_annotation import MetaboliteAdductAnnotationStep
from src.task.step.steps.metabolite_set_enrichment import MetaboliteSetEnrichmentStep
from src.task.step.steps.xic_extract import XicExtractStep


class Ctx(Context):
    def __init__(self, params):
        self.step_params = params
        self._values = {}
        self.metadata = {}

    def __setitem__(self, key, value):
        self._values[key] = value

    def __getitem__(self, key):
        return self._values[key]


def form(rows, columns, dims, labels, names=None):
    df = pd.DataFrame(rows, columns=columns)
    return table_form(df, dims=dims, labels=labels, format_name="table",
                      encoders_cfg={}, row_labels=names)


def run(step, params, inputs):
    step.name = step.definition["id"]
    ctx = Ctx(dict(params))
    step.run(ctx, inputs)
    return ctx[params["output"]]


def test_adduct_annotation_matches_glucose():
    feat = form([[181.07066, 1.2], [500.0, 5.0]], ["mz", "rt"], ["feature", "field"],
                {"field": "builtin"}, ["f1", "f2"])
    db = form([[180.06339]], ["neutral_mass"], ["entry", "field"],
              {"field": "builtin"}, ["glucose"])
    out = run(MetaboliteAdductAnnotationStep(),
              {"output": "adducts", "ppm_tolerance": 10.0, "polarity": "positive"},
              [feat, db])
    assert abs(out.data[0, 0] - 180.06339) < 1e-4
    assert out.data[0, 4] == 1.0
    assert out.data[1, 4] == 0.0


def test_set_enrichment_hypergeometric():
    hits = form([["f1"], ["f2"], ["f3"], ["f4"]], ["metabolite"], ["feature", "field"],
                {"field": "builtin"}, ["h1", "h2", "h3", "h4"])
    sets = form([["setA", "f1"], ["setA", "f2"], ["setA", "f3"], ["setA", "f10"],
                 ["setB", "f3"]], ["set_id", "member"], ["set", "field"],
                {"field": "builtin"}, ["r0", "r1", "r2", "r3", "r4"])
    out = run(MetaboliteSetEnrichmentStep(),
              {"output": "sets", "universe_size": 20}, [hits, sets])
    assert out.data[0, 1] == 3.0
    assert abs(out.data[0, 4] - 0.013415892672858616) < 1e-12


def test_xic_peak_integration():
    xic = form([[1.0, 10], [2.0, 20], [3.0, 100], [4.0, 20], [5.0, 10]],
               ["rt", "intensity"], ["scan", "field"], {"field": "builtin"},
               ["s1", "s2", "s3", "s4", "s5"])
    out = run(XicExtractStep(), {"output": "peaks", "min_snr": 1.0, "smoothing": 1}, [xic])
    assert out.data.shape == (1, 6)
    assert out.data[0, 0] == 3.0
    assert abs(out.data[0, 2] - 150.0) < 1e-6
