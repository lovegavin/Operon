import numpy as np
import pytest

from src.core.forms.form import Form
from src.task.step.steps.bisulfite_conversion_rate import BisulfiteConversionRateStep
from src.task.step.steps.allele_specific_methylation import AlleleSpecificMethylationStep
from src.task.step.steps.tree_robinson_foulds import TreeRobinsonFouldsStep


class Ctx(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args)
        self.step_params = kwargs.get("step_params", {})


def table(cols, rows, encoders=None):
    data = np.asarray(rows, dtype=float)
    return Form(
        data=data,
        dims=["row", "field"],
        labels={
            "row": {str(i): i for i in range(len(rows))},
            "field": {c: i for i, c in enumerate(cols)},
        },
        info={"encoders": {"field": encoders or {}}},
    )


def test_bisulfite_rate():
    ctx = Ctx(step_params={"output": "out"})
    rows = [[3, 1], [1, 3]]
    form = table(["converted", "unconverted"], rows)
    BisulfiteConversionRateStep().run(ctx, [form])
    out = ctx["out"]
    cols = out.labels["statistic"]
    values = out.data[0]
    assert values[cols["n_sites"]] == 2
    assert values[cols["conversion_rate"]] == pytest.approx(0.5)
    assert values[cols["ci_low"]] < 0.5 < values[cols["ci_high"]]


def test_allele_specific_methylation():
    ctx = Ctx(step_params={"output": "out"})
    rows = [[9, 1, 1, 9], [5, 5, 4, 6]]
    form = table(
        ["a_methylated", "a_unmethylated", "b_methylated", "b_unmethylated"], rows
    )
    AlleleSpecificMethylationStep().run(ctx, [form])
    out = ctx["out"]
    cols = out.labels["statistic"]
    values = out.data[0]
    assert values[cols["n_tested"]] == 2
    assert values[cols["n_significant"]] == 1
    assert values[cols["mean_abs_diff"]] == pytest.approx(0.45)


def test_robinson_foulds():
    ctx = Ctx(step_params={"output": "out"})
    newick = {"newick": {0: "(A:1,B:1,(C:1,D:1):1);"}}
    form_a = table(["newick"], [[0.0]], newick)
    altered = {"newick": {0: "(A:1,C:1,(B:1,D:1):1);"}}
    form_b = table(["newick"], [[0.0]], altered)
    TreeRobinsonFouldsStep().run(ctx, [form_a, form_b])
    out = ctx["out"]
    cols = out.labels["statistic"]
    values = out.data[0]
    assert values[cols["rf"]] == 2.0
    assert values[cols["max_rf"]] == 2.0
    assert values[cols["normalized_rf"]] == 1.0
    assert values[cols["n_taxa"]] == 4.0
