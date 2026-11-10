"""Shared Newick parsing for the b72 tree operators."""
from __future__ import annotations
import re
import numpy as np
from src.core import Form


class Node:
    __slots__ = ("name", "length", "children")

    def __init__(self, name="", length=0.0, children=None):
        self.name = name
        self.length = length
        self.children = children or []


TOKEN = re.compile(r"\s*([(),;:]|'(?:[^']|'')*'|[^\s(),;:]+)")


def parse_newick(text):
    tokens = [m.group(1) for m in TOKEN.finditer(text)]
    pos = [0]

    def peek():
        return tokens[pos[0]] if pos[0] < len(tokens) else ""

    def take():
        tok = peek()
        pos[0] += 1
        return tok

    def label():
        tok = peek()
        if tok and tok not in "(),;:":
            take()
            if tok.startswith("'") and tok.endswith("'"):
                return tok[1:-1].replace("''", "'")
            return tok
        return ""

    def node():
        children = []
        if peek() == "(":
            take()
            children.append(node())
            while peek() == ",":
                take()
                children.append(node())
            if peek() != ")":
                raise ValueError("unbalanced Newick")
            take()
        name = label()
        length = 0.0
        if peek() == ":":
            take()
            length = float(label() or 0.0)
        return Node(name, length, children)

    root = node()
    if peek() == ";":
        take()
    return root


def leaves(root):
    out = []
    def walk(n):
        if not n.children:
            out.append(n)
        for c in n.children:
            walk(c)
    walk(root)
    return out


def path_lengths(root):
    out = {}

    def walk(n, acc):
        acc += n.length
        if not n.children:
            out[n.name] = acc
        for c in n.children:
            walk(c, acc)

    walk(root, 0.0)
    return out


def descendants(n):
    names = []

    def walk(x):
        if not x.children:
            names.append(x.name)
        for c in x.children:
            walk(c)
    walk(n)
    return set(names)


def tips_path(root, name):
    found = []

    def walk(n, path):
        if found:
            return
        path = path + [n]
        if not n.children and n.name == name:
            found.extend(path)
            return
        for c in n.children:
            walk(c, path)
    walk(root, [])
    return found


def numeric_column(form, dim, name):
    labels = form.labels.get(dim, {})
    if name not in labels:
        raise ValueError(f"column {name!r} not present on {dim!r}")
    return np.asarray(form.data[:, int(labels[name])], dtype=float)


def result_form(names, values, columns):
    data = np.asarray(values, dtype=float)
    if data.size == 0:
        data = np.zeros((0, len(columns)), dtype=float)
    elif data.ndim == 1:
        data = data.reshape(1, -1)
    out = Form(
        data=np.round(data, 9),
        dims=["entry", "statistic"],
        labels={"entry": {str(n): i for i, n in enumerate(names)},
                "statistic": {c: i for i, c in enumerate(columns)}},
        info={"missing_code": np.nan, "columns": list(columns)},
    )
    out.validate()
    return out


def text_column(form, dim, name):
    labels = form.labels.get(dim) or {}
    if name not in labels:
        raise ValueError(f"column {name!r} not present on {dim!r}")
    idx = int(labels[name])
    vals = form.data[:, idx]
    enc = ((form.info or {}).get("encoders") or {})
    e = (enc.get(dim) or {}).get(name)
    if e is not None:
        if hasattr(e, "inverse_transform"):
            return [str(x) for x in e.inverse_transform(vals.astype(int))]
        if isinstance(e, dict):
            inv = {v: k for k, v in e.items()}
            return [str(inv.get(int(v), v)) for v in vals]
    return [str(v) for v in vals]
