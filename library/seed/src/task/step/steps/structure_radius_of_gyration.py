"""Radius of gyration and maximum atom radius of a PDB structure."""

from __future__ import annotations

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


def form_labels(form, dim):
    labels = (form.labels or {}).get(dim) or {}
    return [key for key, _ in sorted(labels.items(), key=lambda item: int(item[1]))]


def result(dims, labels, rows, info=None):
    out = Form(data=np.round(np.asarray(rows, dtype=np.float64), 9), dims=list(dims),
               labels=labels, info=dict(info or {}))
    out.validate()
    return out


class StructureRadiusOfGyrationStep(Step):
    parameters_file = "structure_radius_of_gyration.StructureRadiusOfGyrationStep.parameters.json"

    definition = {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "structure_radius_of_gyration",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Radius of gyration",
        "description": "Radius of gyration and maximum atom radius of a PDB structure.",
        "category": "Structure",
        "icon": "Ruler",
        "inputs_arity": 1,
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
                        {"param": "atom_dim", "default": "atom"},
                        {"param": "field_dim", "default": "field"},
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
            "inputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
            "outputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
        },
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return (32 * 1024 * 1024, 0)

    def run(self, ctx, inputs):
        params = ctx.step_params
        atom_dim = str(params.get("atom_dim", "atom"))
        field_dim = str(params.get("field_dim", "field"))
        out_name = str(params.get("output", "rg"))
        form = inputs[0]
        if list(form.dims) != [atom_dim, field_dim]:
            raise StepError(
                "structure_radius_of_gyration: expected dims [{}, {}], got {}".format(
                    atom_dim, field_dim, list(form.dims)))
        coords = np.column_stack([
            numeric_column(form, field_dim, "x"),
            numeric_column(form, field_dim, "y"),
            numeric_column(form, field_dim, "z"),
        ])
        centre = coords.mean(axis=0)
        sq = np.sum((coords - centre) ** 2, axis=1)
        rg = float(np.sqrt(np.mean(sq)))
        rows = [[float(coords.shape[0]), rg, float(np.sqrt(np.max(sq)))]]
        labels = {"entry": {"rg": 0}, "statistic": {"n_atoms": 0, "radius_of_gyration": 1, "max_radius": 2}}
        ctx[out_name] = result(["entry", "statistic"], labels, rows, {"method": "mean_squared_distance"})
