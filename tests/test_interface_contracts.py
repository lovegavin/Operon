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
from src.task.step.steps.structure_openmm_energy import StructureOpenmmEnergyStep
from src.task.step.steps.structure_openmm_md_rmsf import StructureOpenmmMdRmsfStep
from src.task.step.steps.structure_openmm_md_stability import StructureOpenmmMdStabilityStep
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
    "step_cls,imports",
    [
        (InterfaceAlanineScanStep, ["openmm"]),
        (InterfaceMmgbsaDeltaStep, ["openmm", "pdbfixer"]),
        (StructureInterfaceResidueEnergyStep, ["openmm", "pdbfixer"]),
        (StructureOpenmmEnergyStep, ["openmm", "pdbfixer"]),
        (StructureOpenmmMdRmsfStep, ["openmm", "pdbfixer"]),
        (StructureOpenmmMdStabilityStep, ["openmm", "pdbfixer"]),
    ],
)
def test_interface_operators_use_openmm81_environment(step_cls, imports):
    definition = step_cls.definition
    assert definition["resources"]["environment"] == "openmm81"
    assert definition["dependency_imports"] == imports
    dependencies = definition["dependencies"]
    assert "openmm==8.1.1" in dependencies
    assert "numpy==1.26.4" in dependencies
    assert not any("pdbfixer" in item for item in dependencies)


def test_export_results_hic_dependency_is_optional():
    dependencies = ExportResultsStep.definition["dependencies"]
    assert not any(item.startswith("hictkpy") for item in dependencies)
