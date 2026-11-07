"""Count N-X-S/T sequons (X not proline) and report density per 100 residues."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.context import Context
from src.task.step.base import Step

from ._protein_motifs import (
    NGLYC,
    count_matches,
    sanitize,
)
from ._sequence_common import decode_sequences


class ProteinNGlycSequonsStep(Step):
    provider = 'operon-core'
    parameters_file = 'protein_nglyc_sequons.ProteinNGlycSequonsStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
                         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'protein_nglyc_sequons',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'Protein N-glycosylation sequons',
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
        'description': 'Count N-X-S/T sequons (X not proline) and report density per 100 residues.',
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
            count = count_matches(NGLYC, sanitized)
            density = (100.0 * count / len(sanitized)) if sanitized else float("nan")
            rows.append([float(count), float(density)])
        data = np.asarray(rows, dtype=np.float32)
        out = Form(
            data=data,
            dims=[seq_dim, "statistic"],
            labels={seq_dim: dict(form.labels[seq_dim]),
                    "statistic": {                                  "nglyc_sequon": 0,
                                  "sequon_density_per_100": 1}},
            info={"missing_code": np.nan},
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {"n_sequences": len(sequences), "statistics": ['nglyc_sequon', 'sequon_density_per_100']}

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
