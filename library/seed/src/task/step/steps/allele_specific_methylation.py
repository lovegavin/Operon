"""Allele-specific methylation"""
from __future__ import annotations

import numpy as np

from src.core.forms.form import Form
from src.task.step.base import Step
from src.task.step.steps._b79_common import numeric, table


def definition(category, arity, outputs_dims):
    return {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "allele_specific_methylation",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Allele-specific methylation",
        "description": "Test allele-specific methylation from methylated and unmethylated read counts per allele using Fisher's exact test with BH correction.",
        "category": category,
        "icon": "Methylation",
        "inputs_arity": arity,
        "output_parameter": "output",
        "outputs": [],
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1, "numeric": True, "ndim": 2,
                    "dims": [{"param": "row_dim", "default": "row"},
                             {"param": "field_dim", "default": "field"}],
                    "labels": [], "parallel": [],
                }
                for _ in range(arity)
            ],
            "output": {
                "mode": "declare",
                "schema": {"ndim": outputs_dims, "numeric": True,
                           "info_open": True, "axis_info_open": True},
            },
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False,
                      "estimate": "estimate_memory"},
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}
                       for _ in range(arity)],
            "outputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
        },
    }


class AlleleSpecificMethylationStep(Step):
    parameters_file = "allele_specific_methylation.AlleleSpecificMethylationStep.parameters.json"

    definition = {'protocol_version': 3, 'protocol_revision': '3.7', 'id': 'allele_specific_methylation', 'version': '1.0.0', 'kind': 'operator', 'title': 'Allele-specific methylation', 'description': "Test allele-specific methylation from methylated and unmethylated read counts per allele using Fisher's exact test with BH correction.", 'category': 'Epigenomics', 'icon': 'Methylation', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': []}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}}


    def run(self, ctx, inputs):
        from scipy import stats

        params = ctx.step_params
        out_name = str(params.get("output", "asm"))
        form = inputs[0]
        am = numeric(form, "a_methylated")
        au = numeric(form, "a_unmethylated")
        bm = numeric(form, "b_methylated")
        bu = numeric(form, "b_unmethylated")
        n = len(am)
        pvals = []
        diffs = []
        tested = 0
        for i in range(n):
            a_total = am[i] + au[i]
            b_total = bm[i] + bu[i]
            if a_total <= 0 or b_total <= 0:
                pvals.append(1.0)
                diffs.append(0.0)
                continue
            tested += 1
            contingency = [[am[i], au[i]], [bm[i], bu[i]]]
            pvals.append(float(stats.fisher_exact(contingency)[1]))
            diffs.append(abs(am[i] / a_total - bm[i] / b_total))
        pvals = np.asarray(pvals, dtype=float)
        order = np.argsort(pvals)
        qvals = np.ones(n, dtype=float)
        running = 1.0
        for rank in range(n - 1, -1, -1):
            idx = int(order[rank])
            running = min(running, pvals[idx] * n / (rank + 1))
            qvals[idx] = running
        n_sig = int(np.sum(qvals < 0.05))
        values = [n, tested, n_sig, float(np.mean(diffs)) if n else 0.0,
                  float(np.min(pvals)) if n else 1.0]
        columns = ["n_sites", "n_tested", "n_significant", "mean_abs_diff", "min_p"]
        ctx[out_name] = table(["allele_specific_methylation"], [values], columns)


    def run(self, ctx, inputs):
        from scipy import stats

        params = ctx.step_params
        out_name = str(params.get("output", "asm"))
        form = inputs[0]
        am = numeric(form, "a_methylated")
        au = numeric(form, "a_unmethylated")
        bm = numeric(form, "b_methylated")
        bu = numeric(form, "b_unmethylated")
        n = len(am)
        pvals = []
        diffs = []
        tested = 0
        for i in range(n):
            a_total = am[i] + au[i]
            b_total = bm[i] + bu[i]
            if a_total <= 0 or b_total <= 0:
                pvals.append(1.0)
                diffs.append(0.0)
                continue
            tested += 1
            contingency = [[am[i], au[i]], [bm[i], bu[i]]]
            pvals.append(float(stats.fisher_exact(contingency)[1]))
            diffs.append(abs(am[i] / a_total - bm[i] / b_total))
        pvals = np.asarray(pvals, dtype=float)
        order = np.argsort(pvals)
        qvals = np.ones(n, dtype=float)
        running = 1.0
        for rank in range(n - 1, -1, -1):
            idx = int(order[rank])
            running = min(running, pvals[idx] * n / (rank + 1))
            qvals[idx] = running
        n_sig = int(np.sum(qvals < 0.05))
        values = [n, tested, n_sig, float(np.mean(diffs)) if n else 0.0,
                  float(np.min(pvals)) if n else 1.0]
        columns = ["n_sites", "n_tested", "n_significant", "mean_abs_diff", "min_p"]
        ctx[out_name] = table(["allele_specific_methylation"], [values], columns)
