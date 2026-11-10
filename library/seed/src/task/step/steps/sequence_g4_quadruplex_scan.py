"""G-quadruplex tract scanning (G3+ runs with short loops)."""
from __future__ import annotations

import re

import numpy as np

from src.task.step.base import Step

from src.core import Form

from ._b91_common import row_names, strings


class SequenceG4QuadruplexScanStep(Step):
    parameters_file = "sequence_g4_quadruplex_scan.SequenceG4QuadruplexScanStep.parameters.json"
    definition = {'protocol_version': 3, 'protocol_revision': '3.7', 'kind': 'operator', 'id': 'sequence_g4_quadruplex_scan', 'version': '1.0.0', 'title': 'G-quadruplex tract scan', 'description': 'Counts G3+ tracts separated by short loops as a G-quadruplex propensity proxy.', 'category': 'Sequence', 'icon': 'dna', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': []}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}, 'dependencies': ['numpy>=1.24'], 'dependency_imports': []}

    def run(self, ctx, inputs):
        params = ctx.step_params
        form = inputs[0]
        seqs = strings(form, form.dims[1], params["sequence_column"])
        min_tracts = int(params.get("min_tracts", 4))
        min_g = int(params.get("min_g", 3))
        max_loop = int(params.get("max_loop", 7))
        pattern = re.compile(r"G{%d,}(?:[^G]{1,%d}G{%d,}){%d,}" % (min_g, max_loop, min_g, min_tracts - 1))
        counts = []
        spans = []
        tracts = []
        for seq in seqs:
            s = (seq or "").upper()
            hits = list(pattern.finditer(s))
            counts.append(float(len(hits)))
            spans.append(float(max((m.end() - m.start() for m in hits), default=0)))
            runs = re.findall(r"G{%d,}" % min_g, s)
            tracts.append(float(max((len(r) for r in runs), default=0)))
        names = row_names(form)
        cols = ["n_g4", "max_span", "max_g_tract"]
        mat = np.column_stack([counts, spans, tracts]).astype(float)
        ctx[params["output"]] = Form(
            data=mat,
            dims=["sequence", "statistic"],
            labels={"sequence": {n: i for i, n in enumerate(names)},
                    "statistic": {c: i for i, c in enumerate(cols)}},
        )
