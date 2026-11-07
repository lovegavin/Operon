"""single-cell ilisi batch mixing"""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form
from src.task.step.base import Step
from ._sc_common import matrix, row_names


def _batch_column(form):
    dim = [d for d in form.dims if d != form.dims[0]][0]
    labels = form.labels.get(dim, {})
    idx = labels.get("batch")
    if idx is None:
        raise ValueError("batch column 'batch' is required")
    return np.asarray(form.data[:, int(idx)], dtype=float)


class ScBatchIlisiStep(Step):
    definition = {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "sc_batch_ilisi",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Single-cell iLISI batch mixing",
        "category": "Single cell",
        "description": "Inverse Simpson index of neighbour batch labels on a cell graph.",
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
    parameters_file = "sc_batch_ilisi.ScBatchIlisiStep.parameters.json"

    def run(self, ctx, inputs):
        params = ctx.step_params
        graph = np.asarray(matrix(inputs[0]), dtype=float)
        batch = _batch_column(inputs[1]).astype(int)
        n = graph.shape[0]
        if batch.size != n:
            raise ValueError("graph rows and batch rows differ")
        batches = sorted(set(int(b) for b in batch))
        global_p = np.array([(batch == b).mean() for b in batches])
        names = row_names(inputs[0], inputs[0].dims[0])

        rows = []
        nb = len(batches)
        for i in range(n):
            w = graph[i]
            total = float(w.sum())
            if total <= 0 or nb < 2:
                rows.append([np.nan, np.nan, float(nb), 0.0])
                continue
            p = np.array([w[batch == b].sum() / total for b in batches])
            ilisi = float(1.0 / np.sum(p ** 2))
            rows.append([ilisi, float((ilisi - 1.0) / (nb - 1.0)), float(nb), total])
        columns = ["ilisi", "ilisi_normalized", "n_batches", "neighbor_weight"]

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
