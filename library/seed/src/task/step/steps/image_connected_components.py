"""Connected components."""

from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.step.base import Step

from ._b84_common import matrix, row_names


class ImageConnectedComponentsStep(Step):
    parameters_file = "image_connected_components.ImageConnectedComponentsStep.parameters.json"
    definition = {'protocol_version': 3, 'protocol_revision': '3.7', 'kind': 'operator', 'id': 'image_connected_components', 'version': '1.0.0', 'title': 'Connected components', 'description': 'Labels binary foreground regions with four-connectivity and filters by area.', 'category': 'Statistics', 'icon': 'image', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}], 'labels': [], 'parallel': []}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}}

    def run(self, ctx, inputs):
        data = matrix(inputs[0])
        binary = data > 0.5
        h, w = binary.shape
        labels = np.zeros((h, w), dtype=int)
        comps = []
        cur = 0
        for y in range(h):
            for x in range(w):
                if not binary[y, x] or labels[y, x]:
                    continue
                cur += 1
                stack = [(y, x)]
                labels[y, x] = cur
                pts = []
                while stack:
                    cy, cx = stack.pop()
                    pts.append((cy, cx))
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = cy + dy, cx + dx
                        if 0 <= ny < h and 0 <= nx < w and binary[ny, nx] and not labels[ny, nx]:
                            labels[ny, nx] = cur
                            stack.append((ny, nx))
                if len(pts) >= int(float(ctx.step_params.get("min_area", 1))):
                    ys = [p[0] for p in pts]; xs = [p[1] for p in pts]
                    comps.append([cur, len(pts), float(np.mean(ys)), float(np.mean(xs)),
                                  min(ys), min(xs), max(ys), max(xs)])
        if not comps:
            comps = [[0, 0, 0.0, 0.0, 0, 0, 0, 0]]
        arr = np.asarray(comps, dtype=float)
        out = Form(
            arr,
            dims=["component", "statistic"],
            labels={"component": {("c%d" % int(r[0])): i for i, r in enumerate(arr)},
                    "statistic": {"label": 0, "area": 1, "centroid_y": 2, "centroid_x": 3,
                                  "bbox_y0": 4, "bbox_x0": 5, "bbox_y1": 6, "bbox_x1": 7}},
        )
        ctx[ctx.step_params["output"]] = out
