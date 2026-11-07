"""Tests for the b59 metagenomics panel."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form
from src.core.encoding import LabelEncoder
from src.task.context import Context
from src.reader.readers._table_common import table_form
from src.task.step.steps.ani_from_kmers import AniFromKmersStep
from src.task.step.steps.checkm_quality_parse import CheckmQualityParseStep
from src.task.step.steps.gtdb_taxonomy_parse import GtdbTaxonomyParseStep
from src.task.step.steps.mlst_typing import MlstTypingStep
from src.task.step.steps.pangenome_matrix import PangenomeMatrixStep

class Ctx(Context):
    def __init__(self, params):
        self.step_params = dict(params)
        self._values = {}

    def __setitem__(self, key, value):
        self._values[key] = value

    def __getitem__(self, key):
        return self._values[key]


def run(step, form, **params):
    ctx = Ctx({"output": "out", **params})
    ctx.step_params = {"output": "out", **params}
    step.run(ctx, [form])
    return ctx["out"]


def numeric_form(rows, names, dim="row"):
    df = __import__("pandas").DataFrame(rows, columns=names)
    return table_form(df, [dim, "field"], {"field": "builtin"}, "csv", encoders_cfg={},
                      row_labels=[f"r{i}" for i in range(len(rows))])


def test_ani_mash_formula():
    form = numeric_form([[1, 1], [1, 1], [1, 1], [1, 0]], ["count_a", "count_b"], "kmer")
    out = run(AniFromKmersStep(), form)
    assert out.data[0, 0] == 3 and out.data[0, 1] == 4
    assert out.data[0, 2] == pytest.approx(0.75)
    assert out.data[0, 4] == pytest.approx(1 - (-(1 / 21) * np.log(2 * 0.75 / 1.75)))


def test_checkm_quality():
    form = numeric_form([[99.0, 1.0], [80.0, 6.0]], ["completeness", "contamination"], "genome")
    out = run(CheckmQualityParseStep(), form)
    np.testing.assert_allclose(out.data[:, 2], [94.0, 50.0])


def test_gtdb_ranks():
    taxa = ["d__Bacteria;p__A;c__B;o__C;f__D;g__E;s__F",
            "d__Bacteria;p__A;c__B;o__C;f__D;g__;s__"]
    enc = LabelEncoder()
    codes = enc.fit_transform(taxa)
    df = __import__("pandas").DataFrame({"taxonomy": codes})
    form = table_form(df, ["genome", "field"], {"field": "builtin"}, "csv",
                      encoders_cfg={}, row_labels=["g1", "g2"])
    form.info.setdefault("encoders", {})["field"] = {"taxonomy": enc}
    out = run(GtdbTaxonomyParseStep(), form)
    assert out.data[0, 0] == 2 and out.data[5, 0] == 1


def test_mlst_types():
    rows = [[1, 2, 3], [1, 2, 3], [9, 9, 9]]
    form = numeric_form(rows, ["locus1", "locus2", "locus3"], "isolate")
    out = run(MlstTypingStep(), form, loci=3)
    np.testing.assert_allclose(out.data[:, 0], [1, 1, 2])


def test_pangenome_counts():
    rows = [[0, 1, 0], [0, 1, 1], [1, 1, 0], [2, 1, 0], [3, 1, 0]]
    form = numeric_form(rows, ["gene_index", "present", "genome_index"], "gene")
    out = run(PangenomeMatrixStep(), form, genomes=2)
    # gene0 present in 1 genome, gene1 in 2, gene2 in 1, gene3 in 1.
    np.testing.assert_allclose(out.data[0, :4], [1, 3, 3, 4])
