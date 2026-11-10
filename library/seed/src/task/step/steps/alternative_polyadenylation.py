import numpy as np

from src.core import Form
from src.task.step.base import Step
from ._splice_common import numeric_column, names_for, result_form


class AlternativePolyadenylationStep(Step):
    """Proximal poly(A) site usage from proximal/distal read counts."""

    definition = {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "alternative_polyadenylation",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Alternative polyadenylation",
        "category": "Transcriptomics",
        "description": 'Proximal poly(A) site usage from proximal/distal read counts.',
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
        "contracts": {
            "version": 1,
            "inputs": [
                {"name": "table", "version": 1, "numeric": True,
                 "dims": [{"param": "row_dim", "default": "gene"}, {"param": "field_dim", "default": "field"}],
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

    parameters_file = "alternative_polyadenylation.AlternativePolyadenylationStep.parameters.json"

    def run(self, ctx, inputs):
        params = ctx.step_params
        form = inputs[0]
        prox = numeric_column(form, "gene", "proximal")
        dist = numeric_column(form, "gene", "distal")
        total = prox + dist
        usage = np.divide(prox, total, out=np.full_like(prox, 0.5), where=total > 0)
        log2r = np.log2(np.divide(prox + 0.5, dist + 0.5))
        flag = ((usage > 0.7) | (usage < 0.3)).astype(float)
        out = result_form("gene", names_for(form, "gene"),
                          ["proximal_usage", "log2_ratio", "total_reads", "apa_flag"],
                          np.column_stack([usage, log2r, total, flag]))
        ctx[params["output"]] = out
        return None


def export(ctx):
    return ctx._export_data()
