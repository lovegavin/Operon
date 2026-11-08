"""Mismatch distribution"""

from __future__ import annotations

import math

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step

from ._b81_common import form_labels, read_strings, table


class MismatchDistributionStep(Step):
    parameters_file = "mismatch_distribution.MismatchDistributionStep.parameters.json"

    definition = {'protocol_version': 3, 'protocol_revision': '3.7', 'id': 'mismatch_distribution', 'version': '1.0.0', 'kind': 'operator', 'title': 'Mismatch distribution', 'description': 'Mismatch distribution.', 'category': 'Population genetics', 'icon': 'Dna', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': []}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'dependencies': ['numpy>=1.24'], 'dependency_imports': [], 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}}

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return (32 * 1024 * 1024, 0)

    def run(self, ctx, inputs):
        params = ctx.step_params
        row_dim = str(params.get("row_dim", "row"))
        field_dim = str(params.get("field_dim", "field"))
        out_name = str(params.get("output", "mismatch"))
        sequences = read_strings(inputs[0], row_dim, field_dim)
        if len(sequences) < 2:
            raise StepError("mismatch_distribution: need at least two sequences")
        lengths = {len(seq) for _, seq in sequences}
        if len(lengths) != 1:
            raise StepError("mismatch_distribution: sequences differ in length")
        diffs = []
        for i in range(len(sequences)):
            for j in range(i + 1, len(sequences)):
                diffs.append(sum(a != b for a, b in zip(sequences[i][1], sequences[j][1])))
        count = len(diffs)
        mean = float(np.mean(diffs))
        variance = float(np.var(diffs, ddof=1)) if count > 1 else 0.0
        maximum = int(max(diffs))
        histogram = np.zeros(maximum + 1, dtype=np.float64)
        for value in diffs:
            histogram[int(value)] += 1.0
        fractions = histogram / count
        raggedness = float(np.sum((fractions[:-1] - fractions[1:]) ** 2)) if maximum > 0 else 0.0
        mode = int(np.argmax(histogram))
        ctx[out_name] = table(
            ["mismatch"],
            [[count, mean, variance, maximum, mode, raggedness]],
            ["n_pairs", "mean_mismatches", "var_mismatches", "max_mismatch", "mode_mismatch", "raggedness_index"],
        )

