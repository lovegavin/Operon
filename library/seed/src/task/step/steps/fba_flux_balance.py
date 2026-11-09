"""Auto-generated b83 operator."""
import numpy as np

from src.core import Form
from src.core.errors import StepError
from src.task.step.base import Step

from ._b83_common import column, strings, table


class FbaFluxBalanceStep(Step):
    parameters_file = "fba_flux_balance.FbaFluxBalanceStep.parameters.json"

    definition = {'id': 'fba_flux_balance', 'version': '1.0.0', 'title': 'Flux balance analysis', 'description': 'Solve a steady-state flux balance linear program from a stoichiometric matrix and bounds.', 'category': 'Metabolic modelling', 'kind': 'operator', 'inputs_arity': 2, 'output_parameter': 'output', 'outputs': [], 'protocol_version': 3, 'protocol_revision': '3.7', 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}, {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}, 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': []}, {'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': []}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}}

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return (32 * 1024 * 1024, 0)

    def run(self, ctx, inputs):
        params = ctx.step_params
        stoich = inputs[0]
        bounds = inputs[1]
        S = np.asarray(stoich.data, dtype=float)
        if bounds.data.ndim != 2 or bounds.data.shape[0] != S.shape[1]:
            raise StepError("fba_flux_balance: bounds must have one row per reaction")
        low = column(bounds, 0)
        high = column(bounds, 1)
        if bounds.data.shape[1] >= 3:
            obj = column(bounds, 2)
        else:
            obj = np.zeros(S.shape[1])
        from scipy.optimize import linprog
        result = linprog(-obj, A_eq=S, b_eq=np.zeros(S.shape[0]), bounds=list(zip(low, high)), method="highs")
        names = [str(i) for i in range(S.shape[1])]
        labels = bounds.labels.get(bounds.dims[0]) or {}
        if labels:
            inv = {v: k for k, v in labels.items()}
            names = [str(inv.get(i, i)) for i in range(S.shape[1])]
        if not result.success:
            raise ValueError(f"flux balance did not converge: {result.message}")
        rows = [[float(f)] for f in result.x]
        rows.append([float(-result.fun)])
        names.append("objective")
        ctx[str(params.get("output", "output"))] = table(names, rows, ["flux"])

