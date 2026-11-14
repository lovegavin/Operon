import json
from pathlib import Path

import numpy as np
import pytest

from src.reader import read_source
from library.seed.src.task.step.steps.structure_convert_format import StructureConvertFormatStep

ROOT = Path(__file__).resolve().parents[1]


class Ctx(dict):
    def __init__(self, base, params=None):
        super().__init__()
        self.step_params = params or {"filename": "converted.pdb"}
        self.base = Path(base)
        self.artifacts = {}

    def artifact_path(self, name):
        return str(self.base / name)


def test_environment_manifest_012():
    data = json.loads((ROOT / "library/seed/operon/environments.json").read_text())
    boltz = data["environments"]["boltz"]
    assert "libstdcxx-ng" in boltz["conda_packages"]
    esmfold = data["environments"]["esmfold"]
    assert esmfold["python"] == "3.11"
    assert "fair-esm==2.0.0" in esmfold["pip_pypi"]
    assert esmfold["wired"] is True


def test_convert_pdb_roundtrip(tmp_path):
    source = ROOT / "tests/fixtures/vhh_1mel.pdb"
    form = read_source(source, ["atom", "field"], {"atom": "auto", "field": "builtin"})
    original = form.data.shape[0]
    assert original > 100 and list(form.dims) == ["atom", "field"]

    ctx = Ctx(tmp_path)
    step = StructureConvertFormatStep()
    step.run(ctx, [form])
    out = ctx["output"]
    assert list(out.dims) == ["atom", "field"]
    assert out.data.shape[0] == original
    for name in ("x", "y", "z", "atom_name", "resname", "chain", "residue_number", "element"):
        assert name in out.labels["field"]
    assert np.allclose(
        np.asarray(out.data[:, out.labels["field"]["x"]], dtype=float),
        np.asarray(form.data[:, form.labels["field"]["x"]], dtype=float),
    )

    files = step.export(ctx)["result_files"]
    assert len(files) == 1 and files[0]["bytes"] > 1000
    text = Path(files[0]["path"]).read_text()
    assert text.startswith("ATOM")
    assert text.rstrip().endswith("END")
    assert len([line for line in text.splitlines() if line.startswith("ATOM")]) == original


def test_convert_mmcif_columns(tmp_path):
    cif = tmp_path / "mini.cif"
    cif.write_text(
        "data_x\n"
        "loop_\n"
        "_atom_site.group_PDB\n"
        "_atom_site.id\n"
        "_atom_site.type_symbol\n"
        "_atom_site.label_atom_id\n"
        "_atom_site.label_comp_id\n"
        "_atom_site.label_asym_id\n"
        "_atom_site.label_seq_id\n"
        "_atom_site.Cartn_x\n"
        "_atom_site.Cartn_y\n"
        "_atom_site.Cartn_z\n"
        "_atom_site.label_alt_id\n"
        "ATOM 1 N N ALA A 1 0.000 0.000 0.000 .\n"
        "ATOM 2 CA C ALA A 1 1.458 0.000 0.000 .\n"
        "ATOM 3 C C ALA A 1 2.009 1.420 0.000 .\n"
    )
    form = read_source(cif, ["atom", "field"], {"atom": "auto", "field": "builtin"})
    ctx = Ctx(tmp_path / "out")
    StructureConvertFormatStep().run(ctx, [form])
    out = ctx["output"]
    assert out.data.shape[0] == 3
    assert np.allclose(out.data[:, out.labels["field"]["y"]], [0.0, 0.0, 1.42], atol=1e-4)
