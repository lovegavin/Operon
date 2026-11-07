import numpy as np

from src.core import Form
from src.task.step.base import Step
from ._splice_common import numeric_column, names_for, result_form


class ExonSkippingStep(Step):
    """Per-exon inclusion ratio and deviation from the gene mean."""

    definition = {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "exon_skipping",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Exon skipping",
        "category": "Transcriptomics",
        "description": 'Per-exon inclusion ratio and deviation from the gene mean.',
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
        "contracts": {
            "version": 1,
            "inputs": [
                {"name": "table", "version": 1, "numeric": True,
                 "dims": [{"param": "row_dim", "default": "exon"}, {"param": "field_dim", "default": "field"}],
                 "labels": [], "parallel": [], "ndim": 2},
            ],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True,
                       "info_open": True, "axis_info_open": True}},
        },
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"]}],
            "outputs": [{"logical_type": "form", "representations": ["form"]}],
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"},
    }

    parameters_file = "exon_skipping.ExonSkippingStep.parameters.json"

    def run(self, ctx, inputs):
        params = ctx.step_params
        form = inputs[0]
        inc = numeric_column(form, "exon", "inclusion")
        exc = numeric_column(form, "exon", "exclusion")
        gene = np.asarray([int(v) for v in numeric_column(form, "exon", "gene_index")])
        total = inc + exc
        psi = np.divide(inc, total, out=np.zeros_like(inc), where=total > 0)
        out = np.zeros((len(psi), 4))
        for g in np.unique(gene):
            sel = gene == g
            out[sel, 0] = psi[sel]
            out[sel, 1] = float(np.mean(psi[sel]))
            out[sel, 2] = psi[sel] - out[sel, 1]
            out[sel, 3] = int(sel.sum())
        out = result_form("exon", names_for(form, "exon"),
                          ["psi", "gene_mean_psi", "delta", "n_genes"], out)
        ctx[params["output"]] = out
        return None


def export(ctx):
    return ctx._export_data()
