# tests/test_engine_output_formats.py
"""The output validator must resolve dynamic output names to a declared format."""

from src.task.runner import output_format_for

ANNOTATION = {"kind": "form", "dims": ["interval", "statistic"]}
COVERAGE = {"kind": "form", "dims": ["region", "statistic"]}


def test_dynamic_name_uses_the_only_declared_format():
    spec = output_format_for(["annotation", "n1"], [ANNOTATION], "n1")
    assert spec is ANNOTATION


def test_declared_names_keep_their_own_format():
    formats = [ANNOTATION, COVERAGE]
    assert output_format_for(["annotation", "coverage"], formats, "annotation") is ANNOTATION
    assert output_format_for(["annotation", "coverage"], formats, "coverage") is COVERAGE


def test_extra_dynamic_names_reuse_the_last_format():
    spec = output_format_for(["annotation", "n1", "n2"], [ANNOTATION], "n2")
    assert spec is ANNOTATION


def test_missing_formats_yield_none():
    assert output_format_for(["annotation", "n1"], [], "n1") is None
