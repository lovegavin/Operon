import numpy as np
from src.core import Form
from src.task.step.base import Step
from src.task.step.steps._b65_common import numeric, names, table, matrix, knn


class ScSpatialDomainsStep(Step):
    parameters_file = "sc_spatial_domains.ScSpatialDomainsStep.parameters.json"
    definition = {'id': 'sc_spatial_domains', 'version': '1.0.0', 'title': 'Spatial domain assignment', 'description': 'Assign spatial domains by k-means on coordinates and report neighbour purity.', 'category': 'Single cell', 'icon': 'dna', 'kind': 'operator', 'protocol_version': 3, 'protocol_revision': '3.7', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'dims': ['row', 'field'], 'schema': {'type': 'object', 'additionalProperties': True}}], 'output': {'mode': 'declare', 'schema': {'type': 'object', 'additionalProperties': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form']}], 'outputs': [{'logical_type': 'form', 'representations': ['form']}]}}

    def run(self, ctx, inputs):
        form = inputs[0]
        field = form.dims[1]
        coords = np.column_stack([numeric(form, field, "x"), numeric(form, field, "y")])
        cells = names(form)
        n = len(cells)
        k = int(ctx.step_params["k"])
        k = max(1, min(k, n - 1))
        nc = max(1, min(int(ctx.step_params["n_domains"]), n))
        idx, _ = knn(coords, k)
        centers = [coords[0]]
        for _ in range(nc - 1):
            dmin = np.min([((coords - c) ** 2).sum(axis=1) for c in centers], axis=0)
            centers.append(coords[int(np.argmax(dmin))])
        centers = np.asarray(centers)
        labels = np.zeros(n, dtype=int)
        for _ in range(int(ctx.step_params["iterations"])):
            d2 = ((coords[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
            new = np.argmin(d2, axis=1)
            if np.array_equal(new, labels):
                break
            labels = new
            for j in range(nc):
                members = coords[labels == j]
                if len(members):
                    centers[j] = members.mean(axis=0)
        neigh = np.zeros(n, dtype=float)
        for i in range(n):
            neigh[i] = np.mean(labels[idx[i]] == labels[i])
        ctx[ctx.step_params["output"]] = table(cells, np.column_stack([labels, neigh]),
                                              ["domain", "neighbor_purity"])
