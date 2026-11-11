"""Contract regressions for the interface operators (BE-01/BE-02/BE-06)."""

from __future__ import annotations

import pytest

from src.core.contracts import compatible
from src.task.step.steps.export_results import ExportResultsStep
from src.task.step.steps.interface_alanine_scan import InterfaceAlanineScanStep
from src.task.step.steps.interface_mmgbsa_delta import InterfaceMmgbsaDeltaStep
from src.task.step.steps.structure_interface_core import StructureInterfaceCoreStep
from src.task.step.steps.structure_interface_residue_energy import (
    StructureInterfaceResidueEnergyStep,
)
from src.task.step.steps.structure_paratope_predict import StructureParatopePredictStep

CASES = [
    (
        StructureInterfaceCoreStep,
        ["delta_sasa", "isolated_sasa", "buried_fraction", "is_core"],
    ),
    (
        StructureParatopePredictStep,
        ["n_contacts", "min_distance", "is_paratope", "cdr_index"],
    ),
    (
        StructureInterfaceResidueEnergyStep,
        ["coulomb_kj", "lj_kj", "total_kj", "n_contacts"],
    ),
    (
        InterfaceAlanineScanStep,
        ["wt_delta_kj", "mutant_delta_kj", "delta_delta_kj"],
    ),
    (
        InterfaceMmgbsaDeltaStep,
        ["complex_kj", "binder_kj", "target_kj", "delta_kj"],
    ),
]


@pytest.mark.parametrize("step_cls,expected", CASES)
def test_interface_statistics_are_static_labels(step_cls, expected):
    schema = step_cls.definition["contracts"]["output"]["schema"]
    assert schema["numeric"] is True
    assert schema["ndim"] == 2
    assert schema["labels"]["statistic"] == expected
    result = compatible(
        schema,
        {
            "ndim": 2,
            "numeric": True,
            "dims": [schema["dims"][0]],
            "labels_axis": [{"axis": 1, "values": [expected[-1]]}],
        },
    )
    assert result["status"] == "compatible"
    assert not any("需要字段" in reason for reason in result["reasons"])


@pytest.mark.parametrize(
    "step_cls",
    [
        InterfaceAlanineScanStep,
        InterfaceMmgbsaDeltaStep,
        StructureInterfaceResidueEnergyStep,
    ],
)
def test_interface_operators_declare_openmm_dependencies(step_cls):
    dependencies = step_cls.definition["dependencies"]
    assert "openmm>=8.0" in dependencies
    assert "pdbfixer>=1.9" in dependencies


def test_export_results_hic_dependency_is_optional():
    dependencies = ExportResultsStep.definition["dependencies"]
    assert not any(item.startswith("hictkpy") for item in dependencies)
