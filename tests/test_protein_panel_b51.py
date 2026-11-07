"""Tests for the b51 protein motif and property panel."""
import numpy as np
import pytest

from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.protein_aliphatic_index import ProteinAliphaticIndexStep
from src.task.step.steps.protein_nls_motifs import ProteinNlsMotifsStep
from src.task.step.steps.protein_pts1_signal import ProteinPts1SignalStep
from src.task.step.steps.protein_kinase_motifs import ProteinKinaseMotifsStep
from src.task.step.steps.protein_nglyc_sequons import ProteinNGlycSequonsStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = dict(params)


def run(step, sequences, output="out"):
    step.name = "test"
    form = encode_sequences(sequences, "sequence", "position", "protein")
    ctx = Ctx({"output": output, "sequence_dim": "sequence", "position_dim": "position"})
    step.run(ctx, [form])
    return ctx[output]


def column(form, name):
    return form.data[:, form.labels["statistic"][name]]


def test_aliphatic_index_hand_values():
    out = run(ProteinAliphaticIndexStep(), ["AAAA", "VVVV", "ILIL"])
    assert list(out.data[:, 0]) == pytest.approx([100.0, 290.0, 390.0])


def test_nls_monopartite_and_bipartite():
    out = run(ProteinNlsMotifsStep(),
              ["PKKKRKV", "KRPAATKKAGQAKKKK", "PAAAAAA"])
    assert column(out, "monopartite_nls")[0] >= 1
    assert column(out, "bipartite_nls")[1] >= 1
    assert column(out, "total_nls")[2] == 0


def test_pts1_terminal_tripeptide():
    out = run(ProteinPts1SignalStep(), ["MGSSKL", "MGSKLA", "SKL"])
    assert list(out.data[:, 0]) == pytest.approx([1.0, 0.0, 1.0])


def test_kinase_motif_counts():
    out = run(ProteinKinaseMotifsStep(), ["RRASL", "SLDED", "SPAK"])
    assert out.data[0, 0] >= 1
    assert out.data[1, 1] >= 1
    assert out.data[2, 2] >= 1
    assert out.data[0, 3] == out.data[0, 0] + out.data[0, 1] + out.data[0, 2]


def test_nglyc_sequons_and_density():
    out = run(ProteinNGlycSequonsStep(), ["NST", "NPS", "NNSS"])
    assert list(out.data[:, 0]) == pytest.approx([1.0, 0.0, 2.0])
    assert out.data[0, 1] == pytest.approx(100.0 / 3.0)


def test_unknown_residues_are_ignored():
    out = run(ProteinAliphaticIndexStep(), ["AAXAA"])
    assert out.data[0, 0] == pytest.approx(80.0)
