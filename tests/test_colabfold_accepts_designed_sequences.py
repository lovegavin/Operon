"""ProteinMPNN designs must feed ColabFold without a hand-written adapter."""

from __future__ import annotations

import numpy as np
import pytest

from src.core.contracts import compatible, describe_form
from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.steps.colabfold_predict import ColabfoldPredictStep, sequence_for_colabfold


def designed_form(sequences: list[str]) -> Form:
    """The shape ``proteinmpnn_design`` hands downstream."""

    return Form(
        data=np.zeros((len(sequences), 3), dtype=np.float32),
        dims=["design", "statistic"],
        labels={
            "design": {f"design_{i}": i for i in range(len(sequences))},
            "statistic": {"score": 0, "global_score": 1, "seq_recovery": 2},
        },
        info={"sequences": sequences, "headers": [f"score=0.{i}" for i in range(len(sequences))]},
    )


def test_design_output_is_compatible_with_the_predictor_input():
    requirement = ColabfoldPredictStep.definition["contracts"]["inputs"][0]
    verdict = compatible(describe_form(designed_form(["MSKGEELFT"])), requirement)
    assert verdict["status"] == "compatible", verdict["reasons"]


def test_sequence_for_colabfold_reads_the_design_form():
    assert sequence_for_colabfold(designed_form(["MSKGEELFT"])) == "MSKGEELFT"


def test_sequence_for_colabfold_names_the_requested_index():
    with pytest.raises(StepError, match="outside the 1 sequences"):
        sequence_for_colabfold(designed_form(["MSKGEELFT"]), index=1)


def test_sequence_index_picks_one_of_several_designs():
    from src.core.errors import StepError

    form = designed_form(["MSKGEELFT", "MSKGEELFA"])
    assert sequence_for_colabfold(form, index=1) == "MSKGEELFA"
    with pytest.raises(StepError, match="outside the 2 sequences"):
        sequence_for_colabfold(form, index=2)
