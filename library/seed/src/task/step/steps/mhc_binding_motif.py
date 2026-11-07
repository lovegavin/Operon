import numpy as np
from src.core import Form
from src.task.step.base import Step
from src.task.step.steps._b65b_common import names, numeric, strings, table, matrix


class MhcBindingMotifStep(Step):
    parameters_file = "mhc_binding_motif.MhcBindingMotifStep.parameters.json"
    definition = {'id': 'mhc_binding_motif', 'version': '1.0.0', 'title': 'MHC anchor binding score', 'description': 'Score peptide MHC-I anchors at P2 and P9.', 'category': 'Immunology', 'icon': 'dna', 'kind': 'operator', 'protocol_version': 3, 'protocol_revision': '3.7', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'dims': ['row', 'field'], 'schema': {'type': 'object', 'additionalProperties': True}}], 'output': {'mode': 'declare', 'schema': {'type': 'object', 'additionalProperties': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form']}], 'outputs': [{'logical_type': 'form', 'representations': ['form']}]}}

    def run(self, ctx, inputs):
        pep = inputs[0]
        col = pep.dims[0]
        labs = (pep.labels or {}).get(col) or {}
        seqs = strings(pep, col, "peptide") if "peptide" in labs else names(pep)
        anchors = set("ILMFVWY")
        rows = []
        for s in seqs:
            s = str(s).upper()
            p2 = s[1] if len(s) > 1 else ""
            p9 = s[8] if len(s) > 8 else (s[-1] if s else "")
            score = 2.0 * (p2 in anchors) + 2.0 * (p9 in anchors) + (1.0 if 8 <= len(s) <= 10 else 0.0)
            rows.append([score, 1.0 if p2 in anchors else 0.0, 1.0 if p9 in anchors else 0.0])
        ctx[ctx.step_params["output"]] = table(seqs, rows, ["score", "anchor_p2", "anchor_p9"])
