import numpy as np

from src.core import Form
from src.task.step.steps.ligand_formula_parse import LigandFormulaParseStep
from src.task.step.steps.ligand_dbe import LigandDbeStep
from src.task.step.steps.ligand_adduct_mz import LigandAdductMzStep
from src.task.step.steps.ligand_mass_fraction import LigandMassFractionStep
from src.task.step.steps.ligand_nitrogen_rule import LigandNitrogenRuleStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = dict(params)
        self._values = {}


def formula_form(formulas):
    names = [f"m{i}" for i in range(len(formulas))]
    return Form(
        data=np.zeros((len(formulas), 1), dtype=np.float32),
        dims=["molecule", "field"],
        labels={"molecule": {n: i for i, n in enumerate(names)}, "field": {"smiles": 0}},
        info={"formula": list(formulas)},
    )


def run(step, formulas, **params):
    ctx = Ctx({"output": "out", **params})
    step.run(ctx, [formula_form(formulas)])
    return ctx["out"]


def test_formula_counts():
    out = run(LigandFormulaParseStep(), ["C9H8O4", "C2H6O"])
    assert out.data.shape == (2, 14)
    assert out.data[0, 0] == 9 and out.data[0, 1] == 8 and out.data[0, 13] == 3
    assert out.data[1, 3] == 1


def test_dbe():
    out = run(LigandDbeStep(), ["C9H8O4", "C2H6O"])
    assert abs(out.data[0, 0] - 6.0) < 1e-6
    assert abs(out.data[1, 0] - 0.0) < 1e-6
    assert abs(out.data[0, 4] - 6.0) < 1e-6
    assert abs(out.data[1, 4] - 0.0) < 1e-6


def test_adduct_mz():
    out = run(LigandAdductMzStep(), ["C9H8O4"])
    assert abs(out.data[0, 1] - 181.04953) < 1e-4
    assert abs(out.data[0, 5] - 91.0284) < 1e-3


def test_mass_fraction_sums_to_one():
    out = run(LigandMassFractionStep(), ["C9H8O4"])
    assert abs(float(out.data[0, :8].sum()) - 1.0) < 1e-5


def test_nitrogen_rule():
    out = run(LigandNitrogenRuleStep(), ["C8H10N4O2", "C9H8O4"])
    assert out.data[0, 2] == 1 and out.data[0, 3] == 1 and out.data[0, 4] == 1
    assert out.data[1, 4] == 1


def test_bad_formula_raises():
    try:
        run(LigandFormulaParseStep(), ["C9H8(O)4"])
    except Exception:
        return
    raise AssertionError("invalid formula should raise")
