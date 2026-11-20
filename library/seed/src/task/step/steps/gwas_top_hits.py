"""Lead variants from a GWAS association table with distance-based clumping."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.step.base import Step

from ._gwas_utils import association_rows, clump


DEFAULTS = {'threshold': 5e-08, 'clump_distance': 1000000, 'max_hits': 0, 'variant_dim': 'variant', 'statistic_dim': 'statistic', 'output': 'hits'}


def variant_position(label, operator: str = "gwas_top_hits") -> tuple:
    """Split a ``chrom:position`` variant label, raising a readable ValueError."""
    chromosome, _, remainder = str(label).strip().partition(":")
    position_text = remainder.partition(":")[0].strip()
    try:
        position = int(position_text)
    except (TypeError, ValueError):
        position = None
    if not chromosome.strip() or position is None:
        raise ValueError(
            f"{operator}: variant label {label!r} does not name a chromosome and a position; "
            "the top-hit clumping step needs both for every variant. Label each variant "
            "'<chrom>:<position>[:<ref>:<alt>]' such as '22:16050075:A:G', or start from an "
            "association table whose variant labels already include them."
        )
    return chromosome.strip(), position


class GwasTopHitsStep(Step):
    parameters_file = "gwas_top_hits.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "gwas_top_hits",
        "version": "1.0.0",
        "kind": "operator",
        "title": "GWAS top hits",
        "description": "Select independent lead variants below a p-value threshold using distance-based clumping.",
        "category": "Statistics",
        "icon": "Target",
        "inputs_arity": 1,
        "output_parameter": "output",
        "outputs": [],
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "name": "association",
                    "numeric": True,
                    "ndim": 2,
                    "dims": [
                        {"param": "variant_dim", "default": "variant"},
                        {"param": "statistic_dim", "default": "statistic"},
                    ],
                    "labels": [],
                    "parallel": [],
                    "description": "Association table with p, beta and se columns.",
                }
            ],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
            },
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False},
    }

    parameters = [
        {"name": "threshold", "type": "number", "default": 5e-8, "minimum": 0.0, "maximum": 1.0},
        {"name": "clump_distance", "type": "integer", "default": 1000000, "minimum": 0},
        {"name": "max_hits", "type": "integer", "default": 0, "minimum": 0},
        {"name": "variant_dim", "type": "string", "default": "variant"},
        {"name": "statistic_dim", "type": "string", "default": "statistic"},
        {"name": "output", "type": "string", "default": "hits"},
    ]

    def run(self, ctx, inputs):
        params = {**DEFAULTS, **dict(ctx.step_params or {})}
        rows = association_rows(
            inputs[0], params["variant_dim"], params["statistic_dim"], "gwas_top_hits"
        )
        for row in rows:
            row["chrom"], row["pos"] = variant_position(row["variant"])
        hits = clump(
            rows,
            float(params["threshold"]),
            int(params["clump_distance"]),
            int(params["max_hits"]),
        )
        statistics = ("p", "beta", "se")
        data = np.asarray([[row[key] for key in statistics] for row in hits], dtype=float)
        labels = {
            "variant": {row["variant"]: index for index, row in enumerate(hits)},
            "statistic": {name: index for index, name in enumerate(statistics)},
        }
        info = {
            "threshold": float(params["threshold"]),
            "clump_distance": int(params["clump_distance"]),
            "n_tested": len(rows),
            "n_hits": len(hits),
        }
        if not hits:
            raise StepError(
                f"gwas_top_hits: no variant passed threshold {params['threshold']}"
            )
        ctx[params["output"]] = Form(
            data, dims=["variant", "statistic"], labels=labels, info=info
        )
        self._export = {
            "n_hits": len(hits),
            "n_tested": len(rows),
            "threshold": float(params["threshold"]),
        }

    def export(self, ctx):
        return dict(self._export)
