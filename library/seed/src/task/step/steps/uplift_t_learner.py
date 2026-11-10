"""Auto-generated b83 operator."""
import numpy as np

from src.core import Form
from src.task.step.base import Step

from ._b83_common import column, feature_matrix, named_column, strings, table


class UpliftTLearnerStep(Step):
    parameters_file = "uplift_t_learner.UpliftTLearnerStep.parameters.json"

    definition = {'id': 'uplift_t_learner', 'version': '1.0.0', 'title': 'Uplift T-learner', 'description': 'Fit separate least-squares outcome models per treatment arm and report per-sample uplift.', 'category': 'Causal inference', 'kind': 'operator', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'protocol_version': 3, 'protocol_revision': '3.7', 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}, 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': []}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}}

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return (32 * 1024 * 1024, 0)

    def run(self, ctx, inputs):
        params = ctx.step_params
        form = inputs[0]
        treat = named_column(form, "treatment")
        y = named_column(form, "outcome")
        X = feature_matrix(form, {"id", "treatment", "outcome"})
        if X.shape[1] == 0:
            raise ValueError("uplift_t_learner needs at least one feature column after treatment and outcome")
        arms = []
        for value in (0.0, 1.0):
            mask = treat == value
            if int(mask.sum()) < 2:
                raise ValueError("each treatment arm needs at least two rows")
            A = np.column_stack([np.ones(int(mask.sum())), X[mask]])
            coef, *_ = np.linalg.lstsq(A, y[mask], rcond=None)
            arms.append(np.column_stack([np.ones(len(y)), X]) @ coef)
        mu0, mu1 = arms
        names = [str(i) for i in range(len(y))]
        labels = form.labels.get(form.dims[0]) or {}
        if labels:
            inv = {v: k for k, v in labels.items()}
            names = [str(inv.get(i, i)) for i in range(len(y))]
        rows = np.column_stack([mu0, mu1, mu1 - mu0])
        ctx[str(params.get("output", "output"))] = table(names, rows, ["mu0", "mu1", "uplift"])

