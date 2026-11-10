import numpy as np
from src.core import Form
from src.task.step.base import Step
from src.task.step.steps._b65b_common import names, numeric, strings, table, matrix


class ScDeconvolutionStep(Step):
    parameters_file = "sc_deconvolution.ScDeconvolutionStep.parameters.json"
    definition = {'id': 'sc_deconvolution', 'version': '1.0.0', 'title': 'NNLS cell-type deconvolution', 'description': 'Non-negative least squares deconvolution of bulk expression against a signature matrix.', 'category': 'Single cell', 'icon': 'dna', 'kind': 'operator', 'protocol_version': 3, 'protocol_revision': '3.7', 'inputs_arity': 2, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'dims': ['row', 'field'], 'schema': {'type': 'object', 'additionalProperties': True}}, {'dims': ['row', 'field'], 'schema': {'type': 'object', 'additionalProperties': True}}], 'output': {'mode': 'declare', 'schema': {'type': 'object', 'additionalProperties': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form']}, {'logical_type': 'form', 'representations': ['form']}], 'outputs': [{'logical_type': 'form', 'representations': ['form']}]}}

    def run(self, ctx, inputs):
        bulk = inputs[0]
        sig = inputs[1]
        sf = sig.dims[1]
        sig_genes = names(sig)
        bulk_genes = names(bulk)
        if sig_genes != bulk_genes:
            common = [g for g in bulk_genes if g in set(sig_genes)]
            bi = [bulk_genes.index(g) for g in common]
            si = [sig_genes.index(g) for g in common]
            B = np.asarray(bulk.data[bi, :], dtype=float)
            S = np.asarray(sig.data[si, :], dtype=float)
        else:
            B = np.asarray(bulk.data, dtype=float)
            S = np.asarray(sig.data, dtype=float)
        samples = [str(c) for c in (bulk.info or {}).get("columns", [])]
        if len(samples) != B.shape[1]:
            samples = [f"sample{i}" for i in range(B.shape[1])]
        types = [f"type{i}" for i in range(S.shape[1])]
        from scipy.optimize import nnls
        props = []
        for j in range(B.shape[1]):
            w, _ = nnls(S, B[:, j])
            total = float(w.sum())
            props.append(list(w / total) if total > 0 else list(w))
        ctx[ctx.step_params["output"]] = matrix(samples, types, np.asarray(props))
