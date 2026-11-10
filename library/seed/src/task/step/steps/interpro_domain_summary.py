"""InterPro domain summary."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._annot_common import (matrix_form, numeric, row_names,
                                               strings)



class InterproDomainSummaryStep(Step):
    provider = "operon-core"
    parameters_file = "interpro_domain_summary.InterproDomainSummaryStep.parameters.json"

    definition = {
        "protocol_revision": "3.7",
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
            "outputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
        },
        "protocol_version": 3,
        "id": "interpro_domain_summary",
        "version": "1.0.0",
        "kind": "operator",
        "title": "InterPro domain summary",
        "description": "Per-protein domain count, covered bases and best e-value.",
        "category": "Genome annotation",
        "icon": "Table",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [
                        {"param": "hit_dim", "default": "hit"},
                        {"param": "field_dim", "default": "field"},
                    ],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                    "info": {"missing_code": {"type": ["number", "null"]}},
                }
            ],
            "output": {
                "mode": "declare",
                "schema": {
                    "ndim": 2,
                    "numeric": True,
                    "info_open": True,
                    "axis_info_open": True,
                    "info": {"missing_code": {"type": ["number", "null"]}},
                },
            },
        },
        "resources": {
            "memory_modes": ["full"],
            "supports_cuda": False,
            "estimate": "estimate_memory",
        },
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        total = sum(int(np.asarray(getattr(i, "data", [])).nbytes) for i in inputs)
        return (max(total, 8 * 1024 * 1024), 1024 * 1024)

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        out_name = params.get("output", self.name)
        row_dim = str(params.get("hit_dim", "hit"))
        field_dim = str(params.get("field_dim", "field"))
        form = inputs[0]
        names = row_names(form, row_dim)

        proteins = strings(form, field_dim, "protein", "interpro_domain_summary")
        starts = numeric(form, field_dim, "start", "interpro_domain_summary")
        ends = numeric(form, field_dim, "end", "interpro_domain_summary")
        evalues = numeric(form, field_dim, "evalue", "interpro_domain_summary")
        grouped = {}
        for i, name in enumerate(proteins):
            grouped.setdefault(name, []).append(i)
        names = sorted(grouped)
        rows = []
        for name in names:
            idx = grouped.get(name, [])
            if not idx:
                rows.append((0.0, 0.0, 0.0, 0.0))
                continue
            order = sorted(idx, key=lambda k: (starts[k], ends[k]))
            covered = 0.0
            cur_s = starts[order[0]]
            cur_e = ends[order[0]]
            for k in order[1:]:
                if starts[k] <= cur_e:
                    cur_e = max(cur_e, ends[k])
                else:
                    covered += max(cur_e - cur_s, 0.0)
                    cur_s, cur_e = starts[k], ends[k]
            covered += max(cur_e - cur_s, 0.0)
            rows.append((float(len(idx)), covered,
                         float(np.mean(ends[idx] - starts[idx])),
                         float(-np.log10(max(float(np.min(evalues[idx])), 1e-300)))))
        values = np.asarray(rows, dtype=float)
        columns = {
            "n_domains": values[:, 0],
            "covered_bp": values[:, 1],
            "mean_domain_length": values[:, 2],
            "best_evalue_log10": values[:, 3],
        }
        ctx[out_name] = matrix_form(row_dim, names, columns, {})
