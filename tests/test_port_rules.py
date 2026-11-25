"""The registry refuses port contracts that hide run data in a path."""
from __future__ import annotations

import json
from pathlib import Path

from operon.port_rules import check_descriptor

FORM_OUTPUT = [{"logical_type": "form", "representations": ["form"]}]
FILE_OUTPUT = [{"logical_type": "file_artifact", "representations": ["file_artifact"]}]
FORM_INPUT = [{"logical_type": "form", "representations": ["form"], "metadata": {}}]


def _operator(**overrides):
    descriptor = {
        "id": "demo_operator",
        "kind": "operator",
        "inputs_arity": 1,
        "data_formats": {"inputs": FORM_INPUT, "outputs": FORM_OUTPUT},
        "parameters_schema": {"properties": {"output": {"type": "string"}}},
    }
    descriptor.update(overrides)
    return descriptor


def _paths(*names):
    return {"properties": {name: {"type": "string"} for name in names}}


def test_a_form_operator_with_no_paths_passes():
    assert check_descriptor(_operator()) == []


def test_a_tool_path_needs_no_port():
    descriptor = _operator(
        inputs_arity=0,
        data_formats={"inputs": [], "outputs": FORM_OUTPUT},
        parameters_schema=_paths("mkdssp_path", "vina_path"),
    )
    assert check_descriptor(descriptor) == []


def test_a_data_path_without_a_port_is_rejected():
    descriptor = _operator(
        inputs_arity=0,
        data_formats={"inputs": [], "outputs": FORM_OUTPUT},
        parameters_schema=_paths("structure_path"),
    )
    issues = check_descriptor(descriptor)
    assert any("structure_path" in issue and "no input port" in issue for issue in issues)


def test_an_unlisted_file_emitter_is_rejected():
    issues = check_descriptor(_operator(data_formats={"inputs": FORM_INPUT, "outputs": FILE_OUTPUT}))
    assert any("recorded necessity" in issue for issue in issues)


def test_a_listed_file_emitter_passes():
    descriptor = _operator(
        id="vcf_filter",
        data_formats={"inputs": FORM_INPUT, "outputs": FILE_OUTPUT},
    )
    assert check_descriptor(descriptor) == []


def test_a_stale_whitelist_entry_is_rejected():
    issues = check_descriptor(_operator(id="vcf_filter"))
    assert any("no longer emits" in issue for issue in issues)


def test_a_converted_emitter_may_not_emit_again():
    descriptor = _operator(id="msa_trim", data_formats={"inputs": FORM_INPUT, "outputs": FILE_OUTPUT})
    assert any("converted" in issue for issue in check_descriptor(descriptor))


def test_a_reader_with_inputs_is_rejected():
    descriptor = {
        "id": "DemoReader",
        "kind": "reader",
        "inputs_arity": 0,
        "data_formats": {"inputs": FORM_INPUT, "outputs": FILE_OUTPUT},
    }
    issues = check_descriptor(descriptor)
    assert any("reader DemoReader declares inputs" in issue for issue in issues)


def test_an_unclassified_path_is_rejected():
    issues = check_descriptor(_operator(inputs_arity=0, data_formats={"inputs": [], "outputs": FORM_OUTPUT}, parameters_schema=_paths("mystery_path")))
    assert any("unclassified" in issue for issue in issues)


def test_the_shipped_catalog_passes_every_rule():
    index = Path(__file__).resolve().parents[1] / "library" / "seed" / "operon" / "builtin_packages.json"
    payload = json.loads(index.read_text(encoding="utf-8"))
    problems = [
        issue
        for package in payload["packages"]
        for descriptor in package["descriptors"]
        for issue in check_descriptor(descriptor)
    ]
    assert problems == []
