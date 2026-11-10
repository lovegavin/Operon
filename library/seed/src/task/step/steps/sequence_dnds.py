"""dN/dS ratio (Nei-Gojobori)"""

from __future__ import annotations

import math

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step

from ._b81_common import form_labels, read_strings, table


class SequenceDndsStep(Step):
    parameters_file = "sequence_dnds.SequenceDndsStep.parameters.json"

    definition = {'protocol_version': 3, 'protocol_revision': '3.7', 'id': 'sequence_dnds', 'version': '1.0.0', 'kind': 'operator', 'title': 'dN/dS ratio (Nei-Gojobori)', 'description': 'dN/dS ratio (Nei-Gojobori).', 'category': 'Sequence', 'icon': 'Dna', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': []}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'dependencies': ['numpy>=1.24', 'biopython>=1.80'], 'dependency_imports': [], 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}}

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return (32 * 1024 * 1024, 0)

    def run(self, ctx, inputs):
        from Bio.Data import CodonTable

        params = ctx.step_params
        row_dim = str(params.get("row_dim", "row"))
        field_dim = str(params.get("field_dim", "field"))
        out_name = str(params.get("output", "dnds"))
        sequences = read_strings(inputs[0], row_dim, field_dim)
        if len(sequences) < 2:
            raise StepError("sequence_dnds: need at least two coding sequences")
        for name, seq in sequences:
            if len(seq) % 3 != 0:
                raise StepError("sequence_dnds: %s length is not a multiple of three" % name)

        codon_table = CodonTable.unambiguous_dna_by_name["Standard"]
        forward = codon_table.forward_table
        bases = "TCAG"

        def amino(codon):
            return forward.get(codon, "*")

        def synonymous_fraction(codon):
            total = 0.0
            reference = amino(codon)
            for pos in range(3):
                hits = 0
                for base in bases:
                    if base == codon[pos]:
                        continue
                    changed = codon[:pos] + base + codon[pos + 1:]
                    if amino(changed) == reference:
                        hits += 1
                total += hits / 3.0
            return total

        site_cache = {}
        rows = []
        names = []
        for i in range(len(sequences)):
            for j in range(i + 1, len(sequences)):
                first_name, first = sequences[i]
                second_name, second = sequences[j]
                if len(first) != len(second):
                    raise StepError("sequence_dnds: sequences differ in length")
                syn_sites = 0.0
                nonsyn_sites = 0.0
                syn_diff = 0.0
                nonsyn_diff = 0.0
                for pos in range(0, len(first), 3):
                    codon_a = first[pos:pos + 3].upper()
                    codon_b = second[pos:pos + 3].upper()
                    for codon in (codon_a, codon_b):
                        if codon not in site_cache:
                            site_cache[codon] = synonymous_fraction(codon)
                        syn_sites += site_cache[codon]
                        nonsyn_sites += 3.0 - site_cache[codon]
                    for offset in range(3):
                        if codon_a[offset] == codon_b[offset]:
                            continue
                        hits = 0
                        for base in bases:
                            if base == codon_a[offset]:
                                continue
                            changed = codon_a[:offset] + base + codon_a[offset + 1:]
                            if amino(changed) == amino(codon_b):
                                hits += 1
                        syn_diff += hits / 3.0
                        nonsyn_diff += 1.0 - hits / 3.0
                ps = syn_diff / syn_sites if syn_sites > 0 else 0.0
                pn = nonsyn_diff / nonsyn_sites if nonsyn_sites > 0 else 0.0
                ds = -0.75 * math.log(1.0 - 4.0 * ps / 3.0) if ps < 0.75 else float("nan")
                dn = -0.75 * math.log(1.0 - 4.0 * pn / 3.0) if pn < 0.75 else float("nan")
                ratio = dn / ds if ds and math.isfinite(ds) and ds != 0 else float("nan")
                names.append("%s|%s" % (first_name, second_name))
                rows.append([dn, ds, ratio, syn_sites, nonsyn_sites, syn_diff, nonsyn_diff])
        columns = ["dN", "dS", "dN_dS_ratio", "syn_sites", "nonsyn_sites", "syn_diff", "nonsyn_diff"]
        ctx[out_name] = table(names, rows, columns)

