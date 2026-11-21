"""Reader-declared label defaults survive an empty workflow mapping."""
from pathlib import Path

import numpy as np

from src.reader import read_source

CSV = "sample,x0,x1\ns0,1,2\ns1,3,4\n"


def test_empty_labels_inherit_reader_defaults(tmp_path: Path):
    path = tmp_path / "matrix.csv"
    path.write_text(CSV, encoding="utf-8")
    form = read_source(path, ["sample", "feature"], {}, reader_id="CsvReader")
    # the reader declares feature='builtin', so the header names the axis
    assert list(form.labels["feature"]) == ["sample", "x0", "x1"]
    # sample='auto' has no label column to consume, so positions remain
    assert list(form.labels["sample"]) == ["0", "1"]
    assert np.asarray(form.data).shape == (2, 3)


def test_explicit_label_rule_still_wins(tmp_path: Path):
    path = tmp_path / "matrix.csv"
    path.write_text(CSV, encoding="utf-8")
    form = read_source(path, ["sample", "feature"], {"sample": {"feature": 0}}, reader_id="CsvReader")
    assert list(form.labels["sample"]) == ["s0", "s1"]
    assert list(form.labels["feature"]) == ["x0", "x1"]
    assert np.asarray(form.data).shape == (2, 2)


def test_mapping_for_unknown_dimension_still_rejected(tmp_path: Path):
    path = tmp_path / "matrix.csv"
    path.write_text(CSV, encoding="utf-8")
    try:
        read_source(path, ["sample", "feature"], {"row": "auto"}, reader_id="CsvReader")
    except Exception as error:  # ReaderError
        assert "is not one of" in str(error)
    else:  # pragma: no cover - defensive
        raise AssertionError("expected a ReaderError for a foreign dimension")
