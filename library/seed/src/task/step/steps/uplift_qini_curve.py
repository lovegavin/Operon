"""Auto-generated b83 operator."""
import numpy as np

from src.core import Form
from src.task.step.base import Step

from ._b83_common import column, feature_matrix, named_column, strings, table


class UpliftQiniCurveStep(Step):
    parameters_file = "uplift_qini_curve.UpliftQiniCurveStep.parameters.json"

    definition = {'id': 'uplift_qini_curve', 'version': '1.0.0', 'title': 'Uplift Qini curve', 'description': 'Sort samples by estimated uplift and report the cumulative Qini gain curve.', 'category': 'Causal inference', 'kind': 'operator', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'protocol_version': 3, 'protocol_revision': '3.7', 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}, 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': []}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}}

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return (32 * 1024 * 1024, 0)

    def run(self, ctx, inputs):
        params = ctx.step_params
        form = inputs[0]
        treat = named_column(form, "treatment")
        y = named_column(form, "outcome")
        X = feature_matrix(form, {"id", "treatment", "outcome"})
        n_bins = int(params.get("n_bins", 10))
        arms = []
        for value in (0.0, 1.0):
            mask = treat == value
            A = np.column_stack([np.ones(int(mask.sum())), X[mask]])
            coef, *_ = np.linalg.lstsq(A, y[mask], rcond=None)
            arms.append(np.column_stack([np.ones(len(y)), X]) @ coef)
        uplift = arms[1] - arms[0]
        order = np.argsort(-uplift)
        n = len(order)
        gains, sizes = [], []
        for k in range(1, n + 1):
            idx = order[:k]
            t = treat[idx]; yy = y[idx]
            nt = float((t == 1).sum()); nc = float((t == 0).sum())
            if nt == 0 or nc == 0:
                gains.append(0.0)
            else:
                gains.append(float(yy[t == 1].sum()) / nt - float(yy[t == 0].sum()) / nc)
            sizes.append(float(k) / n)
        step = max(1, n // max(1, n_bins))
        rows, entry = [], []
        for k in range(0, n, step):
            rows.append([sizes[k], gains[k], gains[k] / (sizes[k] + 1e-12)])
            entry.append(f"q{k}")
        ctx[str(params.get("output", "output"))] = table(entry, rows, ["fraction", "uplift_sum", "qini"])

