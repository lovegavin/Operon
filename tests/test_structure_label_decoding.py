"""Tests build forms by hand, so the PDB writing path is exercised without a reader."""

from __future__ import annotations

import numpy as np
import pytest

from src.core import Form
from src.core.encoding import LabelEncoder
from src.core.errors import StepError
from src.task.step.steps import structure_convert_format as converter
from src.task.step.steps import structure_extract_chain as extractor

ROWS = [
    (0.0, 0.0, 0.0, 1, "ALA", "A", "CA", "C"),
    (3.8, 0.0, 0.0, 2, "GLY", "A", "CA", "C"),
    (0.0, 3.8, 0.0, 1, "SER", "B", "CA", "C"),
]


def structure_form(chain_column: str = "chain") -> Form:
    columns = ["x", "y", "z", "residue_number", chain_column, "resname", "atom_name", "element"]
    arrays = []
    encoders = {}
    for name in columns:
        values = []
        for row in ROWS:
            if name == "x":
                values.append(row[0])
            elif name == "y":
                values.append(row[1])
            elif name == "z":
                values.append(row[2])
            elif name == "residue_number":
                values.append(row[3])
            elif name == "resname":
                values.append(row[4])
            elif name in ("chain", "label_asym_id"):
                values.append(row[5])
            elif name == "atom_name":
                values.append(row[6])
            else:
                values.append(row[7])
        if name in ("x", "y", "z", "residue_number"):
            arrays.append(np.asarray(values, dtype=np.float64))
            continue
        encoder = LabelEncoder()
        arrays.append(np.asarray(encoder.fit_transform(values), dtype=np.float64))
        encoders[name] = encoder
    return Form(
        data=np.column_stack(arrays).astype(np.float32),
        dims=["atom", "field"],
        labels={
            "atom": {f"atom:{index}": index for index in range(len(ROWS))},
            "field": {name: index for index, name in enumerate(columns)},
        },
        info={"missing_code": np.nan, "encoders": {"field": encoders}},
    )


class Ctx:
    def __init__(self, params, task_dir):
        self.step_params = params
        self.task_dir = task_dir
        self._values = {}

    def __setitem__(self, key, value):
        self._values[key] = value

    def __getitem__(self, key):
        return self._values[key]


def _identity_reader(path, dims, labels):
    return Form(
        data=np.zeros((1, 2), dtype=np.float32),
        dims=list(dims),
        labels={dims[0]: {"0": 0}, dims[1]: {}},
        info={},
    )


def test_decoded_columns_restores_chain_letters():
    form = structure_form()
    labels = converter._labels(form, "field")
    chains = [str(value) for value in converter.decoded_columns(form, "field", labels, "chain")]
    assert chains == ["A", "A", "B"]


def test_decoded_columns_reads_the_label_asym_id_alias():
    form = structure_form("label_asym_id")
    labels = converter._labels(form, "field")
    chains = [str(value) for value in converter.decoded_columns(form, "field", labels, "chain")]
    assert chains == ["A", "A", "B"]


def test_convert_writes_chain_letters_not_codes(tmp_path, monkeypatch):
    monkeypatch.setattr(converter, "read_source", _identity_reader)
    form = structure_form()
    ctx = Ctx({"output": "out"}, tmp_path)
    converter.StructureConvertFormatStep().run(ctx, [form])
    path = next((tmp_path / "artifacts").rglob("*.pdb"))
    written = path.read_text(encoding="ascii")
    lines = [line for line in written.splitlines() if line.startswith("ATOM")]
    assert [line[21] for line in lines] == ["A", "A", "B"]
    assert "ALA" in written and "SER" in written


def test_extract_reads_a_label_asym_id_form(tmp_path, monkeypatch):
    monkeypatch.setattr(extractor, "read_source", _identity_reader)
    form = structure_form("label_asym_id")
    ctx = Ctx({"output": "out", "chains": "B"}, tmp_path)
    extractor.StructureExtractChainStep().run(ctx, [form])
    path = next((tmp_path / "artifacts").rglob("*.pdb"))
    lines = [line for line in path.read_text(encoding="ascii").splitlines() if line.startswith("ATOM")]
    assert len(lines) == 1
    assert lines[0][21] == "B"


def test_extract_reports_a_missing_chain_column(tmp_path):
    form = structure_form()
    del form.labels["field"]["chain"]
    ctx = Ctx({"output": "out"}, tmp_path)
    with pytest.raises(StepError, match="no chain column"):
        extractor.StructureExtractChainStep().run(ctx, [form])


def test_selected_indices_names_the_chains_it_found():
    with pytest.raises(StepError) as error:
        extractor.selected_indices(["A", "B"], ["C"])
    message = str(error.value)
    assert "no atoms belong to chains C" in message
    assert "the input carries A, B" in message


def test_fmt_atom_prints_the_decoded_chain():
    line = converter._fmt_atom("CA", "ALA", "A", 1, 0.0, 0.0, 0.0, 1.0, 0.0, " C", "", "", 1, False)
    assert line[21] == "A"


def _form_with_null_residues():
    form = structure_form()
    encoder = LabelEncoder()
    codes = encoder.fit_transform([".", "2", "."])
    form.data[:, 3] = np.asarray(codes, dtype=np.float32)
    form.info["encoders"]["field"]["residue_number"] = encoder
    return form


def test_convert_tolerates_null_residue_numbers(tmp_path):
    form = _form_with_null_residues()
    ctx = Ctx({"output": "out"}, tmp_path)
    converter.StructureConvertFormatStep().run(ctx, [form])
    path = next((tmp_path / "artifacts").rglob("*.pdb"))
    lines = [line for line in path.read_text(encoding="ascii").splitlines() if line.startswith("ATOM")]
    assert len(lines) == 3


def test_extract_tolerates_null_residue_numbers(tmp_path, monkeypatch):
    monkeypatch.setattr(extractor, "read_source", _identity_reader)
    form = _form_with_null_residues()
    ctx = Ctx({"output": "out", "chains": "B"}, tmp_path)
    extractor.StructureExtractChainStep().run(ctx, [form])
    path = next((tmp_path / "artifacts").rglob("*.pdb"))
    lines = [line for line in path.read_text(encoding="ascii").splitlines() if line.startswith("ATOM")]
    assert len(lines) == 1
    assert lines[0][21] == "B"


def _form_with_hetero_rows():
    form = structure_form()
    encoder = LabelEncoder()
    codes = encoder.fit_transform(["ATOM", "HETATM", "ATOM"])
    form.data = np.column_stack([form.data, np.asarray(codes, dtype=np.float32)])
    form.labels["field"]["group_pdb"] = form.data.shape[1] - 1
    form.info["encoders"]["field"]["group_pdb"] = encoder
    return form


def test_convert_skips_hetero_rows_by_default(tmp_path):
    form = _form_with_hetero_rows()
    ctx = Ctx({"output": "out"}, tmp_path)
    converter.StructureConvertFormatStep().run(ctx, [form])
    written = next((tmp_path / "artifacts").rglob("*.pdb")).read_text(encoding="ascii")
    lines = [line for line in written.splitlines() if line.startswith(("ATOM", "HETATM"))]
    assert len(lines) == 2
    assert [line[21] for line in lines] == ["A", "B"]
    assert "HETATM" not in written


def test_convert_keeps_hetero_rows_when_asked(tmp_path, monkeypatch):
    monkeypatch.setattr(converter, "read_source", _identity_reader)
    form = _form_with_hetero_rows()
    ctx = Ctx({"output": "out", "include_hetatm": True}, tmp_path)
    converter.StructureConvertFormatStep().run(ctx, [form])
    written = next((tmp_path / "artifacts").rglob("*.pdb")).read_text(encoding="ascii")
    assert written.count("HETATM") == 1
    assert written.count("ATOM  ") == 2


def test_extract_skips_hetero_rows_by_default(tmp_path, monkeypatch):
    monkeypatch.setattr(extractor, "read_source", _identity_reader)
    form = _form_with_hetero_rows()
    ctx = Ctx({"output": "out", "chains": "A"}, tmp_path)
    extractor.StructureExtractChainStep().run(ctx, [form])
    lines = [line for line in next((tmp_path / "artifacts").rglob("*.pdb")).read_text(encoding="ascii").splitlines()
             if line.startswith(("ATOM", "HETATM"))]
    assert len(lines) == 1
    assert lines[0].startswith("ATOM")
