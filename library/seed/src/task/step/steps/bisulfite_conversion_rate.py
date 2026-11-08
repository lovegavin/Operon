"""Bisulfite conversion rate"""
from __future__ import annotations

import numpy as np

from src.core.forms.form import Form
from src.task.step.base import Step
from src.task.step.steps._b79_common import numeric, table


def definition(category, arity, outputs_dims):
    return {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "bisulfite_conversion_rate",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Bisulfite conversion rate",
        "description": "Estimate bisulfite conversion efficiency from converted and unconverted cytosine counts with a Wilson interval.",
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


class BisulfiteConversionRateStep(Step):
    parameters_file = "bisulfite_conversion_rate.BisulfiteConversionRateStep.parameters.json"

    definition = {'protocol_version': 3, 'protocol_revision': '3.7', 'id': 'bisulfite_conversion_rate', 'version': '1.0.0', 'kind': 'operator', 'title': 'Bisulfite conversion rate', 'description': 'Estimate bisulfite conversion efficiency from converted and unconverted cytosine counts with a Wilson interval.', 'category': 'Epigenomics', 'icon': 'Methylation', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': []}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}}


    def run(self, ctx, inputs):
        params = ctx.step_params
        out_name = str(params.get("output", "conversion"))
        form = inputs[0]
        converted = numeric(form, "converted")
        unconverted = numeric(form, "unconverted")
        if converted.shape != unconverted.shape:
            raise ValueError("converted and unconverted differ in length")
        total = float(converted.sum() + unconverted.sum())
        if total <= 0:
            raise ValueError("no cytosines observed")
        rate = float(converted.sum()) / total
        z = 1.959963984540054
        denom = 1.0 + z * z / total
        centre = (rate + z * z / (2.0 * total)) / denom
        half = z * np.sqrt(rate * (1.0 - rate) / total + z * z / (4.0 * total * total)) / denom
        values = [len(converted), float(converted.sum()), float(unconverted.sum()),
                  rate, max(0.0, centre - half), min(1.0, centre + half)]
        columns = ["n_sites", "converted", "unconverted", "conversion_rate", "ci_low", "ci_high"]
        ctx[out_name] = table(["conversion"], [values], columns)


    def run(self, ctx, inputs):
        params = ctx.step_params
        out_name = str(params.get("output", "conversion"))
        form = inputs[0]
        converted = numeric(form, "converted")
        unconverted = numeric(form, "unconverted")
        if converted.shape != unconverted.shape:
            raise ValueError("converted and unconverted differ in length")
        total = float(converted.sum() + unconverted.sum())
        if total <= 0:
            raise ValueError("no cytosines observed")
        rate = float(converted.sum()) / total
        z = 1.959963984540054
        denom = 1.0 + z * z / total
        centre = (rate + z * z / (2.0 * total)) / denom
        half = z * np.sqrt(rate * (1.0 - rate) / total + z * z / (4.0 * total * total)) / denom
        values = [len(converted), float(converted.sum()), float(unconverted.sum()),
                  rate, max(0.0, centre - half), min(1.0, centre + half)]
        columns = ["n_sites", "converted", "unconverted", "conversion_rate", "ci_low", "ci_high"]
        ctx[out_name] = table(["conversion"], [values], columns)
