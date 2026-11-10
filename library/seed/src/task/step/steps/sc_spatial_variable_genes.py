import math

import numpy as np
from src.core import Form
from src.core.errors import StepError
from src.task.step.base import Step
from src.task.step.steps._b65_common import numeric, names, table, matrix, knn


class ScSpatialVariableGenesStep(Step):
    parameters_file = "sc_spatial_variable_genes.ScSpatialVariableGenesStep.parameters.json"
    definition = {'id': 'sc_spatial_variable_genes', 'version': '1.0.0', 'title': "Spatially variable genes (Moran's I)", 'description': "Score each gene with Moran's I on a spatial kNN graph.", 'category': 'Single cell', 'icon': 'dna', 'kind': 'operator', 'protocol_version': 3, 'protocol_revision': '3.7', 'inputs_arity': 2, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'dims': ['row', 'field'], 'schema': {'type': 'object', 'additionalProperties': True}}, {'dims': ['row', 'field'], 'schema': {'type': 'object', 'additionalProperties': True}}], 'output': {'mode': 'declare', 'schema': {'type': 'object', 'additionalProperties': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form']}, {'logical_type': 'form', 'representations': ['form']}], 'outputs': [{'logical_type': 'form', 'representations': ['form']}]}}

    def run(self, ctx, inputs):
        counts = inputs[0]
        coords_form = inputs[1]
        genes = names(counts)
        cells = names(coords_form)
        cf = coords_form.dims[1]
        xy = np.column_stack([numeric(coords_form, cf, "x"), numeric(coords_form, cf, "y")])
        k = int(ctx.step_params["k"])
        idx, dist = knn(xy, k)
        n = len(cells)
        if counts.data.shape[1] != n:
            raise StepError("sc_spatial_variable_genes: counts must have one column per spatial cell")
        sigma = float(np.median(dist)) or 1.0
        adj = np.zeros((n, n))
        for i in range(n):
            adj[i, idx[i]] = np.exp(-(dist[i] ** 2) / (2.0 * sigma ** 2))
        adj = np.maximum(adj, adj.T)
        wsum = float(adj.sum())
        rows = []
        for g in range(counts.data.shape[0]):
            z = np.asarray(counts.data[g, :], dtype=float)
            z = z - z.mean()
            denom = float((z ** 2).sum())
            if denom <= 0:
                rows.append([0.0, 0.0, 1.0])
                continue
            num = float(z @ adj @ z)
            i_moran = (n / wsum) * (num / denom)
            z_score = (i_moran + 1.0 / (n - 1)) / np.sqrt(2.0 / (n - 1)) if n > 2 else 0.0
            p_value = math.erfc(abs(z_score) / math.sqrt(2.0))
            rows.append([i_moran, z_score, p_value])
        ctx[ctx.step_params["output"]] = table(genes, rows, ["moran_i", "z_score", "p_value"])
