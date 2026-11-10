"""Operator hdbscan_cluster."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.core.errors import StepError
from src.task.step.base import Step

from src.task.step.steps._b90_common import column, matrix, table


class HdbscanClusterStep(Step):
    parameters_file = "hdbscan_cluster.HdbscanClusterStep.parameters.json"

    definition = {'id': 'hdbscan_cluster', 'version': '1.0.0', 'title': 'HDBSCAN density clustering', 'description': 'Cluster a numeric table with HDBSCAN and return per-point cluster, probability and outlier score.', 'category': 'Machine Learning', 'kind': 'operator', 'protocol_version': 3, 'protocol_revision': '3.7', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': []}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}}

    def run(self, ctx, inputs):
        """Execute the operator."""
        import hdbscan

        params = dict(ctx.step_params)
        data = matrix(inputs[0])
        algo = hdbscan.HDBSCAN(
            min_cluster_size=int(params.get("min_cluster_size", 2)),
            min_samples=int(params.get("min_samples", 1)),
            metric=str(params.get("metric", "euclidean")),
            allow_single_cluster=bool(params.get("allow_single_cluster", True)),
        )
        labels = algo.fit_predict(data)
        prob = getattr(algo, "probabilities_", np.zeros(len(data)))
        out = np.column_stack([labels.astype(float), prob.astype(float), algo.outlier_scores_.astype(float)])
        ctx[params["output"]] = Form(
            data=out,
            dims=["row", "statistic"],
            labels={"row": {str(i): i for i in range(len(data))},
                    "statistic": {"cluster": 0, "probability": 1, "outlier_score": 2}},
            info={"n_clusters": int(len(set(labels)) - (1 if -1 in labels else 0)),
                  "n_noise": int(np.sum(labels == -1))},
        )
