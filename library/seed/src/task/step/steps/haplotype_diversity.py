"""Haplotype and nucleotide diversity"""

from __future__ import annotations

import math

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step

from ._b81_common import form_labels, read_strings, table


class HaplotypeDiversityStep(Step):
    parameters_file = "haplotype_diversity.HaplotypeDiversityStep.parameters.json"

    definition = {'protocol_version': 3, 'protocol_revision': '3.7', 'id': 'haplotype_diversity', 'version': '1.0.0', 'kind': 'operator', 'title': 'Haplotype and nucleotide diversity', 'description': 'Haplotype and nucleotide diversity.', 'category': 'Population genetics', 'icon': 'Dna', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': []}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'dependencies': ['numpy>=1.24'], 'dependency_imports': [], 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}}

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return (32 * 1024 * 1024, 0)

    def run(self, ctx, inputs):
        params = ctx.step_params
        row_dim = str(params.get("row_dim", "row"))
        field_dim = str(params.get("field_dim", "field"))
        out_name = str(params.get("output", "diversity"))
        sequences = read_strings(inputs[0], row_dim, field_dim)
        if not sequences:
            raise StepError("haplotype_diversity: empty alignment")
        lengths = {len(seq) for _, seq in sequences}
        if len(lengths) != 1:
            raise StepError("haplotype_diversity: sequences differ in length")
        length = lengths.pop()
        counts = {}
        for _, seq in sequences:
            counts[seq] = counts.get(seq, 0) + 1
        n = len(sequences)
        k = len(counts)
        hd = 0.0
        if n > 1:
            hd = (n / (n - 1.0)) * (1.0 - sum((c / n) ** 2 for c in counts.values()))
        pair_diffs = 0.0
        pairs = 0
        for i in range(n):
            for j in range(i + 1, n):
                pairs += 1
                pair_diffs += sum(a != b for a, b in zip(sequences[i][1], sequences[j][1]))
        pi = pair_diffs / pairs / length if pairs and length else 0.0
        segregating = sum(1 for column in range(length) if len({seq[column] for _, seq in sequences}) > 1)
        ctx[out_name] = table(
            ["diversity"],
            [[n, k, hd, pi, segregating]],
            ["n_sequences", "n_haplotypes", "haplotype_diversity", "nucleotide_diversity", "segregating_sites"],
        )

