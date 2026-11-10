"""Isolation-forest anomaly scores (isolation_forest_anomaly, b93)."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.step.base import Step
from ._b93_common import column, matrix, row_names, table


class IsolationForestAnomalyStep(Step):
    parameters_file = "isolation_forest_anomaly.IsolationForestAnomalyStep.parameters.json"
    definition = {'id': 'isolation_forest_anomaly', 'version': '1.0.0', 'title': 'Isolation-forest anomaly scores', 'description': 'Builds a deterministic isolation forest from random splits and scores every row by expected path length.', 'category': 'Machine Learning', 'icon': 'scatter', 'protocol_version': 3, 'protocol_revision': '3.7', 'kind': 'operator', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': []}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}}

    def run(self, ctx, inputs):
        n_estimators = int(ctx.step_params.get("n_estimators", 100))
        sample_size = int(ctx.step_params.get("sample_size", 64))
        seed = int(ctx.step_params.get("seed", 7))
        threshold = float(ctx.step_params.get("threshold", 0.6))
        x = matrix(inputs[0])
        n = x.shape[0]
        if n < 4:
            raise ValueError("need at least 4 rows")
        psi = min(sample_size, n)
        rng = np.random.default_rng(seed)
        depth_limit = int(np.ceil(np.log2(max(psi, 2))))
        paths = np.zeros(n, dtype=float)
        counts = np.zeros(n, dtype=float)
        for _ in range(n_estimators):
            idx = rng.choice(n, size=psi, replace=False)
            leaves = {}
            def build(rows, depth):
                if depth >= depth_limit or len(rows) <= 1:
                    return ("leaf", depth, len(rows))
                lo = x[rows].min(axis=0)
                hi = x[rows].max(axis=0)
                span = hi - lo
                feats = np.where(span > 0)[0]
                if feats.size == 0:
                    return ("leaf", depth, len(rows))
                f = int(rng.choice(feats))
                cut = float(rng.uniform(lo[f], hi[f]))
                left = rows[x[rows, f] < cut]
                right = rows[x[rows, f] >= cut]
                if left.size == 0 or right.size == 0:
                    return ("leaf", depth, len(rows))
                return ("node", f, cut, build(left, depth + 1), build(right, depth + 1))
            tree = build(idx, 0)
            for i in range(n):
                node = tree
                depth = 0
                while node[0] == "node":
                    _, f, cut, left, right = node
                    node = left if x[i, f] < cut else right
                depth = node[1]
                paths[i] += depth + _expected_path(node[2])
                counts[i] += 1
        avg = paths / np.maximum(counts, 1)
        cpsi = _expected_path(psi)
        score = np.power(2.0, -avg / max(cpsi, 1e-12))
        flag = (score >= threshold).astype(float)
        names = row_names(inputs[0])
        out = table("row", names, {"score": np.round(score, 9), "mean_path": np.round(avg, 9), "is_anomaly": flag},
                    columns=["score", "mean_path", "is_anomaly"])
        ctx[ctx.step_params.get("output", "isolation_forest_anomaly_out")] = out



def _expected_path(n):
    if n <= 1:
        return 0.0
    return 2.0 * (np.log(n - 1) + 0.5772156649015329) - 2.0 * (n - 1) / n
