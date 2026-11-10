"""Auto-generated b83 operator."""
import numpy as np

from src.core import Form
from src.task.step.base import Step

from ._b83_common import column, strings, table


class CrisprMitSpecificityStep(Step):
    parameters_file = "crispr_mit_specificity.CrisprMitSpecificityStep.parameters.json"

    definition = {'id': 'crispr_mit_specificity', 'version': '1.0.0', 'title': 'CRISPR MIT specificity', 'description': 'Compute the Hsu 2013 position-weighted MIT specificity score for guide/off-target pairs.', 'category': 'Genome editing', 'kind': 'operator', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'protocol_version': 3, 'protocol_revision': '3.7', 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}, 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': []}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}}

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return (32 * 1024 * 1024, 0)

    def run(self, ctx, inputs):
        params = ctx.step_params
        form = inputs[0]
        guides = strings(form, form.dims[1], "guide")
        offtargets = strings(form, form.dims[1], "off_target")
        weights = np.array([0.0, 0.0, 0.014, 0.0, 0.0, 0.395, 0.317, 0.0, 0.389, 0.079,
                            0.445, 0.508, 0.613, 0.851, 0.732, 0.828, 0.615, 0.804, 0.685, 0.583])
        rows, entry = [], []
        for idx, (g, o) in enumerate(zip(guides, offtargets)):
            if len(g) != len(o):
                raise ValueError("guide and off_target must have equal length")
            score = 1.0
            mm = 0
            farthest = 0
            for i, (a, b) in enumerate(zip(g.upper(), o.upper())):
                if a != b:
                    mm += 1
                    farthest = i
                    score *= 1.0 - weights[min(i, len(weights) - 1)]
            rows.append([100.0 * score, float(mm), float(farthest)])
            entry.append(f"g{idx + 1}_{g[:8]}_{o[:8]}")
        ctx[str(params.get("output", "output"))] = table(entry, rows, ["mit_score", "mismatches", "last_mismatch_pos"])

