"""colabfold_predict: keep the raw multimer string instead of decoded codes."""

from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.step.steps.colabfold_predict import sequence_for_colabfold


def _form(sequences, alphabet_map, data):
    return Form(
        data=np.asarray(data, dtype=np.float32),
        dims=["sequence", "position"],
        labels={"sequence": {"0": 0}, "position": {str(i): i for i in range(len(data[0]))}},
        info={
            "representation": "sequence_codes",
            "alphabet_map": alphabet_map,
            "unknown_code": 21,
            "sequences": sequences,
        },
    )


def test_raw_multimer_sequence_wins_over_decoded_codes():
    form = _form(["ACDE:FG"], {"A": 0, "C": 1, "D": 2, "E": 3, ":": 22, "F": 5, "G": 6}, [[0, 1, 2, 3, 22, 5, 6]])
    assert sequence_for_colabfold(form) == "ACDE:FG"


def test_decoded_codes_are_used_when_no_raw_sequence_is_recorded():
    form = _form([], {"A": 0, "C": 1}, [[0, 1]])
    assert sequence_for_colabfold(form) == "AC"
