"""Viterbi decoding for a discrete hidden Markov model"""

from __future__ import annotations

import math

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step

from ._b82_common import column, row_names, table


class HiddenMarkovViterbiStep(Step):
    parameters_file = "hidden_markov_viterbi.HiddenMarkovViterbiStep.parameters.json"

    definition = {'protocol_version': 3, 'protocol_revision': '3.7', 'id': 'hidden_markov_viterbi', 'version': '1.0.0', 'kind': 'operator', 'title': 'Viterbi decoding for a discrete hidden Markov model', 'description': 'Most probable hidden state path for a discrete-emission HMM.', 'category': 'Machine Learning', 'icon': 'ChartLine', 'inputs_arity': 3, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': []}, {'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': []}, {'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': []}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'dependencies': ['numpy>=1.24'], 'dependency_imports': [], 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}, {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}, {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}}

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return (32 * 1024 * 1024, 0)

    def run(self, ctx, inputs):
        params = ctx.step_params
        obs_form, trans_form, emit_form = inputs[0], inputs[1], inputs[2]
        obs = column(obs_form, obs_form.data.shape[1] - 1).astype(int)
        trans = np.asarray(trans_form.data, dtype=np.float64)
        emit = np.asarray(emit_form.data, dtype=np.float64)
        if trans.ndim != 2 or trans.shape[0] != trans.shape[1]:
            raise StepError("transition table must be square")
        states = trans.shape[0]
        if emit.ndim != 2 or emit.shape[0] != states:
            raise StepError("emission table must have one row per state")
        log_trans = np.log(np.clip(trans, 1e-12, None))
        log_emit = np.log(np.clip(emit, 1e-12, None))
        log_start = np.full(states, -math.log(states))
        n = int(obs.size)
        delta = log_start + log_emit[:, obs[0]]
        back = np.zeros((n, states), dtype=int)
        for t in range(1, n):
            candidates = delta[:, None] + log_trans
            back[t] = np.argmax(candidates, axis=0)
            delta = candidates[back[t], np.arange(states)] + log_emit[:, obs[t]]
        path = np.zeros(n, dtype=int)
        path[-1] = int(np.argmax(delta))
        for t in range(n - 1, 0, -1):
            path[t - 1] = back[t, path[t]]
        rows = []
        entry = []
        total = float(np.max(delta))
        for t in range(n):
            entry.append("t{}".format(t))
            rows.append([float(t), float(path[t]), float(log_emit[path[t], obs[t]])])
        ctx[str(params.get("output", "output"))] = table(
            entry, rows, ["time", "state", "log_emission"]
        )
