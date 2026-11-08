"""Operator: Baum-Welch HMM training."""

from __future__ import annotations

import numpy as np

from src.core import Form
from src.core.errors import StepError
from src.task.step.base import Step
from ._b86_common import matrix, table


class HmmBaumWelchStep(Step):
    parameters_file = "hmm_baum_welch.HmmBaumWelchStep.parameters.json"

    definition = {'id': 'hmm_baum_welch', 'version': '1.0.0', 'title': 'Baum-Welch HMM training', 'description': 'Fit a discrete hidden Markov model with scaled Baum-Welch EM and report the final log-likelihood, iteration count and transition/emission matrices.', 'category': 'Statistics', 'icon': 'activity', 'kind': 'operator', 'protocol_version': 3, 'protocol_revision': '3.7', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': []}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True}}}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'dependencies': ['numpy>=1.24']}

    def run(self, ctx, inputs):
        out_name = ctx.step_params["output"]
        params = ctx.step_params
        n_states = ctx.step_params.get("n_states", 2)
        n_iter = ctx.step_params.get("n_iter", 100)
        tol = ctx.step_params.get("tol", 1e-06)
        seed = ctx.step_params.get("seed", 0)

        obs = matrix(inputs[0]).reshape(-1).astype(int)
        n_states = int(params["n_states"]); n_iter = int(params["n_iter"])
        tol = float(params["tol"]); seed = int(params["seed"])
        n_obs = int(obs.max()) + 1 if obs.size else 1
        rng = np.random.default_rng(seed)
        trans = rng.random((n_states, n_states)) + 1.0
        trans = trans / trans.sum(axis=1, keepdims=True)
        emit = rng.random((n_states, n_obs)) + 1.0
        emit = emit / emit.sum(axis=1, keepdims=True)
        init = np.full(n_states, 1.0 / n_states)
        last = -np.inf; converged = 0.0
        ll = 0.0
        for it in range(1, n_iter + 1):
            alpha = np.zeros((obs.size, n_states)); scale = np.zeros(obs.size)
            alpha[0] = init * emit[:, obs[0]]; scale[0] = alpha[0].sum(); alpha[0] /= scale[0]
            for t in range(1, obs.size):
                alpha[t] = (alpha[t - 1] @ trans) * emit[:, obs[t]]
                scale[t] = alpha[t].sum(); alpha[t] /= scale[t]
            ll = float(np.log(scale).sum())
            beta = np.zeros_like(alpha); beta[-1] = 1.0
            for t in range(obs.size - 2, -1, -1):
                beta[t] = (trans @ (emit[:, obs[t + 1]] * beta[t + 1])) / scale[t + 1]
            gamma = alpha * beta; gamma /= gamma.sum(axis=1, keepdims=True)
            xi_sum = np.zeros((n_states, n_states))
            for t in range(obs.size - 1):
                xi = (alpha[t][:, None] * trans) * (emit[:, obs[t + 1]] * beta[t + 1])[None, :]
                xi_sum += xi / xi.sum()
            init = gamma[0] / gamma[0].sum()
            trans = xi_sum / xi_sum.sum(axis=1, keepdims=True)
            new_emit = np.zeros_like(emit)
            for k in range(n_obs):
                new_emit[:, k] = gamma[obs == k].sum(axis=0)
            emit = new_emit / new_emit.sum(axis=1, keepdims=True)
            if abs(ll - last) < tol:
                converged = 1.0
                break
            last = ll
        names = ["log_likelihood", "n_iter", "converged", "n_states", "n_observations"]
        vals = {"log_likelihood": [ll], "n_iter": [it], "converged": [converged], "n_states": [n_states], "n_observations": [obs.size]}
        out = table(["hmm"], vals, names)
        out.info["transition"] = np.round(trans, 9).tolist()
        out.info["emission"] = np.round(emit, 9).tolist()
        ctx[out_name] = out

