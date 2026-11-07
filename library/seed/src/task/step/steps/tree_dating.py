import numpy as np
from src.core import Form
from src.task.step.base import Step
from src.task.step.steps._tree_common import parse_newick, leaves, path_lengths, tips_path, numeric_column, result_form, text_column


class TreeDatingStep(Step):
    parameters_file = "tree_dating.TreeDatingStep.parameters.json"
    definition = {'id': 'tree_dating', 'version': '1.0.0', 'title': 'Root-to-tip dating', 'description': 'Root-to-tip regression against tip dates.', 'category': 'Phylogenetics', 'icon': 'tree', 'kind': 'operator', 'protocol_version': 3, 'protocol_revision': '3.7', 'inputs_arity': 2, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'dims': ['row', 'field'], 'schema': {'type': 'object', 'additionalProperties': True}}, {'dims': ['row', 'field'], 'schema': {'type': 'object', 'additionalProperties': True}}], 'output': {'mode': 'declare', 'schema': {'type': 'object', 'additionalProperties': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form']}, {'logical_type': 'form', 'representations': ['form']}], 'outputs': [{'logical_type': 'form', 'representations': ['form']}]}}

    def run(self, ctx, inputs):
        tree_form = inputs[0]
        date_form = inputs[1]
        tf = tree_form.dims[1]
        text = text_column(tree_form, tf, "tree")[0]
        root = parse_newick(text)
        dist = path_lengths(root)
        df = date_form.dims[1]
        rlab = date_form.labels.get(date_form.dims[0]) or {}
        tips = [str(k) for k in sorted(rlab, key=lambda k: rlab[k])]
        dates = numeric_column(date_form, df, "date")
        x = []
        y = []
        for i, t in enumerate(tips):
            if t in dist:
                x.append(float(dates[i]))
                y.append(float(dist[t]))
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        n = len(x)
        if n > 2 and float(x.std()) > 0:
            slope, intercept = np.polyfit(x, y, 1)
            pred = slope * x + intercept
            ss_res = float(((y - pred) ** 2).sum())
            ss_tot = float(((y - y.mean()) ** 2).sum())
            r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
        else:
            slope = intercept = r2 = float("nan")
        ctx[ctx.step_params["output"]] = result_form(["overall"], [[slope, float(intercept), r2, float(n)]],
                                                     ["slope", "intercept", "r2", "n_tips"])
