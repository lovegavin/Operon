"""Annotate peaks with the nearest same-chromosome gene"""
import numpy as np
from src.core import Form
from src.task.step.base import Step
from src.task.step.steps._b62_common import names, numeric, strings, table


class PeakAnnotateStep(Step):
    parameters_file = "peak_annotate.PeakAnnotateStep.parameters.json"

    definition = {
    "id": "peak_annotate",
    "version": "1.0.0",
    "title": "Annotate peaks with the nearest same-chromosome gene",
    "description": "Annotate peaks with the nearest same-chromosome gene",
    "category": "Epigenomics",
    "icon": "epigenomics",
    "kind": "operator",
    "protocol_version": 3,
    "protocol_revision": "3.7",
    "inputs_arity": 2,
    "outputs": [],
    "output_parameter": "output",
    "contracts": {
        "version": 1,
        "inputs": [
            {
                "name": "in1",
                "dims": [
                    "row",
                    "field"
                ]
            },
            {
                "name": "in2",
                "dims": [
                    "row",
                    "field"
                ]
            }
        ],
        "output": {
            "mode": "declare",
            "schema": {
                "dims": [
                    "row",
                    "statistic"
                ],
                "logical_type": "form",
                "representations": [
                    "form"
                ]
            }
        }
    },
    "resources": {
        "memory_modes": [
            "full"
        ],
        "supports_cuda": False,
        "estimate": "estimate_memory"
    },
    "data_formats": {
        "inputs": [
            {
                "logical_type": "form",
                "representations": [
                    "form"
                ]
            },
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
    }
}

    def run(self, ctx, inputs):

        peaks, genes = inputs
        pnames = names(peaks)
        pchrom = strings(peaks, peaks.dims[1], "chrom")
        pstart = numeric(peaks, peaks.dims[1], "start")
        pend = numeric(peaks, peaks.dims[1], "end")
        gchrom = strings(genes, genes.dims[1], "chrom")
        gtss = numeric(genes, genes.dims[1], "tss")
        rows = []
        for i, name in enumerate(pnames):
            mid = 0.5 * (pstart[i] + pend[i])
            best, bestd = -1, float("inf")
            for j, gc in enumerate(gchrom):
                if gc != pchrom[i]:
                    continue
                d = abs(gtss[j] - mid)
                if d < bestd:
                    best, bestd = j, d
            signed = (gtss[best] - mid) if best >= 0 else float("nan")
            rows.append([best, signed, bestd if best >= 0 else float("nan"),
                         sum(1 for gc in gchrom if gc == pchrom[i])])
        out = table(pnames, rows, ["nearest_gene_index", "distance", "abs_distance", "n_same_chrom"])
        ctx[ctx.step_params["output"]] = out

