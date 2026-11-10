"""Distance-to-TSS bin enrichment"""
import numpy as np
from src.core import Form
from src.task.step.base import Step
from src.task.step.steps._b62_common import names, numeric, strings, table


class PeakTssEnrichmentStep(Step):
    parameters_file = "peak_tss_enrichment.PeakTssEnrichmentStep.parameters.json"

    definition = {
    "id": "peak_tss_enrichment",
    "version": "1.0.0",
    "title": "Distance-to-TSS bin enrichment",
    "description": "Distance-to-TSS bin enrichment",
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
        pchrom = strings(peaks, peaks.dims[1], "chrom")
        pstart = numeric(peaks, peaks.dims[1], "start")
        pend = numeric(peaks, peaks.dims[1], "end")
        gchrom = strings(genes, genes.dims[1], "chrom")
        gtss = numeric(genes, genes.dims[1], "tss")
        width = float(ctx.step_params.get("bin_width", 1000))
        nbins = int(ctx.step_params.get("n_bins", 10))
        counts = np.zeros(nbins, dtype=float)
        total = 0
        for i in range(len(pstart)):
            mid = 0.5 * (pstart[i] + pend[i])
            ds = [abs(gtss[j] - mid) for j in range(len(gtss)) if gchrom[j] == pchrom[i]]
            if not ds:
                continue
            total += 1
            k = min(nbins - 1, int(min(ds) // width))
            counts[k] += 1
        rows = [[k * width, counts[k], counts[k] / total if total else 0.0] for k in range(nbins)]
        out = table(["bin%d" % k for k in range(nbins)], rows, ["bin_start", "count", "fraction"])
        out.info["total_peaks"] = total
        ctx[ctx.step_params["output"]] = out

