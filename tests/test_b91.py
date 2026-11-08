import os
from pathlib import Path

import numpy as np
import pytest

from src.core import Form

pytest.importorskip("torch")
pytest.importorskip("transformers")

WEIGHTS = Path(os.path.expanduser("~/.cache/operon-weights/NTv2-50M"))
if not (WEIGHTS / "config.json").is_file():
    pytest.skip("Nucleotide Transformer weights are not available", allow_module_level=True)

from src.task.step.steps.nucleotide_transformer_embedding import NucleotideTransformerEmbeddingStep
from src.task.step.steps.nucleotide_transformer_variant_effect import NucleotideTransformerVariantEffectStep
from src.task.step.steps.sequence_g4_quadruplex_scan import SequenceG4QuadruplexScanStep


class Ctx(dict):
    @property
    def step_params(self):
        return self


def seq_form(rows, columns=("seq",), encoders=None):
    data = np.asarray(rows, dtype=float)
    return Form(data=data, dims=["row", "field"],
                labels={"row": {str(i): i for i in range(len(rows))},
                        "field": {c: i for i, c in enumerate(columns)}},
                info={"encoders": {"field": encoders or {}}})


def test_embedding_shape_and_variation():
    form = seq_form([[0], [1]], encoders={"seq": {0: "ACGTACGTACGT", 1: "TTTTGGGGCCCC"}})
    ctx = Ctx(output="emb", sequence_column="seq", max_length=64, batch_size=2, model_path="")
    NucleotideTransformerEmbeddingStep().run(ctx, [form])
    out = ctx["emb"]
    assert out.data.shape == (2, 512)
    assert np.isfinite(out.data).all()
    assert abs(float(out.data[0].sum()) - float(out.data[1].sum())) > 1e-3


def test_variant_effect_identical_and_different():
    enc = {"ref": {0: "ACGTACGTACGT"}, "alt": {0: "ACGTACGTACGT", 1: "ACGTACGTACGA"}}
    form = seq_form([[0, 0], [0, 1]], columns=("ref", "alt"), encoders=enc)
    ctx = Ctx(output="eff", ref_column="ref", alt_column="alt", max_length=64, model_path="")
    NucleotideTransformerVariantEffectStep().run(ctx, [form])
    out = ctx["eff"]
    assert out.data.shape == (2, 5)
    assert abs(float(out.data[0, 2]) - 1.0) < 1e-6
    assert abs(float(out.data[0, 3])) < 1e-9
    assert float(out.data[1, 2]) < 1.0


def test_g4_quadruplex_counts():
    form = seq_form([[0], [1], [2]], encoders={"seq": {0: "GGGAGGGAGGGAGGG", 1: "GGGAAAAAAGGG", 2: "ACGT"}})
    ctx = Ctx(output="g4", sequence_column="seq", min_tracts=4, min_g=3, max_loop=7)
    SequenceG4QuadruplexScanStep().run(ctx, [form])
    out = ctx["g4"]
    assert out.data.tolist() == [[1.0, 15.0, 3.0], [0.0, 0.0, 3.0], [0.0, 0.0, 0.0]]
