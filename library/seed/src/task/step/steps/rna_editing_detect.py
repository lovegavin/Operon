import math
import numpy as np
from src.core import Form
from src.task.step.base import Step


class RnaEditingDetectStep(Step):
    parameters_file = "rna_editing_detect.RnaEditingDetectStep.parameters.json"
    definition = {'id': 'rna_editing_detect', 'version': '1.0.0', 'title': 'RNA editing candidate detection', 'description': 'Flags A>G / T>C substitutions and reports editing fraction.', 'category': 'Transcriptomics', 'icon': 'gene', 'kind': 'operator', 'protocol_version': 3, 'protocol_revision': '3.7', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'dims': ['row', 'field'], 'schema': {'type': 'object', 'additionalProperties': True}}], 'output': {'mode': 'declare', 'schema': {'type': 'object', 'additionalProperties': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form']}], 'outputs': [{'logical_type': 'form', 'representations': ['form']}]}}

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

        chrom = text("chrom"); pos = num("pos"); ref = text("ref"); alt = text("alt")
        cov = num("coverage"); ac = num("alt_count")
        names, vals = [], []
        for i in range(len(ref)):
            r = ref[i].upper(); a = alt[i].upper()
            cand = 1.0 if (r == "A" and a == "G") or (r == "T" and a == "C") else 0.0
            frac = float(ac[i] / cov[i]) if cov[i] > 0 else 0.0
            names.append(f"{chrom[i]}:{int(pos[i])}")
            vals.append([cand, frac, float(cov[i]), float(ac[i])])
        out = Form(data=np.round(np.asarray(vals, dtype=float), 9), dims=["entry", "statistic"],
                   labels={"entry": {n: i for i, n in enumerate(names)},
                           "statistic": {"candidate": 0, "fraction": 1, "coverage": 2, "alt_count": 3}},
                   info={"columns": ["candidate", "fraction", "coverage", "alt_count"]})
        out.validate()
        ctx[ctx.step_params["output"]] = out
