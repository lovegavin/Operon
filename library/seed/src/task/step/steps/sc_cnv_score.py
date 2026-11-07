import numpy as np
from src.core import Form
from src.task.step.base import Step
from src.task.step.steps._b65b_common import names, numeric, strings, table, matrix


class ScCnvScoreStep(Step):
    parameters_file = "sc_cnv_score.ScCnvScoreStep.parameters.json"
    definition = {'id': 'sc_cnv_score', 'version': '1.0.0', 'title': 'Per-cell CNV score', 'description': 'Average absolute arm-level z-score per cell.', 'category': 'Single cell', 'icon': 'dna', 'kind': 'operator', 'protocol_version': 3, 'protocol_revision': '3.7', 'inputs_arity': 2, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'dims': ['row', 'field'], 'schema': {'type': 'object', 'additionalProperties': True}}, {'dims': ['row', 'field'], 'schema': {'type': 'object', 'additionalProperties': True}}], 'output': {'mode': 'declare', 'schema': {'type': 'object', 'additionalProperties': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form']}, {'logical_type': 'form', 'representations': ['form']}], 'outputs': [{'logical_type': 'form', 'representations': ['form']}]}}

    def run(self, ctx, inputs):
        expr = inputs[0]
        arm = inputs[1]
        af = arm.dims[1]
        arms = strings(arm, af, "arm")
        map_rows = names(arm)
        gene_to_arm = {map_rows[i]: arms[i] for i in range(len(map_rows))}
        cells = [str(c) for c in (expr.info or {}).get("columns", [])]
        if len(cells) != expr.data.shape[1]:
            cells = [f"cell{i}" for i in range(expr.data.shape[1])]
        gene_names = names(expr)
        buckets = {}
        for i, g in enumerate(gene_names):
            a = gene_to_arm.get(g)
            if a is None:
                continue
            buckets.setdefault(a, []).append(i)
        rows = []
        for j in range(expr.data.shape[1]):
            scores = []
            for a, idxs in buckets.items():
                v = np.asarray(expr.data[idxs, j], dtype=float)
                sd = float(v.std(ddof=0))
                if sd > 0:
                    scores.append(float(np.abs((v - v.mean()) / sd).mean()))
            rows.append([float(np.mean(scores)) if scores else 0.0, float(len(scores))])
        ctx[ctx.step_params["output"]] = table(cells, rows, ["cnv_score", "n_arms"])
