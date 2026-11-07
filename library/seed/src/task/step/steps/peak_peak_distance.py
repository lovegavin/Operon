import numpy as np
from src.core import Form
from src.task.step.base import Step
from src.task.step.steps._b62_common import names, numeric, table


class PeakPeakDistanceStep(Step):
    parameters_file = "peak_peak_distance.PeakPeakDistanceStep.parameters.json"

    definition = {'id': 'peak_peak_distance', 'version': '1.0.0', 'title': 'Nearest peak distance', 'description': 'For each peak, report the distance to the closest other peak midpoint.', 'category': 'Epigenomics', 'icon': 'dna', 'kind': 'operator', 'protocol_version': 3, 'protocol_revision': '3.7', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'dims': ['row', 'field'], 'schema': {'type': 'object', 'additionalProperties': True}}], 'output': {'mode': 'declare', 'schema': {'type': 'object', 'additionalProperties': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form']}], 'outputs': [{'logical_type': 'form', 'representations': ['form']}]}}

    def run(self, ctx, inputs):
        form = inputs[0]
        field_dim = form.dims[1]
        start = numeric(form, field_dim, "start")
        end = numeric(form, field_dim, "end")
        if len(start) < 2:
            raise ValueError("at least two peaks are required")
        center = (start + end) / 2.0
        diff = np.abs(center[:, None] - center[None, :])
        np.fill_diagonal(diff, np.inf)
        nearest = diff.argmin(axis=1)
        dist = diff[np.arange(len(center)), nearest]
        rows = names(form)
        vals = [[float(dist[i]), int(nearest[i])] for i in range(len(center))]
        ctx[ctx.step_params["output"]] = table(rows, vals, ["nearest_distance", "nearest_index"])
