import numpy as np
from src.core import Form
from src.task.step.base import Step
from src.task.step.steps._tree_common import parse_newick, leaves, path_lengths, tips_path, numeric_column, result_form, text_column


class TreeQuartetSupportStep(Step):
    parameters_file = "tree_quartet_support.TreeQuartetSupportStep.parameters.json"
    definition = {'id': 'tree_quartet_support', 'version': '1.0.0', 'title': 'Quartet topology support', 'description': 'Tree-induced quartet topology against expected topologies.', 'category': 'Phylogenetics', 'icon': 'tree', 'kind': 'operator', 'protocol_version': 3, 'protocol_revision': '3.7', 'inputs_arity': 2, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'dims': ['row', 'field'], 'schema': {'type': 'object', 'additionalProperties': True}}, {'dims': ['row', 'field'], 'schema': {'type': 'object', 'additionalProperties': True}}], 'output': {'mode': 'declare', 'schema': {'type': 'object', 'additionalProperties': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form']}, {'logical_type': 'form', 'representations': ['form']}], 'outputs': [{'logical_type': 'form', 'representations': ['form']}]}}

    def run(self, ctx, inputs):
        tree_form = inputs[0]
        q_form = inputs[1]
        tf = tree_form.dims[1]
        tcol = (tree_form.labels.get(tf) or {}).get("tree", 0)
        text = text_column(tree_form, tf, "tree")[0]
        root = parse_newick(text)

        def distance(a, b):
            pa = tips_path(root, a)
            pb = tips_path(root, b)
            sa = set(id(x) for x in pa)
            lca = None
            for node in pb:
                if id(node) in sa:
                    lca = node
                    break
            if lca is None:
                return float("nan")
            da = 0.0
            for node in pa:
                if node is lca:
                    break
                da += node.length
            db = 0.0
            for node in pb:
                if node is lca:
                    break
                db += node.length
            return da + db

        qf = q_form.dims[1]
        rlab = q_form.labels.get(q_form.dims[0]) or {}
        qs = [str(k) for k in sorted(rlab, key=lambda k: rlab[k])]
        tp = numeric_column(q_form, qf, "topology")
        names = []
        vals = []
        good = 0
        for i, q in enumerate(qs):
            parts = [p.strip() for p in q.replace(";", ",").split(",") if p.strip()]
            if len(parts) != 4:
                continue
            a, b, c, d = parts
            s0 = distance(a, b) + distance(c, d)
            s1 = distance(a, c) + distance(b, d)
            s2 = distance(a, d) + distance(b, c)
            topo = int(np.argmin([s0, s1, s2]))
            match = 1.0 if topo == int(tp[i]) else 0.0
            good += int(match)
            names.append(q)
            vals.append([match, float(topo), float(int(tp[i]))])
        names.append("overall")
        vals.append([good / len(names[:-1]) if len(names) > 1 else 0.0, float(good), float(len(names) - 1)])
        ctx[ctx.step_params["output"]] = result_form(names, vals, ["match", "tree_topology", "expected"])
