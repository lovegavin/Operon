import numpy as np
import pandas as pd

from src.core import Form
from src.task.context import Context
from src.reader.readers._table_common import table_form
from src.task.step.steps.fst_outlier_scan import FstOutlierScanStep
from src.task.step.steps.recombination_rate import RecombinationRateStep
from src.task.step.steps.qtl_interval_mapping import QtlIntervalMappingStep
from src.task.step.steps.genomic_selection_rrblup import GenomicSelectionRrblupStep
from src.task.step.steps.genotype_allele_balance import GenotypeAlleleBalanceStep


class Ctx(Context):
    def __init__(self, params):
        self.step_params = dict(params)
        self._values = {}

    def __setitem__(self, key, value):
        self._values[key] = value

    def __getitem__(self, key):
        return self._values[key]


def ctx(params):
    return Ctx(params)


def table(names, rows, dim):
    df = pd.DataFrame(rows, columns=names)
    return table_form(df, [dim, "field"], {"field": {n: i for i, n in enumerate(names)}},
                      "test", encoders_cfg={}, row_labels=["r%d" % i for i in range(len(rows))])


def pheno(values):
    return Form(data=np.asarray(values, dtype=float)[:, None], dims=["individual", "trait"],
                labels={"individual": {str(i): i for i in range(len(values))}, "trait": {"phenotype": 0}},
                info={"missing_code": np.nan})


def test_fst_flags_outlier():
    rows = [("chr1", 100, 90, 10, 90, 10), ("chr1", 200, 50, 50, 50, 50),
            ("chr1", 300, 95, 5, 60, 40)]
    form = table(["chrom", "pos", "n1_ref", "n1_alt", "n2_ref", "n2_alt"], rows, "variant")
    c = ctx({"output": "o", "window_bp": 150, "z_threshold": 0.5})
    step = FstOutlierScanStep()
    step.name = "fst_outlier_scan"
    step.run(c, [form])
    out = c["o"]
    assert out.data.shape == (3, 4)
    assert abs(out.data[1, 0]) < 1e-12
    assert out.data[2, 0] > 0


def test_recombination_rate():
    rows = [("chr1", 0, 0.0), ("chr1", 1_000_000, 1.0), ("chr1", 3_000_000, 3.0)]
    form = table(["chrom", "pos", "cM"], rows, "interval")
    c = ctx({"output": "o"})
    step = RecombinationRateStep()
    step.name = "recombination_rate"
    step.run(c, [form])
    out = c["o"]
    assert abs(out.data[1, 2] - 1.0) < 1e-9
    assert abs(out.data[2, 2] - 1.0) < 1e-9


def test_qtl_recovers_slope():
    gen = np.array([[0.0], [0.0], [1.0], [1.0], [2.0], [2.0]])
    g = Form(data=gen, dims=["individual", "marker"],
             labels={"individual": {str(i): i for i in range(6)}, "marker": {"m1": 0}},
             info={"missing_code": np.nan})
    p = pheno([0.0, 0.2, 1.0, 0.9, 2.1, 1.8])
    c = ctx({"output": "o", "phenotype_field": "phenotype"})
    step = QtlIntervalMappingStep()
    step.name = "qtl_interval_mapping"
    step.run(c, [g, p])
    out = c["o"]
    assert abs(out.data[0, 0] - 1.0) < 0.1
    assert out.data[0, 4] > 0


def test_rrblup_prediction():
    rng = np.random.default_rng(3)
    X = rng.integers(0, 3, size=(20, 10)).astype(float)
    y = X @ rng.normal(0, 0.1, 10) + rng.normal(0, 0.05, 20)
    g = Form(data=X, dims=["individual", "marker"],
             labels={"individual": {str(i): i for i in range(20)},
                     "marker": {str(i): i for i in range(10)}},
             info={"missing_code": np.nan})
    p = pheno(y)
    c = ctx({"output": "o", "phenotype_field": "phenotype", "lambda": 1.0})
    step = GenomicSelectionRrblupStep()
    step.name = "genomic_selection_rrblup"
    step.run(c, [g, p])
    out = c["o"]
    assert np.corrcoef(out.data[:, 0], out.data[:, 1])[0, 1] > 0.8


def test_allele_balance():
    rows = [("chr1", 100, 20, 20), ("chr1", 200, 50, 2)]
    form = table(["chrom", "pos", "ref_count", "alt_count"], rows, "variant")
    c = ctx({"output": "o"})
    step = GenotypeAlleleBalanceStep()
    step.name = "genotype_allele_balance"
    step.run(c, [form])
    out = c["o"]
    assert abs(out.data[0, 1] - 0.5) < 1e-12
    assert out.data[0, 2] > 0.5
    assert out.data[1, 3] == 1.0
