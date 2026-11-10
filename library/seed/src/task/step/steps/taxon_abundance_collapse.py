import numpy as np
from src.core import Form
from src.task.step.base import Step
from src.task.step.steps._b58b_common import matrix_form, strings




class TaxonAbundanceCollapseStep(Step):

    definition = {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "taxon_abundance_collapse",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Collapse a taxonomic abundance table to one rank",
        "category": "Metagenomics",
        "icon": "Table",
        "description": "Aggregate taxa sharing a rank prefix (for example g__) across samples.",
        "inputs_arity": 1,
        "output_parameter": "output",
        "outputs": [],
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [
                        {"param": "taxon_dim", "default": "taxon"},
                        {"param": "sample_dim", "default": "sample"}
                    ],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2
                }
            ],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}
            }
        },
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"]}],
            "outputs": [{"logical_type": "form", "representations": ["form"]}]
        },
        "resources": {
            "memory_modes": ["full"],
            "supports_cuda": False,
            "estimate": "estimate_memory"
        }
    }
    parameters_file = "taxon_abundance_collapse.TaxonAbundanceCollapseStep.parameters.json"

    def run(self, ctx, inputs):
        rank = ctx.step_params.get("rank", "genus")
        order = ["d", "p", "c", "o", "f", "g", "s"]
        prefix = "%s__" % order[["phylum", "class", "order", "family", "genus", "species"].index(rank) + 1]
        names = strings(inputs[0], "taxon")
        cols = sorted((inputs[0].labels.get("sample", {}) or {}).items(), key=lambda kv: kv[1])
        columns = [k for k, _ in cols]
        data = inputs[0].data
        agg = {}
        for i, name in enumerate(names):
            parts = [p for p in name.split(";") if p.startswith(prefix)]
            key = parts[0] if parts else "unclassified"
            agg.setdefault(key, np.zeros(len(columns)))
            agg[key] += data[i]
        keys = sorted(agg)
        out = matrix_form(keys, columns, np.vstack([agg[k] for k in keys]) if keys else np.zeros((0, len(columns))),
                          {"rank": rank, "n_input_taxa": len(names)})
        ctx[ctx.step_params["output"]] = out
        return None

