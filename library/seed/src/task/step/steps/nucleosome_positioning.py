import numpy as np
from src.core import Form
from src.task.step.base import Step
from src.task.step.steps._b62_common import names, numeric, strings, table


class NucleosomePositioningStep(Step):
    parameters_file = "nucleosome_positioning.NucleosomePositioningStep.parameters.json"

    definition = {'id': 'nucleosome_positioning', 'version': '1.0.0', 'title': 'Nucleosome positioning periodicity', 'description': 'Autocorrelation of a signal track to estimate nucleosome repeat length.', 'category': 'Epigenomics', 'icon': 'dna', 'kind': 'operator', 'protocol_version': 3, 'protocol_revision': '3.7', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'dims': ['row', 'field'], 'schema': {'type': 'object', 'additionalProperties': True}}], 'output': {'mode': 'declare', 'schema': {'type': 'object', 'additionalProperties': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form']}], 'outputs': [{'logical_type': 'form', 'representations': ['form']}]}}

    def run(self, ctx, inputs):
        form = inputs[0]
        field_dim = form.dims[1]
        signal = numeric(form, field_dim, "signal")
        step = float(ctx.step_params.get("step_bp", 10.0))
        min_lag = int(ctx.step_params.get("min_lag", 10.0))
        max_lag = int(ctx.step_params.get("max_lag", 40.0))
        x = signal - signal.mean()
        denom = float(np.dot(x, x))
        best_lag, best_r = min_lag, -1.0
        considered = 0
        for lag in range(min_lag, max_lag + 1):
            if lag >= len(x):
                break
            considered += 1
            r = float(np.dot(x[:-lag], x[lag:]) / denom) if denom > 0 else 0.0
            if r > best_r:
                best_lag, best_r = lag, r
        if considered == 0:
            raise ValueError("signal is too short for the requested lag window")
        rows = ["period_bp", "strength", "best_lag", "n_lags", "step_bp"]
        vals = [[best_lag * step], [best_r], [best_lag], [considered], [step]]
        ctx[ctx.step_params["output"]] = table(rows, vals, ["value"])
