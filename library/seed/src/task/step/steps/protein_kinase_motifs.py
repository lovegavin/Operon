"""Count minimal PKA (RRxS/T), CK2 (S/TxxD/E) and CDK (S/T-P-x-K/R) motifs."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.context import Context
from src.task.step.base import Step

from ._protein_motifs import (
    CDK,
    CK2,
    PKA,
    count_matches,
    sanitize,
)
from ._sequence_common import decode_sequences


class ProteinKinaseMotifsStep(Step):
    provider = 'operon-core'
    parameters_file = 'protein_kinase_motifs.ProteinKinaseMotifsStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
                         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'protein_kinase_motifs',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'Protein kinase motifs',
        'category': 'Omics',
        'contracts': {'version': 1,
                       'inputs': [{
                    'version': 1,
                    'numeric': True,
                    'info': {'representation': {'type': 'string', 'const': 'sequence_codes'},
                             'alphabet': {'type': 'string', 'const': 'protein'},
                             'missing_code': {'type': ['number', 'null']}},
                    'dims': [{'param': 'sequence_dim', 'default': 'sequence'},
                             {'param': 'position_dim', 'default': 'position'}],
                    'labels': [],
                    'parallel': [],
                    'ndim': 2}],
                       'output': {'mode': 'declare',
                    'schema': {'ndim': 2,
                               'numeric': True,
                               'info_open': False,
                               'axis_info_open': False,
                               'info': {'missing_code': {'type': ['number', 'null']}}}}},
        'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
        'inputs_arity': 1,
        'outputs': [],
        'output_parameter': 'output',
        'description': 'Count minimal PKA (RRxS/T), CK2 (S/TxxD/E) and CDK (S/T-P-x-K/R) motifs.',
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        seq_dim = ctx.step_params.get("sequence_dim", "sequence")
        pos_dim = ctx.step_params.get("position_dim", "position")
        out_name = ctx.step_params.get("output", self.name)
        sequences = decode_sequences(form, seq_dim, pos_dim)
        rows = []
        for raw in sequences:
            sanitized = sanitize(raw)
            pka = count_matches(PKA, sanitized)
            ck2 = count_matches(CK2, sanitized)
            cdk = count_matches(CDK, sanitized)
            rows.append([float(pka), float(ck2), float(cdk), float(pka + ck2 + cdk)])
        data = np.asarray(rows, dtype=np.float32)
        out = Form(
            data=data,
            dims=[seq_dim, "statistic"],
            labels={seq_dim: dict(form.labels[seq_dim]),
                    "statistic": {                                  "pka_motif": 0,
                                  "ck2_motif": 1,
                                  "cdk_motif": 2,
                                  "total_kinase_motif": 3}},
            info={"missing_code": np.nan},
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {"n_sequences": len(sequences), "statistics": ['pka_motif', 'ck2_motif', 'cdk_motif', 'total_kinase_motif']}

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
