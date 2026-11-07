import numpy as np
from src.core import Form
from src.task.step.base import Step
from src.task.step.steps._b62_common import names, numeric, strings, table
from scipy import stats


class MotifEnrichmentStep(Step):
    parameters_file = "motif_enrichment.MotifEnrichmentStep.parameters.json"

    definition = {'id': 'motif_enrichment', 'version': '1.0.0', 'title': 'Motif enrichment', 'description': 'One-sided Fisher exact test of motif occurrence in foreground versus background sequences.', 'category': 'Epigenomics', 'icon': 'dna', 'kind': 'operator', 'protocol_version': 3, 'protocol_revision': '3.7', 'inputs_arity': 2, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'dims': ['row', 'field'], 'schema': {'type': 'object', 'additionalProperties': True}}, {'dims': ['row', 'field'], 'schema': {'type': 'object', 'additionalProperties': True}}], 'output': {'mode': 'declare', 'schema': {'type': 'object', 'additionalProperties': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form']}, {'logical_type': 'form', 'representations': ['form']}], 'outputs': [{'logical_type': 'form', 'representations': ['form']}]}}

    def run(self, ctx, inputs):
        motif = str(ctx.step_params.get("motif", "")).upper()
        if not motif:
            raise ValueError("motif must be a non-empty string")

        def count(form):
            seqs = [s.upper() for s in strings(form, form.dims[1], "seq")]
            return sum(1 for s in seqs if motif in s), len(seqs)

        k1, n1 = count(inputs[0])
        k2, n2 = count(inputs[1])
        if n1 == 0 or n2 == 0:
            raise ValueError("foreground and background need at least one sequence")
        odds, p = stats.fisher_exact([[k1, n1 - k1], [k2, n2 - k2]], alternative="greater")
        f1, f2 = k1 / n1, k2 / n2
        rows = ["motif_count_fg", "n_fg", "motif_count_bg", "n_bg", "fold", "odds_ratio", "p_value"]
        vals = [[k1], [n1], [k2], [n2], [f1 / f2 if f2 else float("inf")], [odds], [p]]
        ctx[ctx.step_params["output"]] = table(rows, vals, ["value"])
