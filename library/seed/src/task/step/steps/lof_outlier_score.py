"""Local outlier factor (lof_outlier_score, b93)."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.step.base import Step
from ._b93_common import column, matrix, row_names, table


class LofOutlierScoreStep(Step):
    parameters_file = "lof_outlier_score.LofOutlierScoreStep.parameters.json"
    definition = {'id': 'lof_outlier_score', 'version': '1.0.0', 'title': 'Local outlier factor', 'description': 'Computes k-distance, local reachability density and the local outlier factor for every row.', 'category': 'Machine Learning', 'icon': 'scatter', 'protocol_version': 3, 'protocol_revision': '3.7', 'kind': 'operator', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': []}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}}

    def run(self, ctx, inputs):
        k = int(ctx.step_params.get("k", 5))
        threshold = float(ctx.step_params.get("threshold", 0.6))
        x = matrix(inputs[0])
        n = x.shape[0]
        if n <= k:
            raise ValueError("need more rows than k")
        d = np.sqrt(((x[:, None, :] - x[None, :, :]) ** 2).sum(axis=2))
        np.fill_diagonal(d, np.inf)
        knn = np.argsort(d, axis=1)[:, :k]
        kdist = np.take_along_axis(d, knn, axis=1).max(axis=1)
        reach = np.maximum(d, kdist[None, :])
        lrd = np.zeros(n)
        for i in range(n):
            lrd[i] = 1.0 / max(reach[i, knn[i]].mean(), 1e-12)
        lof = np.zeros(n)
        for i in range(n):
            lof[i] = lrd[knn[i]].mean() / max(lrd[i], 1e-12)
        flag = (lof >= threshold).astype(float)
        names = row_names(inputs[0])
        out = table("row", names, {"lof": np.round(lof, 9), "k_distance": np.round(kdist, 9), "is_outlier": flag},
                    columns=["lof", "k_distance", "is_outlier"])
        ctx[ctx.step_params.get("output", "lof_outlier_score_out")] = out



def _expected_path(n):
    if n <= 1:
        return 0.0
    return 2.0 * (np.log(n - 1) + 0.5772156649015329) - 2.0 * (n - 1) / n
