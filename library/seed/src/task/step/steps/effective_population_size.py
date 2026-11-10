"""Effective population size from temporal allele frequencies"""
import numpy as np
from src.core import Form
from src.task.step.base import Step
from src.task.step.steps._b55_common import numeric_column, row_names, string_column, table


class EffectivePopulationSizeStep(Step):
    parameters_file = "effective_population_size.EffectivePopulationSizeStep.parameters.json"

    definition = {
        "id": "effective_population_size",
        "version": "1.0.0",
        "title": "Effective population size from temporal allele frequencies",
        "description": "Effective population size from temporal allele frequencies",
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
        names = row_names(inputs[0])
        p0 = numeric_column(inputs[0], inputs[0].dims[1], "p0")
        p1 = numeric_column(inputs[0], inputs[0].dims[1], "p1")
        gen = numeric_column(inputs[0], inputs[0].dims[1], "generations")
        rows, vals = [], []
        for i, v in enumerate(names):
            pm = (p0[i] + p1[i]) / 2.0
            denom = pm * (1.0 - pm)
            fc = ((p1[i] - p0[i]) ** 2) / denom if denom > 0 else np.nan
            ne = gen[i] / (2.0 * fc) if np.isfinite(fc) and fc > 0 else np.nan
            rows.append(v)
            vals.append([fc, ne, gen[i]])
        ctx[ctx.step_params["output"]] = table(rows, vals, ["fc", "ne", "generations"])
        return None
