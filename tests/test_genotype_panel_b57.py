import numpy as np
from src.core.encoding import LabelEncoder
from src.core.forms.form import Form
from src.task.step.steps.genotype_call_rate_qc import GenotypeCallRateQcStep
from src.task.step.steps.genotype_mendelian_error import GenotypeMendelianErrorStep

class Ctx(dict):
    def __init__(self, params):
        super().__init__(); self.step_params = params; self.metadata = {}

def make_form():
    data = np.array([[0,0,1],[0,2,1],[1,1,2],[0,0,0],[np.nan,0,1],[2,2,1]], float)
    return Form(data=data, dims=["variant","sample"],
                labels={"variant": {f"v{i+1}": i for i in range(6)},
                        "sample": {"father":0,"mother":1,"child":2}})

def run(cls, params):
    ctx = Ctx(params); cls().run(ctx, [make_form()]); return ctx[params["output"]]

def test_mendelian():
    f = run(GenotypeMendelianErrorStep, {"output":"m"})
    assert list(f.data[:,0]) == [1,0,0,0,0,1]
    assert (f.info["n_tested"], f.info["n_errors"]) == (5,2)

def test_call_rate():
    f = run(GenotypeCallRateQcStep, {"output":"c","min_call_rate":0.9})
    assert list(f.data[:,0]) == [6,6,6]
    assert list(f.data[:,2]) == [0.83333333,1.0,1.0]
    assert list(f.data[:,4]) == [0.0,1.0,1.0]
