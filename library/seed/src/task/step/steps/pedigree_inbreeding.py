"""Inbreeding coefficients from a numeric pedigree"""
import numpy as np
from src.core import Form
from src.task.step.base import Step
from src.task.step.steps._b75b_common import numeric, result_form, row_names


class PedigreeInbreedingStep(Step):
    parameters_file = "pedigree_inbreeding.PedigreeInbreedingStep.parameters.json"

    definition = {
        "id": "pedigree_inbreeding",
        "version": "1.0.0",
        "title": "Inbreeding coefficients from a numeric pedigree",
        "description": "Inbreeding coefficients from a numeric pedigree",
        "category": "Population genetics",
        "icon": "Table",
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "kind": "operator",
        "inputs_arity": 1,
        "output_parameter": "output",
        "outputs": [],
        "contracts": {
            "version": 1,
            "inputs": [{
                "version": 1,
                "numeric": True,
                "dims": [
                    {"param": "row_dim", "default": "individual"},
                    {"param": "field_dim", "default": "field"}
                ],
                "labels": [],
                "parallel": [],
                "ndim": 2
            }],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}
        },
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"]}],
            "outputs": [{"logical_type": "form", "representations": ["form"]}]
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"}
    }

    def run(self, ctx, inputs):
        names = row_names(inputs[0], "individual")
        sires = numeric(inputs[0], "individual", "sire_index").astype(int)
        dams = numeric(inputs[0], "individual", "dam_index").astype(int)
        parents = [(int(s) if s >= 0 else None, int(d) if d >= 0 else None) for s, d in zip(sires, dams)]
        kin = {}

        def inbreeding(i):
            si, di = parents[i]
            if si is None or di is None:
                return 0.0
            return kinship(si, di)

        def kinship(i, j):
            if i == j:
                return 0.5 * (1.0 + inbreeding(i))
            key = tuple(sorted((i, j)))
            if key in kin:
                return kin[key]
            si, di = parents[i]
            sj, dj = parents[j]
            if si is None and di is None:
                kin[key] = 0.0 if (sj is None and dj is None) else kinship(j, i)
                return kin[key]
            vals = []
            if si is not None:
                vals.append(kinship(si, j))
            if di is not None:
                vals.append(kinship(di, j))
            val = 0.5 * sum(vals) if vals else 0.0
            kin[key] = val
            return val

        f = np.array([inbreeding(i) for i in range(len(names))])
        n_known = np.array([sum(p is not None for p in parents[i]) for i in range(len(names))], dtype=float)
        ctx[ctx.step_params["output"]] = result_form(
            names, ["inbreeding", "n_parents_known"], np.column_stack([f, n_known]))
        return None

