"""Numeric ``seqid`` columns must not need a label encoder.

GFF files whose chromosome column is ``21`` rather than ``chr21`` are read as a
numeric column, so the reader publishes no encoder for it.  Both operators used
to fail with ``... 'seqid' column is not encoded`` on such input; the value is a
perfectly good chromosome name, so they decode it from the number instead.
"""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form
from src.reader.readers._encoder import LabelEncoder
from src.task.step.steps.annotation_gaps import AnnotationGapsStep
from src.task.step.steps.gene_structure import GeneStructureStep

FIELDS = (
    "seqid", "source", "type", "start", "end",
    "score", "strand", "phase", "attributes",
)

RECORDS = [
    # seqid, type, start, end, strand, attributes
    ("21", "gene", 1000, 2000, "+", "gene_id=G1"),
    ("21", "exon", 1000, 1200, "+", "gene_id=G1"),
    ("21", "CDS", 1100, 1200, "+", "gene_id=G1"),
    ("21", "exon", 1500, 2000, "+", "gene_id=G1"),
    ("21", "gene", 5000, 5400, "-", "gene_id=G2"),
    ("21", "exon", 5000, 5400, "-", "gene_id=G2"),
]


class Ctx(dict):
    def __init__(self, params=None, task_dir="."):
        super().__init__()
        self.step_params = dict(params or {})
        self.task_dir = task_dir


def _numeric_seqid_form() -> Form:
    """A GFF form whose seqid column is numeric and therefore unencoded."""
    types = sorted({record[1] for record in RECORDS})
    strands = sorted({record[4] for record in RECORDS})
    attributes = sorted({record[5] for record in RECORDS})
    type_encoder, strand_encoder, attr_encoder = (
        LabelEncoder(), LabelEncoder(), LabelEncoder()
    )
    type_codes = type_encoder.fit_transform(types)
    strand_codes = strand_encoder.fit_transform(strands)
    attr_codes = attr_encoder.fit_transform(attributes)

    data = np.zeros((len(RECORDS), len(FIELDS)), dtype=np.float32)
    for row, (seqid, gtype, start, end, strand, attr) in enumerate(RECORDS):
        data[row, FIELDS.index("seqid")] = float(seqid)
        data[row, FIELDS.index("start")] = float(start)
        data[row, FIELDS.index("end")] = float(end)
        data[row, FIELDS.index("type")] = type_codes[types.index(gtype)]
        data[row, FIELDS.index("strand")] = strand_codes[strands.index(strand)]
        data[row, FIELDS.index("attributes")] = (
            attr_codes[attributes.index(attr)]
        )

    return Form(
        data=data,
        dims=["record", "field"],
        labels={
            "record": {},
            "field": {name: index for index, name in enumerate(FIELDS)},
        },
        info={
            "missing_code": float("nan"),
            "encoders": {
                "field": {
                    "type": type_encoder,
                    "strand": strand_encoder,
                    "attributes": attr_encoder,
                }
            },
        },
    )


def test_annotation_gaps_reads_a_numeric_seqid():
    ctx = Ctx({"output": "gaps"})
    AnnotationGapsStep().run(ctx, [_numeric_seqid_form()])

    gaps = ctx["gaps"]
    assert gaps.dims == ["gap", "statistic"]
    # G1 ends at 2000, G2 starts at 5000 -> one gap of 2999 bp.
    assert gaps.data.shape == (1, 5)
    assert float(gaps.data[0, 0]) == pytest.approx(2999.0)
    assert gaps.info["seqid"] == ["21"]


def test_gene_structure_reads_a_numeric_seqid():
    ctx = Ctx({"output": "structure"})
    GeneStructureStep().run(ctx, [_numeric_seqid_form()])

    structure = ctx["structure"]
    assert structure.dims == ["gene", "statistic"]
    assert structure.data.shape == (2, 5)
    # G1 has two exons -> one intron; G2 has a single exon.
    assert float(structure.data[0, 0]) == pytest.approx(2.0)
    assert float(structure.data[0, 1]) == pytest.approx(1.0)
    assert float(structure.data[1, 0]) == pytest.approx(1.0)
    assert float(structure.data[0, 4]) == pytest.approx(1.0)
    assert float(structure.data[1, 4]) == pytest.approx(-1.0)
