"""Integrated haplotype score from biallelic haplotypes"""
import numpy as np
from src.core import Form
from src.task.step.base import Step
from src.task.step.steps._b55_common import numeric_column, row_names, string_column, table


class IhsSelectionStep(Step):
    parameters_file = "ihs_selection.IhsSelectionStep.parameters.json"

    definition = {
        "id": "ihs_selection",
        "version": "1.0.0",
        "title": "Integrated haplotype score from biallelic haplotypes",
        "description": "Integrated haplotype score from biallelic haplotypes",
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
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [
                        {
                            "param": "row_dim",
                            "default": "row"
                        },
                        {
                            "param": "field_dim",
                            "default": "field"
                        }
                    ],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2
                }
            ],
            "output": {
                "mode": "declare",
                "schema": {
                    "ndim": 2,
                    "numeric": True,
                    "info_open": True,
                    "axis_info_open": True
                }
            }
        },
        "data_formats": {
            "inputs": [
                {
                    "logical_type": "form",
                    "representations": [
                        "form"
                    ]
                }
            ],
            "outputs": [
                {
                    "logical_type": "form",
                    "representations": [
                        "form"
                    ]
                }
            ]
        },
        "resources": {
            "memory_modes": [
                "full"
            ],
            "supports_cuda": False,
            "estimate": "estimate_memory"
        }
    }

    def run(self, ctx, inputs):
        names = row_names(inputs[0])
        pos = numeric_column(inputs[0], inputs[0].dims[1], "pos")
        field = inputs[0].labels.get(inputs[0].dims[1], {})
        haps = [n for n in field if n.startswith("h") and n[1:].isdigit()]
        haps = sorted(haps, key=lambda n: int(n[1:]))
        if len(haps) < 4:
            raise ValueError("ihs_selection needs at least four haplotype columns")
        mat = np.column_stack([numeric_column(inputs[0], inputs[0].dims[1], h) for h in haps])
        mat = (mat > 0.5).astype(int)
        n = mat.shape[0]
        raw = []
        stats = []
        for i in range(n):
            if i == 0 or i == n - 1:
                raw.append(np.nan)
                stats.append([np.nan, np.nan, np.nan, 0.0, 0.0])
                continue
            vals = []
            for allele in (1, 0):
                sel = mat[i, :] == allele
                nh = int(sel.sum())
                if nh < 2:
                    vals.append(np.nan)
                    continue
                dists = [0.0]
                ehhs = [1.0]
                for j in range(i + 1, n):
                    pats = {}
                    for k in np.nonzero(sel)[0]:
                        key = tuple(mat[i:j + 1, k])
                        pats[key] = pats.get(key, 0) + 1
                    e = sum(c * (c - 1) for c in pats.values()) / (nh * (nh - 1))
                    dists.append(float(pos[j] - pos[i]))
                    ehhs.append(e)
                    if e < 0.05:
                        break
                vals.append(float(np.trapezoid(ehhs, dists)) if len(dists) > 1 else np.nan)
            ihh1, ihh0 = vals
            if np.isfinite(ihh1) and np.isfinite(ihh0) and ihh0 > 0 and ihh1 > 0:
                r = float(np.log(ihh1 / ihh0))
            else:
                r = np.nan
            raw.append(r)
            stats.append([ihh1, ihh0, r, float((mat[i, :] == 1).sum()), float((mat[i, :] == 0).sum())])
        arr = np.asarray([r for r in raw if np.isfinite(r)], dtype=float)
        if len(arr) > 1 and float(arr.std(ddof=0)) > 0:
            mean = float(arr.mean())
            sd = float(arr.std(ddof=0))
            z = [(r - mean) / sd if np.isfinite(r) else np.nan for r in raw]
        else:
            z = [np.nan for _ in raw]
        rows = []
        vals = []
        for i, name in enumerate(names):
            rows.append(name)
            vals.append([z[i], stats[i][2], stats[i][0], stats[i][1], stats[i][3], stats[i][4]])
        ctx[ctx.step_params["output"]] = table(
            rows, vals, ["ihs", "raw_ihs", "ihh1", "ihh0", "n_hap1", "n_hap0"])
        return None
