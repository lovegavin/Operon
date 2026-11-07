import numpy as np
from src.core import Form
from src.task.step.base import Step
from src.task.step.steps._b65_common import numeric, names, table, matrix, knn


class ScSpatialNeighborsStep(Step):
    parameters_file = "sc_spatial_neighbors.ScSpatialNeighborsStep.parameters.json"
    definition = {'id': 'sc_spatial_neighbors', 'version': '1.0.0', 'title': 'Spatial k-nearest-neighbour graph', 'description': 'Build a Gaussian-weighted spatial kNN graph from cell coordinates.', 'category': 'Single cell', 'icon': 'dna', 'kind': 'operator', 'protocol_version': 3, 'protocol_revision': '3.7', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'dims': ['row', 'field'], 'schema': {'type': 'object', 'additionalProperties': True}}], 'output': {'mode': 'declare', 'schema': {'type': 'object', 'additionalProperties': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form']}], 'outputs': [{'logical_type': 'form', 'representations': ['form']}]}}

    def run(self, ctx, inputs):
        form = inputs[0]
        field = form.dims[1]
        x = numeric(form, field, "x")
        y = numeric(form, field, "y")
        coords = np.column_stack([x, y])
        cells = names(form)
        idx, dist = knn(coords, ctx.step_params["k"])
        sigma = float(np.median(dist)) or 1.0
        w = np.exp(-(dist ** 2) / (2.0 * sigma ** 2))
        adj = np.zeros((len(cells), len(cells)))
        for i in range(len(cells)):
            adj[i, idx[i]] = w[i]
        adj = np.maximum(adj, adj.T)
        ctx[ctx.step_params["output"]] = matrix(cells, cells, adj)
