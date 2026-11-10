import numpy as np

from src.core import Form
from src.task.step.base import Step
from ._splice_common import numeric_column, names_for, result_form


class IntronRetentionStep(Step):
    """Length-normalised intron retention ratio per intron."""

    definition = {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "intron_retention",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Intron retention",
        "category": "Transcriptomics",
        "description": 'Length-normalised intron retention ratio per intron.',
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
        "contracts": {
            "version": 1,
            "inputs": [
                {"name": "table", "version": 1, "numeric": True,
                 "dims": [{"param": "row_dim", "default": "intron"}, {"param": "field_dim", "default": "field"}],
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

    parameters_file = "intron_retention.IntronRetentionStep.parameters.json"

    def run(self, ctx, inputs):
        params = ctx.step_params
        form = inputs[0]
        ir = numeric_column(form, "intron", "intron_reads")
        er = numeric_column(form, "intron", "exon_reads")
        il = np.maximum(numeric_column(form, "intron", "intron_length"), 1.0)
        el = np.maximum(numeric_column(form, "intron", "exon_length"), 1.0)
        iden = ir / il
        eden = er / el
        ratio = np.divide(iden, eden, out=np.zeros_like(iden), where=eden > 0)
        flagged = (ratio > 0.1).astype(float)
        out = result_form("intron", names_for(form, "intron"),
                          ["retention_ratio", "intron_density", "exon_density", "retained_flag"],
                          np.column_stack([ratio, iden, eden, flagged]))
        ctx[params["output"]] = out
        return None


def export(ctx):
    return ctx._export_data()
