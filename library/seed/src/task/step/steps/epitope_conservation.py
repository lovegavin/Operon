"""Per-position conservation of aligned epitope sequences"""
import numpy as np
from src.core import Form
from src.task.step.base import Step
from src.task.step.steps._b62b_common import column, string_column, table

class EpitopeConservationStep(Step):
    parameters_file = "epitope_conservation.EpitopeConservationStep.parameters.json"

    definition = {
        "id": "epitope_conservation",
        "version": "1.0.0",
        "title": "Per-position conservation of aligned epitope sequences",
        "description": "Per-position conservation of aligned epitope sequences",
        "category": "Immunology",
        "icon": "Table",
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "kind": "operator",
        "inputs_arity": 1,
        "output_parameter": "output",
        "outputs": [],
        "contracts": {
            "version": 1,
            "inputs": [{"version": 1, "numeric": True, "dims": [{"param": "row_dim", "default": "row"}, {"param": "field_dim", "default": "field"}], "labels": [], "parallel": [], "ndim": 2}],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}
        },
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"]}],
            "outputs": [{"logical_type": "form", "representations": ["form"]}]
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"}
    }

    def run(self, ctx, inputs):

        seqs = string_column(inputs[0], "sequence")
        maxlen = max(len(s) for s in seqs) if seqs else 0
        rows = []
        vals = []
        for pos in range(maxlen):
            chars = [s[pos] if pos < len(s) else "-" for s in seqs]
            gaps = sum(1 for c in chars if c == "-") / len(chars)
            clean = [c for c in chars if c != "-"]
            if not clean:
                rows.append(str(pos + 1)); vals.append([0.0, 0.0, gaps, 0.0]); continue
            counts = {}
            for c in clean:
                counts[c] = counts.get(c, 0) + 1
            p = np.array(list(counts.values()), dtype=float) / len(clean)
            ent = float(-(p * np.log2(p)).sum())
            rows.append(str(pos + 1))
            vals.append([ent, 1.0 - ent / np.log2(20.0), gaps, float(p.max())])
        ctx[ctx.step_params["output"]] = table(rows, ["entropy", "conservation", "gap_fraction", "major_residue_fraction"], vals)
        return None
