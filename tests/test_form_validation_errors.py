"""ValidationError messages stay readable for operators and readers."""

from __future__ import annotations

import numpy as np
import pytest

from src.core.errors.errors import OperonError, ValidationError
from src.core.forms.form import Form


def test_operon_error_joins_its_arguments():
    error = ValidationError("Form", "detail text")
    assert str(error) == "Form: detail text"


def test_single_argument_errors_keep_their_text():
    assert str(OperonError("plain message")) == "plain message"


def test_orphan_encoder_column_names_the_column_and_dim():
    form = Form(
        data=np.zeros((2, 2)),
        dims=["sample", "feature"],
        labels={"sample": {"s1": 0, "s2": 1}, "feature": {"a": 0, "b": 1}},
        info={"encoders": {"feature": {"alpha": "value"}}},
    )
    with pytest.raises(ValidationError) as caught:
        form.validate()
    message = str(caught.value)
    assert "alpha" in message
    assert "feature" in message
    assert "has no values" in message
