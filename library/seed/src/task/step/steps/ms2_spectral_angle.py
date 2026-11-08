"""Spectral angle between two centroid peak lists."""
from __future__ import annotations

import math
import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step


def column(form, name):
    labels = (form.labels or {}).get(form.dims[1]) or {}
    if name not in labels:
        raise StepError("missing column %r" % name)
    return np.asarray(form.data[:, int(labels[name])], dtype=float)


class Ms2SpectralAngleStep(Step):
    parameters_file = "ms2_spectral_angle.Ms2SpectralAngleStep.parameters.json"

    definition = {'category': 'Proteomics',
 'contracts': {'inputs': [{'dims': [{'default': 'peak', 'param': 'peak_dim'},
                                    {'default': 'field', 'param': 'field_dim'}],
                           'labels': [],
                           'ndim': 2,
                           'numeric': True,
                           'parallel': [],
                           'version': 1},
                          {'dims': [{'default': 'peak', 'param': 'peak_dim'},
                                    {'default': 'field', 'param': 'field_dim'}],
                           'labels': [],
                           'ndim': 2,
                           'numeric': True,
                           'parallel': [],
                           'version': 1}],
               'output': {'mode': 'declare',
                          'schema': {'dims': ['entry', 'statistic'], 'numeric': True}},
               'version': 1},
 'data_formats': {'inputs': [{'logical_type': 'form', 'metadata': {}, 'representations': ['form']},
                             {'logical_type': 'form', 'metadata': {}, 'representations': ['form']}],
                  'outputs': [{'logical_type': 'form',
                               'metadata': {},
                               'representations': ['form']}]},
 'description': 'Spectral angle in degrees between two centroid peak lists using square-root '
                'intensities and greedy m/z matching.',
 'icon': 'Tree',
 'id': 'ms2_spectral_angle',
 'inputs_arity': 2,
 'kind': 'operator',
 'output_parameter': 'output',
 'outputs': [],
 'protocol_revision': '3.7',
 'protocol_version': 3,
 'resources': {'estimate': 'estimate_memory', 'memory_modes': ['full'], 'supports_cuda': False},
 'title': 'MS2 spectral angle',
 'version': '1.0.0'}

    def run(self, ctx, inputs):
        q, lib = inputs
        q_mz, q_in = column(q, "mz"), column(q, "intensity")
        l_mz, l_in = column(lib, "mz"), column(lib, "intensity")
        tol = float(ctx.step_params["mz_tolerance"])
        used = set()
        qv, lv = [], []
        for mz, intensity in zip(q_mz, q_in):
            best, distance = None, tol
            for index, other in enumerate(l_mz):
                d = abs(float(mz) - float(other))
                if d <= distance and index not in used:
                    best, distance = index, d
            if best is not None:
                used.add(best)
                qv.append(math.sqrt(max(float(intensity), 0.0)))
                lv.append(math.sqrt(max(float(l_in[best]), 0.0)))
        if not qv:
            raise StepError("no peaks matched within tolerance")
        a = np.asarray(qv, dtype=float)
        b = np.asarray(lv, dtype=float)
        denom = float(np.linalg.norm(a) * np.linalg.norm(b))
        cosine = float(np.dot(a, b) / denom) if denom > 0 else 0.0
        cosine = float(min(1.0, max(-1.0, cosine)))
        angle = math.degrees(math.acos(cosine))
        out = Form(
            data=np.asarray([[cosine, angle, float(len(qv))]], dtype=float),
            dims=["entry", "statistic"],
            labels={"entry": {"angle": 0},
                    "statistic": {"cosine": 0, "angle_deg": 1, "matched_peaks": 2}},
            info={"columns": ["cosine", "angle_deg", "matched_peaks"]},
        )
        ctx[ctx.step_params["output"]] = out
