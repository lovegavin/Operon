"""single-cell kbet batch mixing"""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form, StepError
from src.task.step.base import Step
from ._sc_common import matrix, row_names


def _batch_column(form):
    dim = [d for d in form.dims if d != form.dims[0]][0]
    labels = form.labels.get(dim, {})
    idx = labels.get("batch")
    if idx is None:
        raise ValueError("batch column 'batch' is required")
    return np.asarray(form.data[:, int(idx)], dtype=float)


class ScBatchKbetStep(Step):
    definition = {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "sc_batch_kbet",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Single-cell kBET batch mixing",
        "category": "Single cell",
        "description": "Neighbourhood chi-square test of batch mixing on a cell graph.",
        "inputs_arity": 2,
        "outputs": [],
        "output_parameter": "output",
        "data_formats": {
            "inputs": [
                {"logical_type": "form", "representations": ["form"]},
                {"logical_type": "form", "representations": ["form"]},
            ],
            "outputs": [{"logical_type": "form", "representations": ["form"]}],
        },
        "contracts": {
            "version": 1,
            "inputs": [
                {"dims": [{"param": "cell_dim", "default": "cell"}, {"param": "cell2_dim", "default": "cell2"}]},
                {"dims": [{"param": "cell_dim", "default": "cell"}, {"param": "batch_dim", "default": "batch"}]},
            ],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True}},
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"},
    }
    parameters_file = "sc_batch_kbet.ScBatchKbetStep.parameters.json"

    def run(self, ctx, inputs):
        params = ctx.step_params
        graph = np.asarray(matrix(inputs[0]), dtype=float)
        batch = _batch_column(inputs[1]).astype(int)
        n = graph.shape[0]
        if graph.ndim != 2 or graph.shape[0] != graph.shape[1] or batch.size != n:
            raise StepError("sc_batch_kbet: graph rows and batch rows differ")
        batches = sorted(set(int(b) for b in batch))
        global_p = np.array([(batch == b).mean() for b in batches])
        names = row_names(inputs[0], inputs[0].dims[0])

        alpha = float(params.get("alpha", 0.05))
        rows = []
        for i in range(n):
            w = graph[i]
            total = float(w.sum())
            if total <= 0:
                rows.append([np.nan, np.nan, 0.0, 0.0])
                continue
            obs = np.array([w[batch == b].sum() for b in batches])
            exp = total * global_p
            mask = exp > 0
            chi2 = float(np.sum((obs[mask] - exp[mask]) ** 2 / exp[mask]))
            p = float(stats.chi2.sf(chi2, max(1, len(batches) - 1)))
            rows.append([chi2, p, float(p < alpha), total])
        columns = ["chi2", "p_value", "reject", "neighbor_weight"]

        out = Form(
            data=np.asarray(rows, dtype=float),
            dims=["cell", "statistic"],
            labels={"cell": {n_: i for i, n_ in enumerate(names)},
                    "statistic": {s: i for i, s in enumerate(columns)}},
            info={"missing_code": np.nan},
        )
        out.validate()
        ctx[params["output"]] = out
        return None
