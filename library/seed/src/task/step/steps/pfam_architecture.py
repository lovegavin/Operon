"""Pfam architecture."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._annot_common import (matrix_form, numeric, row_names,
                                               strings)



class PfamArchitectureStep(Step):
    provider = "operon-core"
    parameters_file = "pfam_architecture.PfamArchitectureStep.parameters.json"

    definition = {
        "protocol_revision": "3.7",
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
            "outputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
        },
        "protocol_version": 3,
        "id": "pfam_architecture",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Pfam architecture",
        "description": "Ordered Pfam architecture string and domain counts per protein.",
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

        proteins = strings(form, field_dim, "protein", "pfam_architecture")
        starts = numeric(form, field_dim, "start", "pfam_architecture")
        domains = strings(form, field_dim, "domain", "pfam_architecture")
        grouped = {}
        for i, name in enumerate(proteins):
            grouped.setdefault(name, []).append(i)
        names = sorted(grouped)
        arch = {}
        rows = []
        for name in names:
            idx = sorted(grouped.get(name, []), key=lambda k: starts[k])
            seq = [domains[k] for k in idx]
            arch[name] = "-".join(seq)
            switches = sum(1 for a, b in zip(seq, seq[1:]) if a != b)
            rows.append((float(len(seq)), float(len(set(seq))), float(switches)))
        values = np.asarray(rows, dtype=float)
        columns = {
            "n_domains": values[:, 0],
            "n_unique_domains": values[:, 1],
            "n_architecture_switches": values[:, 2],
        }
        ctx[out_name] = matrix_form(row_dim, names, columns, {"architecture": arch})
