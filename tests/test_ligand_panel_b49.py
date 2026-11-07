"""Unit tests for the b49 ligand property operators."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.reader.readers._table_common import table_form
from src.task.context import Context
from src.task.step.steps.ligand_brics_fragments import LigandBricsFragmentsStep
from src.task.step.steps.ligand_exact_mass import LigandExactMassStep
from src.task.step.steps.ligand_isotope_pattern import LigandIsotopePatternStep
from src.task.step.steps.ligand_molecular_formula import LigandMolecularFormulaStep
from src.task.step.steps.ligand_rgroup_decomposition import LigandRgroupDecompositionStep

MOLECULES = [
    ("CC(=O)Oc1ccccc1C(=O)O", "aspirin"),
    ("Cn1cnc2c1c(=O)n(C)c(=O)n2C", "caffeine"),
    ("CCO", "ethanol"),
    ("CC(=O)Oc1ccccc1", "phenyl_acetate"),
    ("Cc1ccccc1", "toluene"),
]


class Ctx(Context):
    def __init__(self, params, root):
        self.step_params = params
        self._values = {}
        self._root = root

    def __setitem__(self, key, value):
        self._values[key] = value

    def __getitem__(self, key):
        return self._values[key]


def smiles_form():
    rows = []
    for smiles, name in MOLECULES:
        rows.append([name, smiles, float(len(smiles)), float(sum(1 for c in smiles if c.isalpha() and not c.islower()))])
    frame = pd.DataFrame(rows, columns=["molecule", "smiles", "length", "heavy_atoms"])
    return table_form(
        frame,
        ["molecule", "field"],
        {"molecule": "auto", "field": "builtin"},
        "SMILES",
        encoders_cfg={},
        row_labels=[name for _smiles, name in MOLECULES],
    )


def run(step, params, tmp_path):
    ctx = Ctx(params, tmp_path / "out")
    step.name = step.definition["id"]
    step.run(ctx, [smiles_form()])
    return ctx[params["output"]]


def column(form, name):
    for dimension, labels in form.labels.items():
        if dimension != "molecule" and name in labels:
            return np.asarray(form.data)[:, labels[name]]
    raise KeyError(name)


def test_formula_counts_include_hydrogens(tmp_path):
    form = run(LigandMolecularFormulaStep(), {"molecule_dim": "molecule", "field_dim": "field", "output": "formula"}, tmp_path)
    assert column(form, "C")[0] == 9
    assert column(form, "O")[0] == 4
    assert column(form, "heavy_atoms")[0] == 13
    assert column(form, "total_atoms")[0] == 21
    assert form.info["formula"][0] == "C9H8O4"
    assert form.info["formula"][1] == "C8H10N4O2"


def test_exact_mass_matches_pyteomics(tmp_path):
    mass = pytest.importorskip("pyteomics.mass")
    form = run(LigandExactMassStep(), {"molecule_dim": "molecule", "field_dim": "field", "output": "mass"}, tmp_path)
    expected = mass.calculate_mass(formula="C9H8O4")
    assert column(form, "exact_mass")[0] == pytest.approx(expected, abs=1e-4)
    assert column(form, "average_mass")[0] == pytest.approx(180.159, abs=0.01)
    assert column(form, "nominal_mass")[0] == 180


def test_brics_fragments(tmp_path):
    form = run(LigandBricsFragmentsStep(), {"molecule_dim": "molecule", "field_dim": "field", "output": "brics"}, tmp_path)
    assert column(form, "n_fragments")[0] == 4
    assert column(form, "n_unique_fragments")[0] == 4
    assert form.info["fragments"][0]
    assert column(form, "n_fragments")[2] == 1


def test_rgroup_decomposition_marks_unmatched(tmp_path):
    params = {"molecule_dim": "molecule", "field_dim": "field", "output": "rgroups", "scaffold": "c1ccccc1[*:1]"}
    form = run(LigandRgroupDecompositionStep(), params, tmp_path)
    matched = column(form, "matched")
    assert matched.tolist() == [1.0, 0.0, 0.0, 1.0, 1.0]
    assert column(form, "R1")[0] == 4
    assert form.info["rgroup_smiles"][0]["R1"]
    assert form.info["rgroup_smiles"][2] == {}


def test_isotope_pattern_base_peak_and_m_plus_one(tmp_path):
    mass = pytest.importorskip("pyteomics.mass")
    form = run(LigandIsotopePatternStep(), {"molecule_dim": "molecule", "field_dim": "field", "output": "isotopes", "max_peaks": 6, "charge": 1}, tmp_path)
    assert column(form, "rel_0")[0] == pytest.approx(1.0)
    assert column(form, "mz_0")[0] == pytest.approx(181.04953, abs=1e-3)
    assert column(form, "rel_1")[0] == pytest.approx(0.0973, abs=0.01)
    # independent oracle: pyteomics abundance for the M+1 isotopologue
    isotopologues = list(mass.isotopologues("C9H8O4", report_abundance=True))
    by_mass = sorted(isotopologues, key=lambda item: mass.calculate_mass(item[0]))
    base = by_mass[0][1]
    m1 = by_mass[1][1] / base
    assert column(form, "rel_1")[0] == pytest.approx(m1, abs=0.02)


def test_invalid_smiles_raises(tmp_path):
    frame = pd.DataFrame([["bad", "not_a_smiles", 12.0, 3.0]], columns=["molecule", "smiles", "length", "heavy_atoms"])
    form = table_form(frame, ["molecule", "field"], {"molecule": "auto", "field": "builtin"}, "SMILES", encoders_cfg={}, row_labels=["bad"])
    from src.core import StepError
    ctx = Ctx({"molecule_dim": "molecule", "field_dim": "field", "output": "mass"}, tmp_path / "out")
    with pytest.raises(StepError):
        LigandExactMassStep().run(ctx, [form])
