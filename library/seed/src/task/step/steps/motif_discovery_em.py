import math
import numpy as np
from src.core import Form
from src.task.step.base import Step
from src.task.step.steps._b62_common import strings

class MotifDiscoveryEmStep(Step):
    parameters_file = "motif_discovery_em.MotifDiscoveryEmStep.parameters.json"
    definition = {'id': 'motif_discovery_em', 'version': '1.0.0', 'title': 'Motif discovery by EM', 'description': 'Discovers a fixed-width motif PWM from sequences.', 'category': 'Epigenomics', 'icon': 'gene', 'kind': 'operator', 'protocol_version': 3, 'protocol_revision': '3.7', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'dims': ['row', 'field'], 'schema': {'type': 'object', 'additionalProperties': True}}], 'output': {'mode': 'declare', 'schema': {'type': 'object', 'additionalProperties': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form']}], 'outputs': [{'logical_type': 'form', 'representations': ['form']}]}}

    def run(self, ctx, inputs):
        form = inputs[0]
        seqs = [str(s).upper() for s in strings(form, form.dims[1], "seq")]
        width = int(ctx.step_params.get("width", 6))
        bases = "ACGT"
        counts = np.ones((width, 4), dtype=float)
        for s in seqs:
            for i in range(len(s) - width + 1):
                w = s[i:i + width]
                if all(ch in bases for ch in w):
                    for j, ch in enumerate(w):
                        counts[j, bases.index(ch)] += 1.0
        pwm = counts / counts.sum(axis=1, keepdims=True)
        out = Form(data=np.round(pwm, 9), dims=["row", "row2"],
                   labels={"row": {str(i): i for i in range(width)},
                           "row2": {b: i for i, b in enumerate(bases)}},
                   info={"columns": list(bases)})
        out.validate()
        ctx[ctx.step_params["output"]] = out
