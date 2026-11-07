import pandas as pd
from src.core import Form
from src.reader.readers._table_common import table_form
from src.task.context import Context
from src.task.step.steps.conserved_gene_order import ConservedGeneOrderStep
from src.task.step.steps.genome_rearrangement import GenomeRearrangementStep


class Ctx(Context):
    def __init__(self, params):
        self.step_params = params
        self._values = {}

    def __getitem__(self, key):
        return self._values[key]

    def __setitem__(self, key, value):
        self._values[key] = value


def form():
    rows = [["g1", 1.0, 1.0], ["g2", 2.0, 2.0], ["g3", 3.0, 3.0],
            ["g4", 4.0, 5.0], ["g5", 5.0, 4.0], ["g6", 6.0, 6.0]]
    df = pd.DataFrame(rows, columns=["gene", "g1_position", "g2_position"]).drop(columns=["gene"])
    labels = {"field": {"g1_position": 0, "g2_position": 1}}
    return table_form(df, ["gene", "field"], labels, "table", encoders_cfg={},
                      row_labels=[r[0] for r in rows])


def run(step, params):
    ctx = Ctx(params)
    step.run(ctx, [form()])
    return ctx[params["output"]]


def test_conserved_gene_order():
    out = run(ConservedGeneOrderStep(), {"output": "o"})
    row = out.data[0]
    assert abs(row[0] - 0.9428571428571428) < 1e-9
    assert row[2] == 1.0
    assert abs(row[3] - 1.0 / 15.0) < 1e-9


def test_genome_rearrangement():
    out = run(GenomeRearrangementStep(), {"output": "o"})
    row = out.data[0]
    assert abs(row[0] - 0.4) < 1e-9
    assert row[1] == 3.0 and row[2] == 2.0 and row[3] == 3.0
