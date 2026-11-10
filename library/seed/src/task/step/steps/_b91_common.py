"""Shared helpers for the b91 Nucleotide Transformer operators."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import numpy as np

from src.core import Form


def row_names(form):
    dim = form.dims[0]
    labels = form.labels.get(dim) or {}
    if labels:
        inv = {int(v): k for k, v in labels.items()}
        return [inv.get(i, str(i)) for i in range(form.data.shape[0])]
    return [str(i) for i in range(form.data.shape[0])]


def column_index(form, name):
    dim = form.dims[1]
    labels = form.labels.get(dim) or {}
    if isinstance(labels, dict) and name in labels:
        idx = int(labels[name])
        if 0 <= idx < form.data.shape[1]:
            return idx
    raise ValueError(f"column {name!r} not found in {form.dims}")


def strings(form, dim, name):
    idx = column_index(form, name) if dim == form.dims[1] else None
    if idx is None:
        raise ValueError("string column must live on the field axis")
    enc = ((form.info or {}).get("encoders") or {}).get(dim, {}).get(name)
    values = form.data[:, idx]
    if enc is not None:
        inverse = getattr(enc, "inverse", None)
        if isinstance(inverse, dict):
            return [str(inverse[int(v)]) for v in values]
        inv_fn = getattr(enc, "inverse_transform", None)
        if callable(inv_fn):
            return [str(x) for x in inv_fn(values.astype(int))]
        if isinstance(enc, dict):
            return [str(enc[int(v)]) for v in values]
    return [str(v) for v in values]


def table(names, values, columns):
    data = np.array([values[k] for k in columns], dtype=float).T
    data = np.round(data, 6)
    labels = {str(i): i for i in range(data.shape[1])}
    return Form(data, dims=["entry", "statistic"], labels={"entry": {str(i): i for i in range(data.shape[0])}, "statistic": labels})


def resolve_weights(path=""):
    cand = path or os.environ.get("OPERON_NT_WEIGHTS", "")
    base = Path(cand).expanduser() if cand else Path("~/.cache/operon-weights/NTv2-50M").expanduser()
    if not (base / "config.json").is_file():
        raise ValueError(
            "Nucleotide Transformer weights not found at %s; set OPERON_NT_WEIGHTS or model_path" % base
        )
    return str(base)


@lru_cache(maxsize=2)
def load_nt(path):
    import torch
    from transformers import AutoModel, AutoTokenizer

    base = resolve_weights(path)
    tokenizer = AutoTokenizer.from_pretrained(base, trust_remote_code=True)
    from transformers import AutoConfig
    from transformers.dynamic_module_utils import get_class_from_dynamic_module

    config = AutoConfig.from_pretrained(base, trust_remote_code=True)
    model_cls = get_class_from_dynamic_module("modeling_esm.EsmModel", base)
    model = model_cls.from_pretrained(base, config=config)
    model.eval()
    return tokenizer, model


def embed(sequences, path="", max_length=512, batch_size=8):
    import torch

    tokenizer, model = load_nt(path)
    out = []
    with torch.no_grad():
        for start in range(0, len(sequences), batch_size):
            chunk = [s if s else "A" for s in sequences[start:start + batch_size]]
            enc = tokenizer(chunk, return_tensors="pt", padding=True, truncation=True, max_length=max_length)
            hidden = model(**enc).last_hidden_state
            mask = enc["attention_mask"].unsqueeze(-1).to(hidden.dtype)
            pooled = (hidden * mask).sum(1) / mask.sum(1).clamp(min=1.0)
            out.append(pooled.cpu().numpy())
    return np.concatenate(out, axis=0).astype(float)
