"""Tests for the b81 operators: dinucleotide frequency, Gini, Simpson diversity."""

from __future__ import annotations

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.diversity_simpson import DiversitySimpsonStep
from src.task.step.steps.numeric_gini_coefficient import NumericGiniCoefficientStep
from src.task.step.steps.sequence_dinucleotide_frequency import (
    DINUCLEOTIDES,
    SequenceDinucleotideFrequencyStep,
)


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = dict(params or {})


def _vector(values, dim="value"):
    data = np.asarray(values, dtype=np.float64)
    return Form(
        data=data,
        dims=[dim],
        labels={dim: {str(i): i for i in range(data.size)}},
    )


def _sequence_form(sequences):
    return encode_sequences(list(sequences), "sequence", "position", "dna")


def _stat(form, column):
    assert list(form.dims) == ["entry", "statistic"]
    return float(form.data[0, form.labels["statistic"][column]])


def _dinucleotide_oracle(sequences):
    """Manual loop oracle: overlapping windows over ACGT-only content."""
    counts = {name: 0 for name in DINUCLEOTIDES}
    letters = ""
    windows = 0
    for sequence in sequences:
        clean = "".join(ch for ch in sequence.upper() if ch in "ACGT")
        letters += clean
        windows += max(0, len(clean) - 1)
        for index in range(len(clean) - 1):
            counts[clean[index:index + 2]] += 1
    if windows <= 0:
        return counts, {name: 0.0 for name in DINUCLEOTIDES}, 0.0
    frequencies = {name: counts[name] / windows for name in DINUCLEOTIDES}
    freq_c = letters.count("C") / len(letters)
    freq_g = letters.count("G") / len(letters)
    expected = freq_c * freq_g
    ratio = frequencies["CG"] / expected if expected > 0.0 else 0.0
    return counts, frequencies, ratio


def _gini_pairwise(values):
    """Double-sum definition: sum_i sum_j |x_i - x_j| / (2 n^2 mean)."""
    data = [float(value) for value in values if np.isfinite(value)]
    n = len(data)
    if n == 0:
        return 0.0
    mean = sum(data) / n
    if mean <= 0.0:
        return 0.0
    total = 0.0
    for left in data:
        for right in data:
            total += abs(left - right)
    return total / (2.0 * n * n * mean)


def _gini_sorted(values):
    """Sorted-rank identity oracle."""
    data = sorted(float(value) for value in values if np.isfinite(value))
    n = len(data)
    if n == 0 or sum(data) <= 0.0:
        return 0.0
    weighted = sum((2 * (index + 1) - n - 1) * value for index, value in enumerate(data))
    return weighted / (n * sum(data))


def _simpson_oracle(values):
    data = [float(value) for value in values if np.isfinite(value)]
    total = sum(data)
    richness = sum(1 for value in data if value > 0.0)
    if total <= 0.0 or richness == 0:
        return {"simpson": 0.0, "inverse_simpson": 0.0, "evenness": 0.0, "richness": 0.0}
    simpson = sum((value / total) ** 2 for value in data)
    inverse = 1.0 / simpson
    return {
        "simpson": simpson,
        "inverse_simpson": inverse,
        "evenness": inverse / richness,
        "richness": float(richness),
    }


HAND_SEQUENCE = "ACGTACG"
HAND_COUNTS = {"AC": 2, "CG": 2, "GT": 1, "TA": 1}


def test_dinucleotide_hand_computed_sequence():
    ctx = Ctx()
    SequenceDinucleotideFrequencyStep().run(ctx, [_sequence_form([HAND_SEQUENCE])])
    out = ctx["dinucleotide_frequency"]

    assert list(out.dims) == ["dinucleotide", "statistic"]
    assert out.data.shape == (16, 3)
    assert list(out.labels["dinucleotide"]) == list(DINUCLEOTIDES)
    assert list(out.labels["statistic"]) == ["count", "frequency", "cpg_observed_expected"]

    for name in DINUCLEOTIDES:
        count = float(out.data[out.labels["dinucleotide"][name], 0])
        assert count == float(HAND_COUNTS.get(name, 0)), name

    counts, frequencies, ratio = _dinucleotide_oracle([HAND_SEQUENCE])
    for name in DINUCLEOTIDES:
        row = out.labels["dinucleotide"][name]
        assert out.data[row, 0] == counts[name]
        assert out.data[row, 1] == pytest.approx(frequencies[name], abs=1e-12)
        expected_ratio = ratio if name == "CG" else 0.0
        assert out.data[row, 2] == pytest.approx(expected_ratio, abs=1e-12)

    assert float(out.data[:, 1].sum()) == pytest.approx(1.0, abs=1e-12)
    assert out.data[out.labels["dinucleotide"]["CG"], 2] == pytest.approx(49.0 / 12.0, rel=1e-12)
    assert out.info["n_windows"] == 6
    assert out.info["n_bases"] == 7
    assert out.info["n_sequences"] == 1


def test_dinucleotide_ignores_case_and_non_acgt():
    plain_ctx = Ctx()
    SequenceDinucleotideFrequencyStep().run(plain_ctx, [_sequence_form(["acgtACGT"])])
    noisy_ctx = Ctx()
    SequenceDinucleotideFrequencyStep().run(noisy_ctx, [_sequence_form(["acgtNNACGT"])])

    plain = plain_ctx["dinucleotide_frequency"].data
    noisy = noisy_ctx["dinucleotide_frequency"].data
    assert np.array_equal(plain, noisy)
    counts, _frequencies, _ratio = _dinucleotide_oracle(["acgtACGT"])
    assert counts["GT"] == 2
    assert counts["AC"] == 2
    assert counts["CG"] == 2
    assert plain[plain_ctx["dinucleotide_frequency"].labels["dinucleotide"]["CG"], 2] == pytest.approx(
        32.0 / 7.0, rel=1e-12
    )


def test_dinucleotide_empty_window_case():
    ctx = Ctx()
    SequenceDinucleotideFrequencyStep().run(ctx, [_sequence_form(["NNN"])])
    out = ctx["dinucleotide_frequency"]
    assert np.all(out.data == 0.0)
    assert out.info["n_windows"] == 0

    with pytest.raises(StepError):
        SequenceDinucleotideFrequencyStep().run(Ctx(), [])


def test_gini_exact_quarter():
    ctx = Ctx()
    NumericGiniCoefficientStep().run(ctx, [_vector([1, 2, 3, 4])])
    out = ctx["gini_coefficient"]

    assert list(out.dims) == ["entry", "statistic"]
    assert out.data.shape == (1, 4)
    assert list(out.labels["entry"]) == ["gini"]
    assert list(out.labels["statistic"]) == ["gini", "n", "total", "mean"]
    assert _stat(out, "gini") == 0.25
    assert _stat(out, "n") == 4.0
    assert _stat(out, "total") == 10.0
    assert _stat(out, "mean") == 2.5
    assert _stat(out, "gini") == pytest.approx(_gini_pairwise([1, 2, 3, 4]), abs=1e-12)
    assert _stat(out, "gini") == pytest.approx(_gini_sorted([1, 2, 3, 4]), abs=1e-12)


def test_gini_degenerate_and_float_values():
    zeros = Ctx()
    NumericGiniCoefficientStep().run(zeros, [_vector([0.0, 0.0, 0.0])])
    out = zeros["gini_coefficient"]
    assert _stat(out, "gini") == 0.0
    assert _stat(out, "mean") == 0.0
    assert _stat(out, "n") == 3.0

    empty = Ctx()
    NumericGiniCoefficientStep().run(empty, [_vector([])])
    assert all(_stat(empty["gini_coefficient"], name) == 0.0 for name in ("gini", "n", "total", "mean"))

    values = [0.5, 1.5, 2.25, 3.0]
    scaled = Ctx()
    NumericGiniCoefficientStep().run(scaled, [_vector(values)])
    assert _stat(scaled["gini_coefficient"], "gini") == pytest.approx(_gini_pairwise(values), abs=1e-9)
    assert _stat(scaled["gini_coefficient"], "gini") == pytest.approx(_gini_sorted(values), abs=1e-9)

    with pytest.raises(StepError, match="non-negative"):
        NumericGiniCoefficientStep().run(Ctx(), [_vector([1.0, -2.0])])


def test_simpson_hand_computed_vector():
    ctx = Ctx()
    DiversitySimpsonStep().run(ctx, [_vector([5, 0, 5], dim="abundance")])
    out = ctx["simpson_diversity"]

    assert list(out.dims) == ["entry", "statistic"]
    assert out.data.shape == (1, 4)
    assert list(out.labels["entry"]) == ["simpson"]
    assert list(out.labels["statistic"]) == ["simpson", "inverse_simpson", "evenness", "richness"]
    assert _stat(out, "simpson") == pytest.approx(0.5, abs=1e-12)
    assert _stat(out, "inverse_simpson") == pytest.approx(2.0, abs=1e-12)
    assert _stat(out, "evenness") == pytest.approx(1.0, abs=1e-12)
    assert _stat(out, "richness") == 2.0

    oracle = _simpson_oracle([5, 0, 5])
    for name, value in oracle.items():
        assert _stat(out, name) == pytest.approx(value, abs=1e-9)


def test_simpson_degenerate_vectors():
    zeros = Ctx()
    DiversitySimpsonStep().run(zeros, [_vector([0.0, 0.0], dim="abundance")])
    assert all(
        _stat(zeros["simpson_diversity"], name) == 0.0
        for name in ("simpson", "inverse_simpson", "evenness", "richness")
    )

    empty = Ctx()
    DiversitySimpsonStep().run(empty, [_vector([], dim="abundance")])
    assert _stat(empty["simpson_diversity"], "richness") == 0.0

    with pytest.raises(StepError, match="non-negative"):
        DiversitySimpsonStep().run(Ctx(), [_vector([2.0, -1.0], dim="abundance")])


def test_operators_reject_wrong_arity_and_dims():
    with pytest.raises(StepError):
        NumericGiniCoefficientStep().run(Ctx(), [])
    with pytest.raises(StepError):
        DiversitySimpsonStep().run(Ctx(), [])
    with pytest.raises(StepError):
        NumericGiniCoefficientStep().run(Ctx(), [_vector([1.0, 2.0], dim="sample")])
    with pytest.raises(StepError):
        DiversitySimpsonStep().run(Ctx(), [_vector([1.0, 2.0], dim="sample")])
