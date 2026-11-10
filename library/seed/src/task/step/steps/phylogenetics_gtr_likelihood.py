"""GTR likelihood of an alignment on a fixed Newick tree."""
from __future__ import annotations

import math
import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step


def field_column(form, name):
    labels = (form.labels or {}).get(form.dims[1]) or {}
    if name not in labels:
        raise StepError("missing column %r" % name)
    return np.asarray(form.data[:, int(labels[name])], dtype=float)


def text_column(form, dim, name):
    values = field_column(form, name)
    encoders = ((form.info or {}).get("encoders") or {}).get(dim) or {}
    spec = encoders.get(name)
    if isinstance(spec, dict):
        return [str(spec[int(v)]) for v in values]
    inverse = getattr(spec, "inverse_transform", None)
    if callable(inverse):
        return [str(v) for v in inverse(values.astype(int))]
    mapping = getattr(spec, "inverse", None)
    if isinstance(mapping, dict):
        return [str(mapping[int(v)]) for v in values]
    return [str(int(v)) if float(v).is_integer() else str(v) for v in values]


def encoded_column(form, dim, name):
    values = np.asarray(form.data[:, int((form.labels or {})[dim][name])], dtype=float)
    encoders = ((form.info or {}).get("encoders") or {}).get(dim) or {}
    spec = encoders.get(name)
    if isinstance(spec, dict):
        return [str(spec[int(v)]).upper() for v in values]
    inverse = getattr(spec, "inverse_transform", None)
    if callable(inverse):
        return [str(v).upper() for v in inverse(values.astype(int))]
    return [str(int(v)) for v in values]


def transition(q, freqs, t):
    q = q * freqs[None, :]
    np.fill_diagonal(q, 0.0)
    np.fill_diagonal(q, -q.sum(axis=1))
    scale = -float(np.dot(freqs, np.diag(q)))
    q = q / scale
    values, vectors = np.linalg.eig(q)
    inverse = np.linalg.inv(vectors)
    p = np.real(vectors @ np.diag(np.exp(values * t)) @ inverse)
    p = np.clip(p, 0.0, None)
    return p / p.sum(axis=1, keepdims=True)


class PhylogeneticsGtrLikelihoodStep(Step):
    parameters_file = "phylogenetics_gtr_likelihood.PhylogeneticsGtrLikelihoodStep.parameters.json"

    definition = {'category': 'Phylogenetics',
 'contracts': {'inputs': [{'dims': [{'default': 'row', 'param': 'tree_dim'},
                                    {'default': 'field', 'param': 'field_dim'}],
                           'labels': [],
                           'ndim': 2,
                           'numeric': False,
                           'parallel': [],
                           'version': 1},
                          {'dims': [{'default': 'taxon', 'param': 'taxon_dim'},
                                    {'default': 'site', 'param': 'site_dim'}],
                           'labels': [],
                           'ndim': 2,
                           'numeric': False,
                           'parallel': [],
                           'version': 1}],
               'output': {'mode': 'declare',
                          'schema': {'dims': ['entry', 'statistic'], 'numeric': True}},
               'version': 1},
 'data_formats': {'inputs': [{'logical_type': 'form', 'metadata': {}, 'representations': ['form']},
                             {'logical_type': 'form', 'metadata': {}, 'representations': ['form']}],
                  'outputs': [{'logical_type': 'form',
                               'metadata': {},
                               'representations': ['form']}]},
 'description': 'Felsenstein pruning log-likelihood of an alignment on a fixed Newick tree under a '
                'general time-reversible model with fixed exchangeabilities and base frequencies.',
 'icon': 'Tree',
 'id': 'phylogenetics_gtr_likelihood',
 'inputs_arity': 2,
 'kind': 'operator',
 'output_parameter': 'output',
 'outputs': [],
 'protocol_revision': '3.7',
 'protocol_version': 3,
 'resources': {'estimate': 'estimate_memory', 'memory_modes': ['full'], 'supports_cuda': False},
 'title': 'GTR tree likelihood',
 'version': '1.0.0'}

    def run(self, ctx, inputs):
        from src.task.step.steps._phylo_common import parse_newick, tips

        tree_form, alignment = inputs
        tree_text = text_column(tree_form, tree_form.dims[1], str(ctx.step_params.get("tree_column", "newick")))[0]
        root = parse_newick(tree_text)
        leaves = [t.name for t in tips(root)]

        taxon_dim, site_dim = alignment.dims
        taxon_labels = (alignment.labels or {}).get(taxon_dim) or {}
        row_of = {name: int(index) for name, index in taxon_labels.items()}
        missing = [name for name in leaves if name not in row_of]
        if missing:
            raise StepError("tree taxa missing from alignment: %r" % missing)

        site_labels = (alignment.labels or {}).get(site_dim) or {}
        site_names = [name for name in sorted(site_labels, key=lambda k: int(site_labels[k]))]
        sequences = {name: [] for name in leaves}
        for site in site_names:
            column = encoded_column(alignment, site_dim, site)
            for name in leaves:
                sequences[name].append(column[row_of[name]])

        freqs = np.asarray([float(x) for x in str(ctx.step_params["base_freqs"]).split(",")], dtype=float)
        rates = [float(x) for x in str(ctx.step_params["rates"]).split(",")]
        if len(freqs) != 4 or abs(float(freqs.sum()) - 1.0) > 1e-6:
            raise StepError("base_freqs must be four probabilities")
        if len(rates) != 6 or min(rates) < 0:
            raise StepError("rates must be six non-negative values")
        q = np.zeros((4, 4), dtype=float)
        pairs = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]
        for value, (i, j) in zip(rates, pairs):
            q[i, j] = value
            q[j, i] = value
        codes = {"A": 0, "C": 1, "G": 2, "T": 3}
        n_sites = len(site_names)

        def partial(node, site):
            if not node.children:
                out = np.zeros(4, dtype=float)
                out[codes[sequences[node.name][site]]] = 1.0
                return out
            out = np.ones(4, dtype=float)
            for child in node.children:
                out *= transition(q, freqs, float(child.length)) @ partial(child, site)
            return out

        total = 0.0
        for site in range(n_sites):
            total += math.log(float(np.dot(freqs, partial(root, site))))

        names = ["log_likelihood", "n_taxa", "n_sites"]
        values = [round(float(total), 9), float(len(leaves)), float(n_sites)]
        out = Form(
            data=np.asarray(values, dtype=float).reshape(1, 3),
            dims=["entry", "statistic"],
            labels={"entry": {"gtr": 0},
                    "statistic": {"log_likelihood": 0, "n_taxa": 1, "n_sites": 2}},
            info={"columns": names},
        )
        ctx[ctx.step_params["output"]] = out
