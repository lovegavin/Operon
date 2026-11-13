"""Regression tests for interface alanine-scan quality flags."""

from __future__ import annotations

import pytest

from src.task.step.steps import interface_alanine_scan as module
from src.task.step.steps import interface_mmgbsa_delta as mmgbsa


def _rows():
    return [
        {"chain": "A", "number": 103, "residue": "TYR", "side": "binder", "delta_delta": -9.196},
        {"chain": "B", "number": 103, "residue": "TYR", "side": "binder", "delta_delta": 40.469},
        {"chain": "A", "number": 106, "residue": "TYR", "side": "binder", "delta_delta": -6.309},
        {"chain": "B", "number": 106, "residue": "TYR", "side": "binder", "delta_delta": 18.828},
        {"chain": "A", "number": 105, "residue": "GLY", "side": "binder", "delta_delta": -2.0},
        {"chain": "B", "number": 105, "residue": "GLY", "side": "binder", "delta_delta": 5.0},
        {"chain": "A", "number": 55, "residue": "GLY", "side": "binder", "delta_delta": 1361.856},
        {"chain": "B", "number": 55, "residue": "GLY", "side": "binder", "delta_delta": 309.699},
    ]


def test_replicate_conflicts_are_marked_on_both_copies():
    conflicts = module._replicate_conflicts(_rows())
    assert ("A", 103) in conflicts
    assert ("B", 103) in conflicts
    assert ("A", 106) in conflicts
    assert ("B", 106) in conflicts
    assert ("A", 55) not in conflicts


def test_copy_replicate_quality_reports_pearson_and_warning():
    report, warnings = module.copy_replicate_quality(_rows(), exclude_above=200.0)
    assert report["available"] is True
    assert report["pearson"] == pytest.approx(report["pairs"][0]["pearson"])
    pair = report["pairs"][0]
    assert pair["n_common"] == 3
    assert pair["pearson"] < 0.5
    assert pair["spearman"] < 0.5
    assert pair["sign_conflict_fraction"] > 0.2
    assert warnings and "do not report hotspots" in warnings[0]


def test_alanine_parameters_expose_exclusion_threshold():
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    data = json.loads(
        (root / "library/seed/src/task/step/steps/interface_alanine_scan.InterfaceAlanineScanStep.parameters.json").read_text()
    )
    prop = data["properties"]["max_delta_kj"]
    assert prop["default"] == pytest.approx(50.0)
    assert prop["exclusiveMinimum"] == 0.0


def test_flag_rows_marks_gly55_and_replicate_conflicts():
    rows = _rows()
    module.flag_rows(rows, 200.0)
    by_key = {(row["chain"], row["number"]): row for row in rows}
    assert by_key[("A", 55)]["excluded"] == 1
    assert by_key[("B", 55)]["excluded"] == 1
    assert "max_delta_kj" in by_key[("A", 55)]["excluded_reason"]
    assert by_key[("A", 103)]["replicate_conflict"] == 1
    assert by_key[("B", 103)]["replicate_conflict"] == 1
    assert by_key[("A", 103)]["flag"] == 2
    assert by_key[("A", 55)]["flag"] == 1


def test_mmgbsa_cancellation_warning_is_conditional():
    base = mmgbsa._warnings(-10.0, 10.0, 2.0)
    assert len(base) == 1
    assert "not a measured binding affinity" in base[0]
    warned = mmgbsa._warnings(-1495.333, 1494.098, 2423.0)
    assert len(warned) == 2
    assert "oppose each other" in warned[1]
    assert len(mmgbsa._warnings(10.0, 10.0, 6.0)) == 1
