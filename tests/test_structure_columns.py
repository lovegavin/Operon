"""A structure read from mmCIF keeps its coordinates when written back."""

from pathlib import Path

import numpy as np

from src.core.forms.form import Form
from src.task.step.steps._protein_common import column_index, structure_file


def mmcif_like_pdb_form(tmp_path: Path) -> Form:
    labels = {
        "Cartn_x": 0,
        "Cartn_y": 1,
        "Cartn_z": 2,
        "label_atom_id": 3,
        "label_comp_id": 4,
        "label_asym_id": 5,
        "label_seq_id": 6,
        "occupancy": 7,
    }
    data = np.array(
        [
            [11.104, 6.134, -6.504, 0, 0, 0, 1, 1.0],
            [11.639, 6.071, -5.147, 1, 0, 0, 1, 1.0],
        ],
        dtype=float,
    )
    info = {
        "encoders": {
            "field": {
                "label_atom_id": _Encoder(["N", "CA"]),
                "label_comp_id": _Encoder(["ALA", "ALA"]),
                "label_asym_id": _Encoder(["A", "A"]),
            }
        }
    }
    return Form(data=data, dims=["atom", "field"], labels={"field": labels}, info=info)


class _Encoder:
    def __init__(self, values):
        self._values = list(values)

    def inverse_transform(self, values):
        return [self._values[int(value)] for value in values]


def test_column_index_accepts_the_mmcif_spelling():
    form = mmcif_like_pdb_form(Path("/tmp"))
    assert column_index(form, "field", "x") == 0
    assert column_index(form, "field", "y") == 1
    assert column_index(form, "field", "z") == 2
    assert column_index(form, "field", "atom_name") == 3
    assert column_index(form, "field", "residue_number") == 6


def test_written_pdb_keeps_the_real_coordinates(tmp_path):
    form = mmcif_like_pdb_form(tmp_path)
    written = structure_file(form, "", "unit")
    assert written is not None
    text = Path(written).read_text()
    assert "  11.104" in text
    assert "  11.639" in text
    assert "   1.000   1.000   1.000" not in text
