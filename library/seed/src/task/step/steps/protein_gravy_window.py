"""Summarize Kyte-Doolittle GRAVY over 9-residue windows."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.context import Context
from src.task.step.base import Step

from ._sequence_common import decode_sequences
from ._protein_motifs import sanitize
from ._protein_props import gravy, gravy_windows


class ProteinGravyWindowStep(Step):
    provider = 'operon-core'
    parameters_file = 'protein_gravy_window.ProteinGravyWindowStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
                         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'protein_gravy_window',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'Protein GRAVY sliding window',
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
        'description': 'Summarize Kyte-Doolittle GRAVY over 9-residue windows.',
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        seq_dim = ctx.step_params.get("sequence_dim", "sequence")
        pos_dim = ctx.step_params.get("position_dim", "position")
        out_name = ctx.step_params.get("output", self.name)
        sequences = decode_sequences(form, seq_dim, pos_dim)
        rows = []
        for raw in sequences:
            windows = gravy_windows(raw, 9)
            if not windows:
                windows = [gravy(raw)]
            peak = max(range(len(windows)), key=lambda i: windows[i])
            rows.append([gravy(raw), max(windows), min(windows), float(peak + 1)])
        data = np.asarray(rows, dtype=np.float32)
        stats = ['gravy_mean', 'gravy_max', 'gravy_min', 'max_window_start']
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
