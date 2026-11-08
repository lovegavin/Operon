"""Re-root a Newick tree on the branch leading to a named outgroup."""
from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step
from src.task.step.steps._phylo_common import parse_newick, reroot_at_tip, tips, to_newick


def field_index(form, name):
    labels = (form.labels or {}).get(form.dims[1]) or {}
    if name not in labels:
        raise StepError("missing column %r" % name)
    return int(labels[name])


def decode(form, name):
    column = np.asarray(form.data[:, field_index(form, name)])
    encoders = ((form.info or {}).get("encoders") or {}).get(form.dims[1]) or {}
    spec = encoders.get(name)
    if spec is None:
        return [str(v) for v in column]
    if isinstance(spec, dict):
        return [str(spec[int(v)]) for v in column]
    inverse = getattr(spec, "inverse_transform", None)
    if callable(inverse):
        return [str(v) for v in inverse(column.astype(int))]
    mapping = getattr(spec, "inverse", None)
    if isinstance(mapping, dict):
        return [str(mapping[int(v)]) for v in column]
    classes = getattr(spec, "classes_", None)
    if classes is not None:
        return [str(classes[int(v)]) for v in column]
    raise StepError("cannot decode column %r" % name)


class TreeOutgroupRootStep(Step):
    parameters_file = "tree_outgroup_root.TreeOutgroupRootStep.parameters.json"

    definition = {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "tree_outgroup_root",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Outgroup rooting",
        "description": "Re-root a Newick tree on the terminal branch of a named outgroup and report root geometry.",
        "category": "Phylogenetics",
        "icon": "Tree",
        "inputs_arity": 1,
        "output_parameter": "output",
        "outputs": [],
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1, "numeric": False, "ndim": 2,
                    "dims": [{"param": "row_dim", "default": "row"}, {"param": "field_dim", "default": "field"}],
                    "labels": [], "parallel": [],
                },
            ],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
            },
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"},
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
            "outputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
        },
    }

    def run(self, ctx, inputs):
        params = ctx.step_params
        out_name = str(params.get("output", "rooted"))
        outgroup = str(params.get("outgroup", ""))
        form = inputs[0]
        if not outgroup:
            raise StepError("outgroup name is required")
        newick = decode(form, "newick")[0]
        root = parse_newick(newick)
        rooted = reroot_at_tip(root, outgroup)
        names = [tip.name for tip in tips(rooted)]
        rows = [[float(len(names)), float(len(rooted.children)), float(rooted.children[0].length or 0.0)]]
        labels = {"entry": {"rooted_tree": 0},
                  "statistic": {"n_tips": 0, "root_degree": 1, "outgroup_branch": 2}}
        out = Form(data=np.asarray(rows, dtype=np.float64), dims=["entry", "statistic"],
                   labels=labels, info={"method": "outgroup_root", "newick": to_newick(rooted), "outgroup": outgroup})
        out.validate()
        ctx[out_name] = out
