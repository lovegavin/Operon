"""Detect leucine-rich nuclear export signals (NES) in protein sequences."""
from __future__ import annotations

import re

import numpy as np

from src.core import Form
from src.task.context import Context
from src.task.step.base import Step

from ._sequence_common import decode_sequences
from ._protein_motifs import sanitize

# Phi-X(2,3)-Phi-X(2,3)-Phi-X-Phi with Phi in {L, I, V, F, M}.
NES_PATTERN = re.compile(r"(?=([LIVFM].{2,3}[LIVFM].{2,3}[LIVFM].[LIVFM]))")
STATS = ["nes_count", "first_start", "longest_match", "density_per_100aa"]


class ProteinNuclearExportSignalStep(Step):
    provider = 'operon-core'
    parameters_file = 'protein_nuclear_export_signal.ProteinNuclearExportSignalStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
                         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'protein_nuclear_export_signal',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'Protein nuclear export signal',
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
                                 'schema': {'ndim': 2, 'numeric': True, 'info_open': False,
                                            'axis_info_open': False,
                                            'info': {'missing_code': {'type': ['number', 'null']}}}}},
        'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
        'inputs_arity': 1,
        'outputs': [],
        'output_parameter': 'output',
        'description': 'Detect leucine-rich nuclear export signals and report their positions.',
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        seq_dim = ctx.step_params.get("sequence_dim", "sequence")
        pos_dim = ctx.step_params.get("position_dim", "position")
        out_name = ctx.step_params.get("output", self.name)
        sequences = decode_sequences(form, seq_dim, pos_dim)
        rows = []
        for raw in sequences:
            seq = sanitize(raw)
            matches = [m for m in NES_PATTERN.finditer(seq) if m.start() < len(seq)]
            count = len(matches)
            first = float(matches[0].start() + 1) if matches else 0.0
            longest = float(max(len(m.group(1)) for m in matches)) if matches else 0.0
            rows.append([float(count), first, longest, 100.0 * count / max(1, len(seq))])
        out = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=[seq_dim, "statistic"],
            labels={seq_dim: dict(form.labels[seq_dim]),
                    "statistic": {name: i for i, name in enumerate(STATS)}},
            info={"missing_code": np.nan},
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {"n_sequences": len(sequences), "statistics": STATS}

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
