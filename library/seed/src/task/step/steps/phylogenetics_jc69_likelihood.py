"""JC69 likelihood of an alignment on a fixed tree."""
from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step
from src.task.step.steps._phylo_common import log_likelihood, parse_newick


def field_index(form, name):
    labels = (form.labels or {}).get(form.dims[1]) or {}
    if name not in labels:
        raise StepError("missing column %r" % name)
    return int(labels[name])


def decode(form, dim, name):
    column = np.asarray(form.data[:, field_index(form, name)])
    encoders = ((form.info or {}).get("encoders") or {}).get(dim) or {}
    spec = encoders.get(name)
    if spec is None:
        return [str(int(v)) if float(v).is_integer() else str(v) for v in column]
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


class PhylogeneticsJc69LikelihoodStep(Step):
    parameters_file = "phylogenetics_jc69_likelihood.PhylogeneticsJc69LikelihoodStep.parameters.json"

    definition = {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "phylogenetics_jc69_likelihood",
        "version": "1.0.0",
        "kind": "operator",
        "title": "JC69 tree likelihood",
        "description": "Felsenstein pruning log-likelihood of an aligned nucleotide matrix on a fixed Newick tree under the JC69 model.",
        "category": "Phylogenetics",
        "icon": "Tree",
        "inputs_arity": 2,
        "output_parameter": "output",
        "outputs": [],
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1, "numeric": False, "ndim": 2,
                    "dims": [{"param": "tree_dim", "default": "row"}, {"param": "field_dim", "default": "field"}],
                    "labels": [], "parallel": [],
                },
                {
                    "version": 1, "numeric": False, "ndim": 2,
                    "dims": [{"param": "taxon_dim", "default": "taxon"}, {"param": "site_dim", "default": "site"}],
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
            "inputs": [
                {"logical_type": "form", "representations": ["form"], "metadata": {}},
                {"logical_type": "form", "representations": ["form"], "metadata": {}},
            ],
            "outputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
        },
    }

    def run(self, ctx, inputs):
        params = ctx.step_params
        tree_dim = str(params.get("tree_dim", "row"))
        field_dim = str(params.get("field_dim", "field"))
        taxon_dim = str(params.get("taxon_dim", "taxon"))
        site_dim = str(params.get("site_dim", "site"))
        out_name = str(params.get("output", "likelihood"))
        tree_form, aln_form = inputs
        if list(tree_form.dims) != [tree_dim, field_dim]:
            raise StepError("unexpected tree dims %s" % (list(tree_form.dims),))
        if list(aln_form.dims) != [taxon_dim, site_dim]:
            raise StepError("unexpected alignment dims %s" % (list(aln_form.dims),))
        newick = decode(tree_form, field_dim, "newick")[0]
        names = [str(k) for k, _ in sorted(((aln_form.labels or {}).get(taxon_dim) or {}).items(), key=lambda kv: int(kv[1]))]
        sequences = {}
        for column in sorted(((aln_form.labels or {}).get(site_dim) or {}).items(), key=lambda kv: int(kv[1])):
            site = column[0]
            values = decode(aln_form, site_dim, site)
            for name, value in zip(names, values):
                sequences.setdefault(name, "")
                sequences[name] += value
        root = parse_newick(newick)
        logl, n_taxa, n_sites = log_likelihood(root, sequences)
        labels = {"entry": {"log_likelihood": 0}, "statistic": {"value": 0}}
        data = np.asarray([[round(logl, 9)]], dtype=np.float64)
        out = Form(data=data, dims=["entry", "statistic"],
                   labels={"entry": {"log_likelihood": 0}, "statistic": {"value": 0}},
                   info={"method": "jc69_pruning", "n_sites": n_sites, "n_taxa": n_taxa})
        out.validate()
        ctx[out_name] = out
