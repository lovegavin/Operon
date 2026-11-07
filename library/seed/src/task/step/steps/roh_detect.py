"""Runs of homozygosity per sample"""
import numpy as np
from src.core import Form
from src.task.step.base import Step
from src.task.step.steps._b55_common import numeric_column, row_names, string_column, table


class RohDetectStep(Step):
    parameters_file = "roh_detect.RohDetectStep.parameters.json"

    definition = {
        "id": "roh_detect",
        "version": "1.0.0",
        "title": "Runs of homozygosity per sample",
        "description": "Runs of homozygosity per sample",
        "category": "Population genetics",
        "icon": "Table",
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "kind": "operator",
        "inputs_arity": 1,
        "output_parameter": "output",
        "outputs": [],
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [
                        {
                            "param": "row_dim",
                            "default": "row"
                        },
                        {
                            "param": "field_dim",
                            "default": "field"
                        }
                    ],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2
                }
            ],
            "output": {
                "mode": "declare",
                "schema": {
                    "ndim": 2,
                    "numeric": True,
                    "info_open": True,
                    "axis_info_open": True
                }
            }
        },
        "data_formats": {
            "inputs": [
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
        "resources": {
            "memory_modes": [
                "full"
            ],
            "supports_cuda": False,
            "estimate": "estimate_memory"
        }
    }

    def run(self, ctx, inputs):
        field = inputs[0].dims[1]
        samples = string_column(inputs[0], field, "sample")
        pos = numeric_column(inputs[0], inputs[0].dims[1], "pos")
        geno = numeric_column(inputs[0], inputs[0].dims[1], "genotype")
        minv = int(ctx.step_params.get("min_variants", 2))
        order = np.argsort(pos)
        seen = []
        for i in order:
            if samples[i] not in seen:
                seen.append(samples[i])
        rows, vals = [], []
        for sm in seen:
            idx = [i for i in order if samples[i] == sm]
            runs, cur = [], []
            for i in idx:
                if geno[i] in (0, 2):
                    cur.append(i)
                else:
                    if cur:
                        runs.append(cur)
                        cur = []
            if cur:
                runs.append(cur)
            runs = [r for r in runs if len(r) >= minv]
            total = sum(float(pos[r[-1]] - pos[r[0]]) for r in runs)
            span = float(pos[idx[-1]] - pos[idx[0]]) if len(idx) > 1 else 0.0
            longest = max([float(pos[r[-1]] - pos[r[0]]) for r in runs] or [0.0])
            rows.append(sm)
            vals.append([float(len(runs)), total, longest,
                         total / span if span > 0 else 0.0])
        ctx[ctx.step_params["output"]] = table(rows, vals, ["n_roh", "total_bp", "longest_bp", "frac_span"])
        return None
