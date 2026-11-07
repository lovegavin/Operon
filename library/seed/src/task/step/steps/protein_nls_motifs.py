"""Count monopartite and bipartite nuclear localization signal motifs."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.context import Context
from src.task.step.base import Step

from ._protein_motifs import (
    BIPARTITE_NLS,
    MONO_NLS,
    count_matches,
    sanitize,
)
from ._sequence_common import decode_sequences


class ProteinNlsMotifsStep(Step):
    provider = 'operon-core'
    parameters_file = 'protein_nls_motifs.ProteinNlsMotifsStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
                         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'protein_nls_motifs',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'Protein NLS motifs',
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
        'description': 'Count monopartite and bipartite nuclear localization signal motifs.',
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
            mono = count_matches(MONO_NLS, sanitized)
            bi = count_matches(BIPARTITE_NLS, sanitized)
            rows.append([float(mono), float(bi), float(mono + bi)])
        data = np.asarray(rows, dtype=np.float32)
        out = Form(
            data=data,
            dims=[seq_dim, "statistic"],
            labels={seq_dim: dict(form.labels[seq_dim]),
                    "statistic": {                                  "monopartite_nls": 0,
                                  "bipartite_nls": 1,
                                  "total_nls": 2}},
            info={"missing_code": np.nan},
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {"n_sequences": len(sequences), "statistics": ['monopartite_nls', 'bipartite_nls', 'total_nls']}

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
