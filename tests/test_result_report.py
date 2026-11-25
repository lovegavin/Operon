"""ResultReport closes a workflow with a file report."""

from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.step.steps.result_report import ResultReportStep


class _Stub:
    def __init__(self) -> None:
        self.shape = (4, 3)
        self.dims = ("sample", "feature")
        self.labels = {"feature": {"a": 0, "b": 1, "c": 2}}
        self.info = {"source": "unit-test"}
        self.data = np.arange(12, dtype=float).reshape(4, 3)


def test_definition_is_a_terminal_report_step() -> None:
    definition = ResultReportStep.definition
    assert definition["id"] == "result_report"
    assert definition["outputs"] == []
    assert definition["output_parameter"] is None
    assert definition["data_formats"]["outputs"] == []
    assert definition["contracts"]["output"] == {"mode": "report"}


def test_summary_reports_shape_dims_and_labels() -> None:
    step = ResultReportStep.__new__(ResultReportStep)
    rows = step._summary(_Stub())
    table = {row[0]: row[1] for row in rows}
    assert table["shape"] == "4x3"
    assert table["dims"] == "sample, feature"
    assert table["labels[feature]"] == "3 entries"
    assert table["info[source]"] == "unit-test"
    assert "preview" in table


def test_run_registers_a_native_report_without_an_output_port(tmp_path) -> None:
    class _Ctx:
        def __init__(self) -> None:
            self.step_params = {"format": "csv"}
            self.task_dir = tmp_path
            self.artifacts: dict = {}

        def __setitem__(self, key, value) -> None:
            raise AssertionError(f"terminal step must not register output {key!r}")

    form = Form(
        data=np.arange(12, dtype=float).reshape(4, 3),
        dims=["sample", "feature"],
        labels={"feature": {"a": 0, "b": 1, "c": 2}},
        info={"source": "unit-test"},
    )
    step = ResultReportStep.__new__(ResultReportStep)
    ctx = _Ctx()
    step.run(ctx, [form])

    native = ctx.artifacts["native_results"]["report"]
    assert len(native["files"]) == 1
    assert native["files"][0]["format"] == "csv"
    assert step._result_files == native["files"]
    report = tmp_path / "artifacts" / "report"
    written = list(report.glob("*/report.csv"))
    assert len(written) == 1
    text = written[0].read_text(encoding="utf-8")
    assert "shape,4x3" in text
