import numpy as np

from src.core.forms.form import Form
from src.task.step.steps.haplotype_diversity import HaplotypeDiversityStep
from src.task.step.steps.mismatch_distribution import MismatchDistributionStep
from src.task.step.steps.sequence_dnds import SequenceDndsStep


class Enc:
    def __init__(self, inverse):
        self.inverse = inverse


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = dict(params)


def strings_form(rows, columns, encoders):
    data = np.array([[encoders[col]["forward"][value] for col, value in zip(columns, values)] for _, values in rows], dtype=float)
    info = {"encoders": {"site": {}}}
    for col in columns:
        info["encoders"]["site"][col] = Enc(encoders[col]["inverse"])
    form = Form(
        data=data,
        dims=["sequence", "site"],
        labels={"sequence": {name: idx for idx, (name, _) in enumerate(rows)}, "site": {col: idx for idx, col in enumerate(columns)}},
        info=info,
    )
    form.validate()
    return form


def cds_form(sequences):
    columns = ["c1", "c2"]
    alphabet = sorted({codon for seq in sequences for codon in seq})
    mapping = {codon: idx for idx, codon in enumerate(alphabet)}
    encoders = {col: {"forward": mapping, "inverse": {v: k for k, v in mapping.items()}} for col in columns}
    data = np.array([[mapping[codon] for codon in seq] for seq in sequences], dtype=float)
    form = Form(
        data=data,
        dims=["sequence", "codon"],
        labels={"sequence": {f"s{i}": i for i in range(len(sequences))}, "codon": {col: i for i, col in enumerate(columns)}},
        info={"encoders": {"codon": {col: Enc(encoders[col]["inverse"]) for col in columns}}},
    )
    form.validate()
    return form


def test_haplotype_diversity_values():
    form = strings_form(
        [("H1", ["A", "A", "A", "A"]), ("H2", ["A", "A", "A", "T"]), ("H3", ["A", "A", "T", "T"]), ("H4", ["T", "T", "T", "T"])],
        ["s1", "s2", "s3", "s4"],
        {col: {"forward": {"A": 0, "T": 1}, "inverse": {0: "A", 1: "T"}} for col in ["s1", "s2", "s3", "s4"]},
    )
    ctx = Ctx({"output": "diversity", "row_dim": "sequence", "field_dim": "site"})
    HaplotypeDiversityStep().run(ctx, [form])
    out = ctx["diversity"]
    row = list(out.data[0])
    assert row[0] == 4 and row[1] == 4
    assert abs(row[3] - 13 / 6 / 4) < 1e-9
    assert row[4] == 4


def test_mismatch_distribution_values():
    form = strings_form(
        [("H1", ["A", "A", "A", "A"]), ("H2", ["A", "A", "A", "T"]), ("H3", ["A", "A", "T", "T"]), ("H4", ["T", "T", "T", "T"])],
        ["s1", "s2", "s3", "s4"],
        {col: {"forward": {"A": 0, "T": 1}, "inverse": {0: "A", 1: "T"}} for col in ["s1", "s2", "s3", "s4"]},
    )
    ctx = Ctx({"output": "mismatch", "row_dim": "sequence", "field_dim": "site"})
    MismatchDistributionStep().run(ctx, [form])
    row = list(ctx["mismatch"].data[0])
    assert row[0] == 6
    assert abs(row[1] - 13 / 6) < 1e-9
    assert row[3] == 4


def test_dnds_identical_sequences_have_zero_syn_diff():
    form = cds_form([["ATG", "GCT"], ["ATG", "GCT"]])
    ctx = Ctx({"output": "dnds", "row_dim": "sequence", "field_dim": "codon"})
    SequenceDndsStep().run(ctx, [form])
    out = ctx["dnds"]
    assert out.data.shape[0] == 1
    row = list(out.data[0])
    assert abs(row[5]) < 1e-12 and abs(row[6]) < 1e-12
