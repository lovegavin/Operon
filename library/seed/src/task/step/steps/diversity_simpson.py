"""Simpson diversity and derived richness statistics for abundance vectors."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.task.step.base import Step

from ._b81_common import table

STATISTICS = ("simpson", "inverse_simpson", "evenness", "richness")


def simpson_summary(values) -> dict:
    """Return Simpson diversity, inverse Simpson, evenness and richness."""
    finite = np.asarray(values, dtype=np.float64).ravel()
    finite = finite[np.isfinite(finite)]
    if finite.size and float(finite.min()) < 0.0:
        raise StepError("diversity_simpson: abundances must be non-negative")
    richness = int(np.count_nonzero(finite > 0.0))
    total = float(finite.sum()) if finite.size else 0.0
    if total <= 0.0 or richness == 0:
        return {"simpson": 0.0, "inverse_simpson": 0.0, "evenness": 0.0, "richness": 0.0}
    proportions = finite / total
    simpson = float(np.sum(proportions ** 2))
    inverse = 1.0 / simpson
    evenness = inverse / richness
    return {
        "simpson": simpson,
        "inverse_simpson": inverse,
        "evenness": evenness,
        "richness": float(richness),
    }


class DiversitySimpsonStep(Step):
    provider = "operon-core"
    parameters_file = "diversity_simpson.DiversitySimpsonStep.parameters.json"

    definition = {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "diversity_simpson",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Simpson diversity",
        "description": "Computes Simpson diversity, inverse Simpson, evenness and richness of an abundance vector.",
        "category": "Population genetics",
        "icon": "Dna",
        "inputs_arity": 1,
        "output_parameter": "output",
        "outputs": [],
        "contracts": {
            "version": 1,
            "inputs": [{
                "version": 1,
                "numeric": True,
                "ndim": 1,
                "dims": [{"param": "abundance_dim", "default": "abundance"}],
                "labels": [],
                "parallel": [],
            }],
            "output": {
                "mode": "declare",
                "schema": {
                    "ndim": 2,
                    "numeric": True,
                    "info_open": True,
                    "axis_info_open": True,
                },
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

    def run(self, ctx, inputs) -> None:
        if not inputs:
            raise StepError("diversity_simpson: an abundance vector input is required")
        form = inputs[0]
        params = ctx.step_params
        abundance_dim = str(params.get("abundance_dim") or "abundance")
        out_name = str(params.get("output") or "simpson_diversity")

        if form.data.ndim != 1 or list(form.dims) != [abundance_dim]:
            raise StepError(
                "diversity_simpson: a 1-D abundance form with dims "
                f"[{abundance_dim}] is required, got {list(form.dims)}"
            )

        summary = simpson_summary(form.data)
        ctx[out_name] = table(
            ["simpson"],
            [[summary["simpson"], summary["inverse_simpson"], summary["evenness"], summary["richness"]]],
            list(STATISTICS),
        )
