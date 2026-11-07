"""b68 metabolite_set_enrichment."""
from __future__ import annotations

import numpy as np
from scipy import stats as st

from src.core import Form
from src.task.step.base import Step
from src.task.step.steps._b68_common import numeric_column, result_form, string_column


class MetaboliteSetEnrichmentStep(Step):
    definition = {
    "protocol_version": 3,
    "id": "metabolite_set_enrichment",
    "version": "1.0.0",
    "kind": "operator",
    "title": "Metabolite set enrichment",
    "category": "Metabolomics",
    "description": "Hypergeometric over-representation of metabolite sets among detected features.",
    "icon": "Table",
    "inputs_arity": 2,
    "output_parameter": "output",
    "outputs": [],
    "data_formats": {
        "inputs": [
            {
                "logical_type": "form",
                "representations": [
                    "form"
                ]
            },
            {
                "logical_type": "form",
                "representations": [
                    "form"
                ]
            }
        ],
        "outputs": [
            {
                "logical_type": "form",
                "representations": [
                    "form"
                ]
            }
        ]
    },
    "contracts": {
        "version": 1,
        "inputs": [
            {
                "version": 1,
                "numeric": True,
                "ndim": 2,
                "dims": [
                    {
                        "param": "feature_dim",
                        "default": "feature"
                    },
                    {
                        "param": "field_dim",
                        "default": "field"
                    }
                ],
                "labels": [],
                "parallel": []
            },
            {
                "version": 1,
                "numeric": True,
                "ndim": 2,
                "dims": [
                    {
                        "param": "set_dim",
                        "default": "set"
                    },
                    {
                        "param": "set_field_dim",
                        "default": "field"
                    }
                ],
                "labels": [],
                "parallel": []
            }
        ],
        "output": {
            "mode": "declare",
            "schema": {
                "ndim": 2,
                "numeric": True
            }
        }
    },
    "resources": {
        "memory_modes": [
            "full"
        ],
        "supports_cuda": False,
        "estimate": "estimate_memory"
    }
}
    parameters_file = "metabolite_set_enrichment.MetaboliteSetEnrichmentStep.parameters.json"

    def run(self, ctx, inputs):
        universe_size = ctx.step_params.get('universe_size', 20000)
        feature_dim = ctx.step_params.get('feature_dim', 'feature')
        field_dim = ctx.step_params.get('field_dim', 'field')
        set_dim = ctx.step_params.get('set_dim', 'set')
        set_field_dim = ctx.step_params.get('set_field_dim', 'field')
        set_size = ctx.step_params.get('set_size', 'set_size')
        overlap = ctx.step_params.get('overlap', 'overlap')
        expected = ctx.step_params.get('expected', 'expected')
        fold_enrichment = ctx.step_params.get('fold_enrichment', 'fold_enrichment')
        p_value = ctx.step_params.get('p_value', 'p_value')
        q_value = ctx.step_params.get('q_value', 'q_value')
        from scipy import stats as st
        hits = set(string_column(inputs[0], feature_dim, "metabolite"))
        sets_form = inputs[1]
        members = string_column(sets_form, set_dim, "member")
        set_ids = string_column(sets_form, set_dim, "set_id")
        groups = {}
        for sid, member in zip(set_ids, members):
            groups.setdefault(sid, set()).add(member)
        names = sorted(groups)
        n_detected = len(hits)
        rows, pvals = [], []
        for name in names:
            members_set = groups[name]
            k = len(members_set & hits)
            K = len(members_set)
            expected = n_detected * K / universe_size
            p = float(st.hypergeom.sf(k - 1, universe_size, K, n_detected)) if n_detected else 1.0
            pvals.append(p)
            rows.append([K, k, expected, k / expected if expected else 0.0, p, 0.0])
        order = np.argsort(pvals)
        q = np.empty(len(pvals))
        prev = 1.0
        for rank, idx in enumerate(order[::-1], start=1):
            prev = min(prev, pvals[idx] * len(pvals) / (len(pvals) - rank + 1))
            q[idx] = prev
        for row, value in zip(rows, q):
            row[5] = min(1.0, value)
        out = result_form(names, rows, columns=["set_size", "overlap", "expected", "fold_enrichment", "p_value", "q_value"])
        ctx[ctx.step_params["output"]] = out
