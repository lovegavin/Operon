"""Tests for the b52 protein property panel."""
import numpy as np
import pytest

from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.protein_er_retention import ProteinErRetentionStep
from src.task.step.steps.protein_nuclear_export_signal import ProteinNuclearExportSignalStep
from src.task.step.steps.protein_mitochondrial_targeting import ProteinMitochondrialTargetingStep
from src.task.step.steps.protein_charge_curve import ProteinChargeCurveStep
from src.task.step.steps.protein_gravy_window import ProteinGravyWindowStep


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


def test_er_retention_variants():
    out = run(ProteinErRetentionStep(), ["MKKDEL", "MKKHDEL", "MKKDDEL", "MKKKEL"])
    assert out.data[0, 0] == 1 and out.data[0, 3] == 1
    assert out.data[1, 1] == 1 and out.data[1, 3] == 1
    assert out.data[2, 2] == 1 and out.data[2, 3] == 1
    assert out.data[3, 3] == 0


def test_nuclear_export_signal():
    out = run(ProteinNuclearExportSignalStep(), ["LALKLAGLDI", "MDEEDD", "LPPLERLTL"])
    assert out.data[0, 3] > 0.0 and out.data[0, 0] >= 1.0 and out.data[0, 1] == 1.0
    assert out.data[1, 3] == 0.0 and out.data[1, 2] == 0.0
    assert out.data[2, 3] > 0.0


def test_mito_charge_ordering():
    out = run(ProteinMitochondrialTargetingStep(), ["MKKRRAA", "MDDEEDD"])
    assert out.data[0, 2] > 0
    assert out.data[1, 2] < 0
    assert out.data[0, 4] > out.data[1, 4]


def test_charge_curve_ph():
    out = run(ProteinChargeCurveStep(), ["KKKK", "DDDD"])
    # pH 7 is column index 4
    assert out.data[0, 4] > 3.0
    assert out.data[1, 4] < -3.0
    assert all(out.data[0, i] > out.data[0, i + 1] for i in range(8))
    assert out.data[1, 0] > -1.0


def test_gravy_windows():
    out = run(ProteinGravyWindowStep(), ["IIIIIIIII", "DDDDDDDDD"])
    assert out.data[0, 0] == pytest.approx(4.5)
    assert out.data[1, 0] == pytest.approx(-3.5)
    assert out.data[0, 3] == 1.0
