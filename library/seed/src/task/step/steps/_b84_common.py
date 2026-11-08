"""Shared helpers for the b84 image-analysis batch."""

from __future__ import annotations

import numpy as np


def matrix(form):
    return np.asarray(form.data, dtype=float)


def row_names(form):
    labels = form.labels.get(form.dims[0], {})
    if isinstance(labels, dict) and labels:
        return [str(k) for k in sorted(labels, key=labels.get)]
    return [str(i) for i in range(form.data.shape[0])]
