import numpy as np
import pandas as pd
import pytest

from src.core.forms.form import Form
from src.reader.readers._table_common import table_form
from src.task.step.steps.metagenomics_bray_curtis import MetagenomicsBrayCurtisStep
from src.task.step.steps.metagenomics_clr import MetagenomicsClrStep
from src.task.step.steps.structure_radius_of_gyration import StructureRadiusOfGyrationStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params


def make_form(df, dims):
    return table_form(df, dims, labels={dims[1]: "builtin"}, format_name="table",
                      encoders_cfg={}, row_labels=[str(i) for i in range(len(df))])


def test_radius_of_gyration_small():
    df = pd.DataFrame({'x': [0.0, 1.0, 0.0], 'y': [0.0, 0.0, 1.0], 'z': [0.0, 0.0, 0.0]})
    form = make_form(df, ['atom', 'field'])
    ctx = Ctx({'atom_dim': 'atom', 'field_dim': 'field', 'output': 'rg'})
    StructureRadiusOfGyrationStep().run(ctx, [form])
    out = ctx['rg']
    assert out.dims == ['entry', 'statistic']
    assert out.data[0, 0] == 3.0
    assert out.data[0, 1] == pytest.approx(2.0 / 3.0, abs=1e-8)
    assert out.data[0, 2] == pytest.approx((5.0 / 9.0) ** 0.5, abs=1e-8)


def test_bray_curtis_matches_manual():
    df = pd.DataFrame({'t1': [1.0, 2.0], 't2': [2.0, 0.0], 't3': [3.0, 1.0]})
    form = make_form(df, ['sample', 'feature'])
    ctx = Ctx({'row_dim': 'sample', 'field_dim': 'feature', 'output': 'bc'})
    MetagenomicsBrayCurtisStep().run(ctx, [form])
    out = ctx['bc']
    assert out.dims == ['sample', 'sample2']
    assert out.data[0, 0] == 0.0
    assert out.data[0, 1] == pytest.approx(5.0 / 9.0, abs=1e-9)
    assert out.data[1, 0] == pytest.approx(5.0 / 9.0, abs=1e-9)


def test_clr_rows_sum_to_zero():
    df = pd.DataFrame({'t1': [1.0], 't2': [2.0], 't3': [3.0]})
    form = make_form(df, ['sample', 'feature'])
    ctx = Ctx({'row_dim': 'sample', 'field_dim': 'feature', 'pseudocount': 0.5, 'output': 'clr'})
    MetagenomicsClrStep().run(ctx, [form])
    out = ctx['clr']
    logs = np.log(np.array([1.5, 2.5, 3.5]))
    expected = logs - logs.mean()
    assert np.allclose(out.data[0], expected, atol=1e-9)
    assert abs(out.data[0].sum()) < 1e-9
