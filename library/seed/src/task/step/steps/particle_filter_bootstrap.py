"""Operator: Bootstrap particle filter."""

from __future__ import annotations

import numpy as np

from src.core import Form
from src.core.errors import StepError
from src.task.step.base import Step
from ._b86_common import matrix, table


class ParticleFilterBootstrapStep(Step):
    parameters_file = "particle_filter_bootstrap.ParticleFilterBootstrapStep.parameters.json"

    definition = {'id': 'particle_filter_bootstrap', 'version': '1.0.0', 'title': 'Bootstrap particle filter', 'description': 'Bootstrap particle filter for a local-level model with seeded resampling; reports the filtered mean, variance, effective sample size and log-likelihood.', 'category': 'Statistics', 'icon': 'activity', 'kind': 'operator', 'protocol_version': 3, 'protocol_revision': '3.7', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': []}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True}}}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'dependencies': ['numpy>=1.24']}

    def run(self, ctx, inputs):
        out_name = ctx.step_params["output"]
        params = ctx.step_params
        n_particles = ctx.step_params.get("n_particles", 200)
        process_var = ctx.step_params.get("process_var", 1.0)
        obs_var = ctx.step_params.get("obs_var", 1.0)
        seed = ctx.step_params.get("seed", 0)

        y = matrix(inputs[0]).reshape(-1)
        n = int(params["n_particles"]); q = float(params["process_var"]); r = float(params["obs_var"]); seed = int(params["seed"])
        rng = np.random.default_rng(seed)
        particles = rng.normal(y[0], 1.0, n)
        weights = np.full(n, 1.0 / n)
        means = np.zeros(y.size); vars_ = np.zeros(y.size); ess = np.zeros(y.size); loglik = 0.0
        for t in range(y.size):
            if t > 0:
                particles = particles + rng.normal(0.0, np.sqrt(q), n)
            w = weights * np.exp(-0.5 * (y[t] - particles) ** 2 / r)
            s = w.sum(); loglik += float(np.log(s)); w = w / s
            means[t] = float((w * particles).sum()); vars_[t] = float((w * (particles - means[t]) ** 2).sum())
            ess[t] = float(1.0 / (w ** 2).sum())
            if ess[t] < 0.5 * n:
                idx = rng.choice(n, size=n, p=w)
                particles = particles[idx]; weights = np.full(n, 1.0 / n)
            else:
                weights = w
        names = [f"t{i}" for i in range(y.size)]
        cols = {"observed": y, "filtered_mean": means, "filtered_var": vars_, "ess": ess}
        out = table(names, cols, list(cols))
        out.info["log_likelihood"] = round(loglik, 9)
        ctx[out_name] = out

