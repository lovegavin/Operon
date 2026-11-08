"""Codon adaptation index of coding sequences against caller-supplied relative adaptiveness weights."""

from __future__ import annotations

import math

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step


def field_index(form, dim, name):
    labels = (form.labels or {}).get(dim) or {}
    if name not in labels:
        raise StepError("missing column %r in dimension %r" % (name, dim))
    return int(labels[name])


def numeric_column(form, dim, name):
    return np.asarray(form.data[:, field_index(form, dim, name)], dtype=np.float64)


def _decode(form, dim, name):
    column = np.asarray(form.data[:, field_index(form, dim, name)])
    encoders = ((form.info or {}).get("encoders") or {}).get(dim) or {}
    spec = encoders.get(name)
    if spec is None:
        return [str(int(value)) if float(value).is_integer() else str(value) for value in column]
    inverse = getattr(spec, "inverse_transform", None)
    if callable(inverse):
        return [str(value) for value in inverse(column.astype(int))]
    mapping = getattr(spec, "inverse", None)
    if isinstance(mapping, dict):
        return [str(mapping[int(value)]) for value in column]
    if callable(mapping):
        return [str(value) for value in mapping(column.astype(int))]
    classes = getattr(spec, "classes_", None)
    if classes is not None:
        return [str(classes[int(value)]) for value in column]
    raise StepError("cannot decode column %r" % name)


def strings(form, dim, name):
    return _decode(form, dim, name)


def form_labels(form, dim):
    labels = (form.labels or {}).get(dim) or {}
    return [key for key, _ in sorted(labels.items(), key=lambda item: int(item[1]))]


def result(dims, labels, rows, info=None):
    out = Form(data=np.round(np.asarray(rows, dtype=np.float64), 9), dims=list(dims),
               labels=labels, info=dict(info or {}))
    out.validate()
    return out


class SequenceCaiStep(Step):
    parameters_file = "sequence_cai.SequenceCaiStep.parameters.json"

    definition = {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "sequence_cai",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Codon adaptation index",
        "description": "Codon adaptation index of coding sequences against caller-supplied relative adaptiveness weights.",
        "category": "Sequence",
        "icon": "Ruler",
        "inputs_arity": 2,
        "output_parameter": "output",
        "outputs": [],
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "ndim": 2,
                    "dims": [
                        {"param": "seq_dim", "default": "seq"},
                        {"param": "field_dim", "default": "field"}
                    ],
                    "labels": [],
                    "parallel": [],
                },
                {
                    "version": 1,
                    "numeric": True,
                    "ndim": 2,
                    "dims": [
                        {"param": "codon_dim", "default": "codon"},
                        {"param": "field_dim", "default": "field"}
                    ],
                    "labels": [],
                    "parallel": [],
                }
            ],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
            },
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": [],
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}, {"logical_type": "form", "representations": ["form"], "metadata": {}}],
            "outputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
        },
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return (32 * 1024 * 1024, 0)

    STOP = {"TAA", "TAG", "TGA"}

    def run(self, ctx, inputs):
        params = ctx.step_params
        seq_dim = str(params.get("seq_dim", "seq"))
        codon_dim = str(params.get("codon_dim", "codon"))
        field_dim = str(params.get("field_dim", "field"))
        out_name = str(params.get("output", "cai"))
        seqs_form, weights_form = inputs
        if list(seqs_form.dims) != [seq_dim, field_dim]:
            raise StepError("sequence_cai: unexpected sequence dims %s" % (list(seqs_form.dims),))
        if list(weights_form.dims) != [codon_dim, field_dim]:
            raise StepError("sequence_cai: unexpected weight dims %s" % (list(weights_form.dims),))
        names = form_labels(seqs_form, seq_dim)
        sequences = strings(seqs_form, field_dim, "seq")
        codons = strings(weights_form, field_dim, "codon")
        weights = numeric_column(weights_form, field_dim, "w")
        table = {}
        for codon, weight in zip(codons, weights):
            table[str(codon).upper().replace("U", "T")] = float(weight)
        rows = []
        for name, sequence in zip(names, sequences):
            text = str(sequence).upper().replace("U", "T")
            used = []
            for start in range(0, len(text) - 2, 3):
                codon = text[start:start + 3]
                if codon in self.STOP:
                    continue
                weight = table.get(codon)
                if weight is None or weight <= 0.0:
                    raise StepError("sequence_cai: no positive weight for codon %r" % codon)
                used.append(weight)
            if not used:
                rows.append([0.0, 0.0, float("nan")])
            else:
                cai = math.exp(sum(math.log(value) for value in used) / len(used))
                rows.append([float(len(text) // 3), float(len(used)), cai])
        labels = {"sequence": {name: idx for idx, name in enumerate(names)},
                  "statistic": {"n_codons": 0, "n_effective": 1, "cai": 2}}
        ctx[out_name] = result(["sequence", "statistic"], labels, rows, {"method": "cai"})
