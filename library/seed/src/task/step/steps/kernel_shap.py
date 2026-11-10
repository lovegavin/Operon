"""Auto-generated b88 operator: KernelSHAP linear attribution."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.step.base import Step
from ._b88_common import matrix, labels, table


class KernelShapStep(Step):
    parameters_file = "kernel_shap.KernelShapStep.parameters.json"
    definition = {'id': 'kernel_shap', 'kind': 'operator', 'version': '1.0.0', 'title': 'KernelSHAP linear attribution', 'description': 'Exact Shapley attribution for a ridge model (closed form for linear models). (batch b88).', 'category': 'Machine Learning', 'icon': 'operator', 'protocol_version': 3, 'protocol_revision': '3.7', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': []}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}, 'dependencies': ['numpy>=1.24']}

    def run(self, ctx, inputs):
        params = ctx.step_params
        out_name = params["output"]
        x = matrix(inputs[0])
        lab = labels(inputs[0], inputs[0].dims[1])
        tc = params.get("target_column", "target")
        if tc not in lab:
            raise ValueError(f"missing target column {tc}")
        ridx = int(params.get("row", 0))
        y = x[:, lab[tc]]
        feat = [lab[k] for k, _ in sorted(lab.items(), key=lambda kv: kv[1]) if k != tc]
        names = [k for k, _ in sorted(lab.items(), key=lambda kv: kv[1]) if k != tc]
        X = x[:, feat]
        alpha = float(params.get("alpha", 1.0))
        X1 = np.hstack([np.ones((X.shape[0], 1)), X])
        pen = alpha * np.eye(X1.shape[1]); pen[0, 0] = 0.0
        w = np.linalg.solve(X1.T @ X1 + pen, X1.T @ y)
        base = float(w[0] + X.mean(axis=0) @ w[1:])
        pred = float(w[0] + X[ridx] @ w[1:])
        phi = w[1:] * (X[ridx] - X.mean(axis=0))
        vals = {"value": X[ridx], "phi": phi, "abs_phi": np.abs(phi)}
        out = table(names, vals)
        out.info["baseline"] = base
        out.info["prediction"] = pred
        ctx[out_name] = out

