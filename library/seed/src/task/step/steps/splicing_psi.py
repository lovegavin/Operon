import numpy as np
import scipy.stats as st

from src.core import Form
from src.task.step.base import Step
from ._splice_common import numeric_column, names_for, result_form


class SplicingPsiStep(Step):
    """PSI = inclusion / (inclusion + skipping) per event with a Jeffreys interval."""

    definition = {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "splicing_psi",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Splicing PSI",
        "category": "Transcriptomics",
        "description": 'PSI = inclusion / (inclusion + skipping) per event with a Jeffreys interval.',
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
        "contracts": {
            "version": 1,
            "inputs": [
                {"name": "table", "version": 1, "numeric": True,
                 "dims": [{"param": "row_dim", "default": "event"}, {"param": "field_dim", "default": "field"}],
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

    parameters_file = "splicing_psi.SplicingPsiStep.parameters.json"

    def run(self, ctx, inputs):
        params = ctx.step_params
        form = inputs[0]
        inc = numeric_column(form, "event", "inclusion")
        skip = numeric_column(form, "event", "skipping")
        total = inc + skip
        psi = np.divide(inc, total, out=np.zeros_like(inc), where=total > 0)
        lo = st.beta.ppf(0.025, inc + 0.5, skip + 0.5)
        hi = st.beta.ppf(0.975, inc + 0.5, skip + 0.5)
        out = result_form("event", names_for(form, "event"),
                          ["psi", "ci_low", "ci_high", "total_reads"],
                          np.round(np.column_stack([psi, lo, hi, total]), 9))
        ctx[params["output"]] = out
        return None


def export(ctx):
    return ctx._export_data()
