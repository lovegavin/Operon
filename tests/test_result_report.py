"""ResultReport closes a workflow with a file report."""

from __future__ import annotations

import numpy as np

from src.task.step.steps.result_report import ResultReportStep


class _Stub:
    def __init__(self) -> None:
        self.shape = (4, 3)
        self.dims = ("sample", "feature")
        self.labels = {"feature": {"a": 0, "b": 1, "c": 2}}
        self.info = {"source": "unit-test"}
        self.data = np.arange(12, dtype=float).reshape(4, 3)


def test_definition_declares_a_file_output() -> None:
    definition = ResultReportStep.definition
    assert definition["id"] == "result_report"
    assert definition["outputs"] == ["output"]
    assert definition["output_parameter"] == "output"
    assert definition["contracts"]["output"]["mode"] == "declare"
    assert definition["contracts"]["output"]["schema"]["kind"] == "file"


def test_summary_reports_shape_dims_and_labels() -> None:
    step = ResultReportStep.__new__(ResultReportStep)
    rows = step._summary(_Stub())
    table = {row[0]: row[1] for row in rows}
    assert table["shape"] == "4x3"
    assert table["dims"] == "sample, feature"
    assert table["labels[feature]"] == "3 entries"
    assert table["info[source]"] == "unit-test"
    assert "preview" in table
