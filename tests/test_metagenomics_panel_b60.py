import numpy as np

from src.core import Form
from src.core.encoding import LabelEncoder
from src.task.step.steps.bracken_reestimate import BrackenReestimateStep
from src.task.step.steps.humann_pathway_abundance import HumannPathwayAbundanceStep
from src.task.step.steps.kraken_kreport_parse import KrakenKreportParseStep
from src.task.step.steps.metaphlan_profile_parse import MetaphlanProfileParseStep
from src.task.step.steps.plasmid_contig_filter import PlasmidContigFilterStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = dict(params)


def form(columns, values, dim="row"):
    enc = LabelEncoder()
    return Form(data=np.asarray(values, dtype=float), dims=[dim, "field"],
                labels={dim: {f"r{i}": i for i in range(len(values))},
                        "field": {n: i for i, n in enumerate(columns)}},
                info={"missing_code": np.nan})


def run(step, inp, params=None):
    ctx = Ctx(params or {})
    step.name = "test"
    step.run(ctx, [inp])
    return ctx["output"]


def test_kraken():
    out = run(KrakenKreportParseStep(), form(["depth", "rank_code"], [[100, 6], [50, 5], [25, 0]]))
    row = out.data[0]
    assert row[0] == 175
    assert abs(row[1] - 100 / 175) < 1e-9
    assert abs(row[2] - 150 / 175) < 1e-9
    assert row[3] == 6


def test_bracken():
    out = run(BrackenReestimateStep(), form(["reads", "genome_length"], [[100, 2e6], [50, 1e6]]))
    assert abs(out.data[0, 0] - 5e-5) < 1e-12
    assert abs(out.data[0, 1] - 0.5) < 1e-9
    assert abs(out.data[1, 1] - 0.5) < 1e-9


def test_humann():
    out = run(HumannPathwayAbundanceStep(), form(["abundance"], [[10], [30], [60]]))
    row = out.data[0]
    assert row[0] == 100
    assert abs(row[1] - 100 / 3) < 1e-9
    assert row[2] == 30
    assert abs(row[3] - 0.8979457) < 1e-6
    assert abs(row[4] - 0.6) < 1e-9


def test_metaphlan():
    out = run(MetaphlanProfileParseStep(), form(["relative_abundance", "rank_code"],
                                                [[0.5, 6], [0.2, 5], [0.1, 5], [0.2, 2]]))
    assert abs(out.data[6, 0] - 0.5) < 1e-9
    assert abs(out.data[5, 0] - 0.3) < 1e-9
    assert abs(out.data[2, 0] - 0.2) < 1e-9
    assert out.info["total"] == 1.0


def test_plasmid():
    out = run(PlasmidContigFilterStep(), form(["length", "depth", "circular"],
                                             [[5000, 10, 1], [500, 10, 0]]))
    assert out.data[0, 3] == 1
    assert out.data[1, 3] == 0
    assert out.info["n_pass"] == 1
    assert out.info["bp_pass"] == 5000
