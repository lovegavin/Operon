"""Score an N-terminal mitochondrial presequence from charge and amphipathic moment."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.context import Context
from src.task.step.base import Step

from ._sequence_common import decode_sequences
from ._protein_motifs import sanitize
from ._protein_props import hydrophobic_moment


class ProteinMitochondrialTargetingStep(Step):
    provider = 'operon-core'
    parameters_file = 'protein_mitochondrial_targeting.ProteinMitochondrialTargetingStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
                         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'protein_mitochondrial_targeting',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'Protein mitochondrial presequence score',
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
                    'schema': {'ndim': 2, 'numeric': True, 'info_open': False, 'axis_info_open': False,
                               'info': {'missing_code': {'type': ['number', 'null']}}}}},
        'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
        'inputs_arity': 1,
        'outputs': [],
        'output_parameter': 'output',
        'description': 'Score an N-terminal mitochondrial presequence from charge and amphipathic moment.',
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        seq_dim = ctx.step_params.get("sequence_dim", "sequence")
        pos_dim = ctx.step_params.get("position_dim", "position")
        out_name = ctx.step_params.get("output", self.name)
        sequences = decode_sequences(form, seq_dim, pos_dim)
        rows = []
        for raw in sequences:
            nterm = sanitize(raw)[:30]
            positive = sum(1 for a in nterm if a in "KR")
            negative = sum(1 for a in nterm if a in "DE")
            net = float(positive - negative)
            moment = hydrophobic_moment(nterm, 100.0, 18)
            score = net + 4.0 * moment
            rows.append([float(positive), float(negative), net, moment, score])
        data = np.asarray(rows, dtype=np.float32)
        stats = ['positive_residues', 'negative_residues', 'net_charge', 'hydrophobic_moment', 'targeting_score']
        out = Form(
            data=data,
            dims=[seq_dim, "statistic"],
            labels={seq_dim: dict(form.labels[seq_dim]), "statistic": {name: i for i, name in enumerate(stats)}},
            info={"missing_code": np.nan},
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {"n_sequences": len(sequences), "statistics": stats}

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
