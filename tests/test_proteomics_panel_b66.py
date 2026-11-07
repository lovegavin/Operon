import numpy as np

from src.core.encoding import LabelEncoder
from src.core import Form
from src.task.context import Context
from src.reader.readers._table_common import table_form
from src.task.step.steps.peptide_spectrum_annotation import PeptideSpectrumAnnotationStep
from src.task.step.steps.protein_inference import ProteinInferenceStep
from src.task.step.steps.spectrum_library_match import SpectrumLibraryMatchStep


class Ctx(Context):
    def __init__(self, params):
        self.step_params = params
        self._values = {}

    def __setitem__(self, key, value):
        self._values[key] = value

    def __getitem__(self, key):
        return self._values[key]


def peaks_form(rows, dim, columns):
    import pandas as pd
    df = pd.DataFrame(np.asarray(rows, dtype=float), columns=columns)
    return table_form(
        df,
        [dim, "field"],
        {dim: "builtin", "field": "builtin"},
        "peak_table",
        encoders_cfg={},
        row_labels=[f"r{i}" for i in range(len(rows))],
    )


def test_library_match_exact():
    q = peaks_form([[0, 100.0, 1.0], [0, 200.0, 1.0], [0, 300.0, 1.0]], "query", ["query_id", "mz", "intensity"])
    lib = peaks_form([[0, 100.0, 1.0], [0, 200.0, 1.0], [0, 300.0, 1.0]], "library", ["library_id", "mz", "intensity"])
    step = SpectrumLibraryMatchStep()
    step.name = "match"
    ctx = Ctx({"output": "out", "tolerance_ppm": 20.0})
    step.run(ctx, [q, lib])
    out = ctx["out"]
    assert out.dims == ["entry", "statistic"]
    assert abs(out.data[0, 0] - 1.0) < 1e-9
    assert out.data[0, 1] == 3.0
    assert out.data[0, 3] == 0.0


def test_annotation_b_y_ions():
    seq = "PEPTIDE"
    residues = {
        "G": 57.02146, "A": 71.03711, "S": 87.03203, "P": 97.05276,
        "V": 99.06841, "T": 101.04768, "C": 103.00919, "L": 113.08406,
        "I": 113.08406, "N": 114.04293, "D": 115.02694, "Q": 128.05858,
        "K": 128.09496, "E": 129.04259, "M": 131.04049, "H": 137.05891,
        "F": 147.06841, "R": 156.10111, "Y": 163.06333, "W": 186.07931,
    }
    total = sum(residues[a] for a in seq)
    mz = []
    acc = 0.0
    for aa in seq[:-1]:
        acc += residues[aa]
        mz.append(acc + 1.007276)
        mz.append(total - acc + 18.010565 + 1.007276)
    enc = LabelEncoder()
    codes = enc.fit_transform([seq])
    pep = Form(
        data=np.asarray([[float(codes[0])]], dtype=float),
        dims=["peptide", "field"],
        labels={"peptide": {"pep0": 0}, "field": {"peptide": 0}},
        info={"representation": "table", "encoders": {"field": {"peptide": enc}}},
    )
    rows = [[0, m, 100.0] for m in mz]
    spec = peaks_form(rows, "peak", ["spectrum_id", "mz", "intensity"])
    step = PeptideSpectrumAnnotationStep()
    step.name = "annot"
    ctx = Ctx({"output": "out", "tolerance_da": 0.02})
    step.run(ctx, [pep, spec])
    out = ctx["out"]
    assert out.dims == ["entry", "statistic"]
    assert out.data[0, 0] == 12.0
    assert out.data[0, 1] == 12.0
    assert abs(out.data[0, 2] - 1.0) < 1e-6
    assert out.data[0, 3] < 1e-4


def test_protein_inference_counts():
    rows = [[0, 0], [1, 0], [1, 1], [2, 1], [3, 2]]
    import pandas as pd
    df = pd.DataFrame(np.asarray(rows, dtype=float), columns=["peptide_id", "protein_id"])
    form = table_form(
        df,
        ["peptide", "field"],
        {"peptide": "builtin", "field": "builtin"},
        "evidence_table",
        encoders_cfg={},
        row_labels=["p0", "p1", "p2", "p3", "p4"],
    )
    step = ProteinInferenceStep()
    step.name = "prot"
    ctx = Ctx({"output": "out"})
    step.run(ctx, [form])
    out = ctx["out"]
    assert out.dims == ["entry", "statistic"]
    assert out.data[0, 0] == 2.0 and out.data[0, 1] == 1.0 and out.data[0, 2] == 1.0
    assert out.data[2, 0] == 1.0 and out.data[2, 1] == 1.0
