import numpy as np

from src.core import Form
from src.task.step.base import Step
from ._splice_common import numeric_column, names_for, result_form


class IsoformQuantificationEmStep(Step):
    """EM over an isoform/exon compatibility matrix and exon read counts."""

    definition = {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "isoform_quantification_em",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Isoform quantification (EM)",
        "category": "Transcriptomics",
        "description": 'EM over an isoform/exon compatibility matrix and exon read counts.',
        "inputs_arity": 2,
        "outputs": [],
        "output_parameter": "output",
        "contracts": {
            "version": 1,
            "inputs": [
                {"name": "compatibility", "version": 1, "numeric": True,
                 "dims": [{"param": "isoform_dim", "default": "isoform"}, {"param": "exon_dim", "default": "exon"}],
                 "labels": [], "parallel": [], "ndim": 2},
                {"name": "counts", "version": 1, "numeric": True,
                 "dims": [{"param": "exon_dim", "default": "exon"}, {"param": "sample_dim", "default": "sample"}],
                 "labels": [], "parallel": [], "ndim": 2},
            ],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True,
                       "info_open": True, "axis_info_open": True}},
        },
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"]}, {"logical_type": "form", "representations": ["form"]}],
            "outputs": [{"logical_type": "form", "representations": ["form"]}],
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"},
    }

    parameters_file = "isoform_quantification_em.IsoformQuantificationEmStep.parameters.json"

    def run(self, ctx, inputs):
        params = ctx.step_params
        form = inputs[0]
        compat = np.asarray(inputs[0].data, dtype=float)
        counts = np.asarray(inputs[1].data, dtype=float)[:, 0]
        n_iso = compat.shape[0]
        theta = np.full(n_iso, 1.0 / n_iso)
        it = 0
        for it in range(1, int(params.get("max_iter", 200)) + 1):
            eff = compat * theta[:, None]
            denom = eff.sum(axis=0)
            denom[denom <= 0] = 1.0
            alloc = eff * (counts / denom)[None, :]
            new = alloc.sum(axis=1)
            s = new.sum()
            new = new / s if s > 0 else np.full(n_iso, 1.0 / n_iso)
            if np.max(np.abs(new - theta)) < float(params.get("tol", 1e-8)):
                theta = new
                break
            theta = new
        ll = float(np.sum(counts * np.log(np.maximum(compat.T @ theta, 1e-12))))
        out = result_form("isoform", names_for(inputs[0], "isoform"),
                          ["expression", "fraction", "log_likelihood", "iterations"],
                          np.column_stack([theta * counts.sum(), theta,
                                           np.full(n_iso, ll), np.full(n_iso, it)]),
                          info={"iterations": int(it)})
        ctx[params["output"]] = out
        return None


def export(ctx):
    return ctx._export_data()
