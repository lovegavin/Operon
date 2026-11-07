"""Definition for the pangenome_matrix operator."""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.step.base import Step
from ._b59_common import numeric, strings, row_form


class PangenomeMatrixStep(Step):
    definition = {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "pangenome_matrix",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Pangenome core and accessory summary",
        "category": "Metagenomics",
        "description": "Pangenome core and accessory summary.",
        "inputs_arity": 1,
        "output_parameter": "output",
        "outputs": [],
        "contracts": {
            "version": 1,
            "inputs": [{"version": 1, "dims": [{"param": "row_dim", "default": "row"}, {"param": "field_dim", "default": "field"}], "numeric": False, "ndim": 2}],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True}},
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"},
        "data_formats": {"inputs": [{"logical_type": "form", "representations": ["form"]}], "outputs": [{"logical_type": "form", "representations": ["form"]}]},
    }
    parameters_file = "pangenome_matrix.PangenomeMatrixStep.parameters.json"

    def run(self, ctx, inputs):

        form = inputs[0]
        genes = numeric(form, "field", "gene_index", "pangenome")
        present = numeric(form, "field", "present", "pangenome")
        genomes = int(ctx.step_params.get("genomes", 0))
        if genomes <= 0:
            genomes = int(np.max(numeric(form, "field", "genome_index", "pangenome"))) + 1
        n_genes = int(np.max(genes)) + 1
        counts = np.zeros(n_genes)
        for g, pr in zip(genes, present):
            if pr:
                counts[int(g)] += 1
        core = int(np.sum(counts == genomes)); acc = int(np.sum(counts > 0)) - core
        uniq = int(np.sum(counts == 1))
        total = int(np.sum(counts > 0))
        rows = [[core, acc, uniq, total, core / max(1, total), acc / max(1, total)]]
        out = row_form(["core_genes", "accessory_genes", "unique_genes", "pangenome_genes",
                        "core_fraction", "accessory_fraction"], rows, "summary", {"all": 0})

        out.validate()
        ctx[ctx.step_params.get("output", "output")] = out

    def export(self, ctx):
        name = ctx.step_params.get("output", "output")
        f = ctx[name]
        return {"result_files": [], "output": name, "dims": [str(d) for d in f.dims],
                 "rows": int(f.data.shape[0]), "columns": [str(x) for x in f.labels.get("statistic", [])]}
