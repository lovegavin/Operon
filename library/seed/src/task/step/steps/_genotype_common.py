"""Genotype table helpers."""
import numpy as np
from src.core import StepError, Form

def labels(form, dim="sample"):
    lab = form.labels.get(str(dim))
    if not isinstance(lab, dict) or not lab:
        raise StepError("genotype table: missing sample labels")
    return lab

def index(form, name, dim="sample"):
    lab = labels(form, dim)
    if name not in lab:
        raise StepError(f"sample {name!r} not in {sorted(lab)}")
    return int(lab[name])

def _mapping(lab, n):
    if isinstance(lab, dict):
        return lab
    if isinstance(lab, (list, tuple)):
        return {str(v): i for i, v in enumerate(lab)}
    return {str(i): i for i in range(n)}

def form(names, cols, dim, lab):
    data = np.column_stack(cols) if cols else np.zeros((0, 0))
    return Form(data=data, dims=[str(dim), "statistic"],
                labels={str(dim): _mapping(lab, len(lab) if hasattr(lab, "__len__") else 0), "statistic": names if isinstance(names, dict) else {str(n): i for i, n in enumerate(names)}})
