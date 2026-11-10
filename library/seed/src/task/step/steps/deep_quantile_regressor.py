from src.core import Form, StepError
from src.task.step.base import Step
from src.task.step.steps._b89_common import matrix, named_column, table

class DeepQuantileRegressorStep(Step):
    parameters_file = "deep_quantile_regressor.DeepQuantileRegressorStep.parameters.json"

    definition = {'id': 'deep_quantile_regressor', 'version': '1.0.0', 'title': 'Linear quantile regressor', 'description': 'Linear pinball-loss quantile regression solved as a linear program, reporting the fitted slope and intercept.', 'category': 'Machine Learning', 'kind': 'operator', 'protocol_version': 3, 'protocol_revision': '3.7', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': []}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'dependencies': ['numpy>=1.24', 'scipy>=1.11'], 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}}

    def run(self, ctx, inputs):
        import numpy as np
        from scipy.optimize import linprog

        params = ctx.step_params
        x = np.asarray(named_column(inputs[0], params["feature_column"]), dtype=float)
        y = np.asarray(named_column(inputs[0], params["target_column"]), dtype=float)
        n = x.size
        q = float(params["quantile"])
        # Median-regression LP: HiGHS is deterministic across platforms.
        c = np.concatenate([np.zeros(2), np.ones(2 * n)])
        A = np.zeros((n, 2 + 2 * n))
        A[:, 0] = x
        A[:, 1] = 1.0
        for i in range(n):
            A[i, 2 + i] = 1.0
            A[i, 2 + n + i] = -1.0
        bounds = [(None, None), (None, None)] + [(0.0, None)] * (2 * n)
        res = linprog(c, A_eq=A, b_eq=y, bounds=bounds, method="highs")
        if not res.success:
            raise StepError("quantile regression did not converge")
        slope = float(res.x[0])
        intercept = float(res.x[1])
        diff = y - (slope * x + intercept)
        pinball = float(np.mean(np.maximum(q * diff, (q - 1.0) * diff)))
        out_data = np.array([[slope, intercept, q, pinball, float(n)]], dtype=float)
        out = table(
            {"slope": out_data[:, 0], "intercept": out_data[:, 1], "quantile": out_data[:, 2],
             "pinball_loss": out_data[:, 3], "n_train": out_data[:, 4]},
            ["slope", "intercept", "quantile", "pinball_loss", "n_train"],
        )
        ctx[params["output"]] = out
