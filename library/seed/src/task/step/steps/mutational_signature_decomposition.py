"""Auto-generated b87 operator: Mutational signature decomposition."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.step.base import Step
from ._b87_common import matrix, labels, table


class MutationalSignatureDecompositionStep(Step):
    parameters_file = "mutational_signature_decomposition.MutationalSignatureDecompositionStep.parameters.json"
    definition = {'id': 'mutational_signature_decomposition', 'kind': 'operator', 'version': '1.0.0', 'title': 'Mutational signature decomposition', 'description': 'Mutational signature decomposition (batch b87).', 'category': 'Genomics', 'icon': 'operator', 'protocol_version': 3, 'protocol_revision': '3.7', 'inputs_arity': 2, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'sample_dim', 'default': 'row'}, {'param': 'channel_dim', 'default': 'field'}], 'labels': [], 'parallel': []}, {'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'signature_dim', 'default': 'row'}, {'param': 'channel_dim', 'default': 'field'}], 'labels': [], 'parallel': []}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}, {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}, 'dependencies': ['numpy>=1.24', 'scipy>=1.11']}

    def run(self, ctx, inputs):
        from scipy.optimize import nnls
        params = ctx.step_params
        out_name = params["output"]
        counts = matrix(inputs[0])
        sigs = matrix(inputs[1])
        if counts.shape[1] != sigs.shape[1]:
            raise ValueError("counts and signatures must share the channel axis")
        weights = np.maximum(sigs.sum(axis=1, keepdims=True), 1e-12)
        basis = (sigs / weights).T
        sig_labels = labels(inputs[1], inputs[1].dims[0])
        sig_names = [k for k, _ in sorted(sig_labels.items(), key=lambda kv: kv[1])] if sig_labels else [f"signature_{i + 1}" for i in range(sigs.shape[0])]
        sample_labels = labels(inputs[0], inputs[0].dims[0])
        sample_names = [k for k, _ in sorted(sample_labels.items(), key=lambda kv: kv[1])] if sample_labels else [f"sample_{i + 1}" for i in range(counts.shape[0])]
        exps = np.zeros((counts.shape[0], sigs.shape[0]))
        cosines = np.zeros(counts.shape[0])
        totals = np.zeros(counts.shape[0])
        for i in range(counts.shape[0]):
            x = counts[i]
            totals[i] = float(x.sum())
            coef, _ = nnls(basis, x)
            exps[i] = coef
            recon = basis @ coef
            denom = float(np.linalg.norm(recon) * np.linalg.norm(x))
            cosines[i] = float(recon @ x / denom) if denom > 0 else 0.0
        cols = {f"exposure_{sig_names[k]}": exps[:, k] for k in range(sigs.shape[0])}
        cols["cosine"] = cosines
        cols["total"] = totals
        ctx[out_name] = table(sample_names, cols)

