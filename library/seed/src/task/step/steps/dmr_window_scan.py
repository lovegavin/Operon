from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.step.base import Step
from src.task.step.steps._meth_common import numeric_column, probe_form


class DmrWindowScanStep(Step):
    definition = {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "dmr_window_scan",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Differentially methylated window scan",
        "category": "Epigenomics",
        "description": "Scan fixed-width windows for mean beta difference and Welch t statistic.",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "numeric": False,
                    "dims": [
                        {"param": "probe_dim", "default": "probe"},
                        {"param": "field_dim", "default": "field"},
                    ],
                    "labels": [],
                    "parallel": [],
                }
            ],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}},
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"},
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
            "outputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
        },
    }
    parameters_file = "dmr_window_scan.DmrWindowScanStep.parameters.json"

    def run(self, ctx, inputs):
        p = ctx.step_params
        out_name = str(p.get("output") or "output")
        probe_dim = str(p.get("probe_dim") or "probe")
        field_dim = str(p.get("field_dim") or "field")
        chrom = [str(int(v)) for v in numeric_column(inputs[0], field_dim, "chrom")]
        pos = numeric_column(inputs[0], field_dim, "pos")
        m1 = numeric_column(inputs[0], field_dim, "group1_methylated")
        u1 = numeric_column(inputs[0], field_dim, "group1_unmethylated")
        m2 = numeric_column(inputs[0], field_dim, "group2_methylated")
        u2 = numeric_column(inputs[0], field_dim, "group2_unmethylated")
        beta1 = m1 / np.maximum(m1 + u1, 1.0)
        beta2 = m2 / np.maximum(m2 + u2, 1.0)
        delta = beta1 - beta2
        window = float(p.get("window_bp", 1000))
        min_probes = int(p.get("min_probes", 3))
        rows = []
        for c in sorted(set(chrom)):
            idx = np.array([i for i, value in enumerate(chrom) if value == c])
            if idx.size == 0:
                continue
            order = idx[np.argsort(pos[idx])]
            start = float(pos[order[0]])
            while start <= float(pos[order[-1]]):
                sel = order[(pos[order] >= start) & (pos[order] < start + window)]
                if sel.size >= min_probes:
                    d = delta[sel]
                    d = d[np.isfinite(d)]
                    if d.size >= min_probes:
                        mean = float(d.mean())
                        sd = float(d.std(ddof=1))
                        t = mean / (sd / np.sqrt(d.size)) if sd > 0 else 0.0
                        rows.append((start, start + window, d.size, mean, t))
                start += window
        if not rows:
            raise StepError("dmr_window_scan: no window has enough finite probes")
        arr = np.array(rows, dtype=float)
        labels = {"window": {f"w{i}": i for i in range(len(rows))},
                  "statistic": {"start": 0, "end": 1, "n_probes": 2, "mean_delta": 3, "t_stat": 4}}
        from src.core import Form
        ctx[out_name] = Form(data=arr, dims=["window", "statistic"], labels=labels,
                             info={"missing_code": np.nan, "window_bp": window})
