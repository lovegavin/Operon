"""Pseudo-bulk differential expression."""
from __future__ import annotations

import numpy as np
from scipy import stats
from statsmodels.stats.multitest import multipletests

from src.task.step.base import Step
from ._sc_common import matrix, row_names, result_form


class ScPseudobulkDeStep(Step):
    definition = {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "sc_pseudobulk_de",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Pseudo-bulk differential expression",
        "category": "Single cell",
        "description": "Aggregate cells by group and test gene-wise mean differences.",
        "inputs_arity": 2,
        "outputs": [],
        "output_parameter": "output",
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"]},
                       {"logical_type": "form", "representations": ["form"]}],
            "outputs": [{"logical_type": "form", "representations": ["form"]}],
        },
        "contracts": {
            "version": 1,
            "inputs": [{"dims": [{"param": "gene_dim", "default": "gene"}, {"param": "cell_dim", "default": "cell"}]},
                       {"dims": [{"param": "cell_dim", "default": "cell"}, {"param": "field_dim", "default": "field"}]}],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True}},
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"},
    }
    parameters_file = "sc_pseudobulk_de.ScPseudobulkDeStep.parameters.json"

    def run(self, ctx, inputs):
        params = ctx.step_params
        counts = matrix(inputs[0])
        grp_form = inputs[1]
        labels = grp_form.labels.get("field", {})
        col = labels.get(params.get("group_column", "group"), None)
        if col is None:
            col = 0
        raw = np.asarray(grp_form.data)[:, int(col)]
        enc = grp_form.info.get("encoders", {}).get("field", {})
        if isinstance(enc, dict):
            inv = enc.get(params.get("group_column", "group"), enc)
            if isinstance(inv, dict):
                raw = [inv.get(int(v), v) if float(v).is_integer() else v for v in raw]
            elif hasattr(inv, "inverse_transform"):
                raw = inv.inverse_transform(np.asarray(raw).astype(int))
            elif hasattr(inv, "inverse"):
                raw = inv.inverse(np.asarray(raw).astype(int))
        groups = np.asarray([str(v) for v in raw])
        uniq = sorted(set(groups))
        if len(uniq) != 2:
            raise ValueError("sc_pseudobulk_de requires exactly two groups")
        a, b = uniq
        xa, xb = counts[:, groups == a], counts[:, groups == b]
        ma, mb = xa.mean(axis=1), xb.mean(axis=1)
        t, p = stats.ttest_ind(xa, xb, axis=1, equal_var=False)
        lfc = np.log2((mb + 1.0) / (ma + 1.0))
        q = multipletests(np.nan_to_num(p, nan=1.0), method="fdr_bh")[1]
        data = np.column_stack([ma, mb, lfc, t, p, q])
        ctx[params["output"]] = result_form("gene", row_names(inputs[0], "gene"),
                                            ["mean_a", "mean_b", "log2fc", "t", "p", "q"], data,
                                            info={"group_a": a, "group_b": b})
        return None


def export(ctx):
    return ctx._export_data()
