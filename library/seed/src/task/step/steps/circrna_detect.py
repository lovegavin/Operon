import math
import numpy as np
from src.core import Form
from src.task.step.base import Step


class CircrnaDetectStep(Step):
    parameters_file = "circrna_detect.CircrnaDetectStep.parameters.json"
    definition = {'id': 'circrna_detect', 'version': '1.0.0', 'title': 'Circular RNA junction detection', 'description': 'Flags back-spliced junctions and reports circular length.', 'category': 'Transcriptomics', 'icon': 'gene', 'kind': 'operator', 'protocol_version': 3, 'protocol_revision': '3.7', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'dims': ['row', 'field'], 'schema': {'type': 'object', 'additionalProperties': True}}], 'output': {'mode': 'declare', 'schema': {'type': 'object', 'additionalProperties': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form']}], 'outputs': [{'logical_type': 'form', 'representations': ['form']}]}}

    def run(self, ctx, inputs):
        form = inputs[0]
        field = form.dims[1]
        labels = form.labels.get(field) or {}
        enc = ((form.info or {}).get("encoders") or {}).get(field) or {}

        def text(name):
            idx = int(labels[name])
            v = form.data[:, idx]
            e = enc.get(name)
            if e is not None:
                if hasattr(e, "inverse_transform"):
                    return [str(x) for x in e.inverse_transform(v.astype(int))]
                if isinstance(e, dict):
                    inv = {k: vv for vv, k in e.items()}
                    return [str(inv.get(int(x), x)) for x in v]
            return [str(x) for x in v]

        def num(name):
            return np.asarray(form.data[:, int(labels[name])], dtype=float)

        chrom = text("chrom"); donor = num("donor"); acceptor = num("acceptor"); count = num("count")
        mx = float(count.max()) if len(count) else 0.0
        names, vals = [], []
        for i in range(len(chrom)):
            circ = 1.0 if acceptor[i] < donor[i] else 0.0
            length = float(donor[i] - acceptor[i] + 1.0) if circ else 0.0
            ratio = float(count[i] / mx) if mx > 0 else 0.0
            names.append(f"{chrom[i]}:{int(donor[i])}-{int(acceptor[i])}")
            vals.append([circ, length, ratio, float(count[i])])
        out = Form(data=np.round(np.asarray(vals, dtype=float), 9), dims=["entry", "statistic"],
                   labels={"entry": {n: i for i, n in enumerate(names)},
                           "statistic": {"is_circular": 0, "length": 1, "ratio": 2, "count": 3}},
                   info={"columns": ["is_circular", "length", "ratio", "count"]})
        out.validate()
        ctx[ctx.step_params["output"]] = out
