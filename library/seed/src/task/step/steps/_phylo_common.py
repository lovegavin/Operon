"""Small Newick parser and JC69 helpers shared by the b78 phylogenetics operators."""
from __future__ import annotations

import math

import numpy as np


class Node:
    __slots__ = ("name", "length", "children")

    def __init__(self, name="", length=None, children=None):
        self.name = name
        self.length = length
        self.children = children or []


def parse_newick(text):
    text = str(text).strip().rstrip(";")
    pos = 0
    n = len(text)

    def parse_node():
        nonlocal pos
        children = []
        name = ""
        length = None
        if text[pos] == "(":
            pos += 1
            while True:
                children.append(parse_node())
                if text[pos] == ",":
                    pos += 1
                    continue
                if text[pos] == ")":
                    pos += 1
                    break
                raise ValueError("malformed newick near %r" % text[pos:pos + 20])
        start = pos
        while pos < n and text[pos] not in ",():;":
            pos += 1
        name = text[start:pos].strip()
        if pos < n and text[pos] == ":":
            pos += 1
            start = pos
            while pos < n and text[pos] not in ",():;":
                pos += 1
            length = float(text[start:pos])
        return Node(name, length, children)

    root = parse_node()
    if pos != n:
        raise ValueError("trailing newick text %r" % text[pos:])
    return root


def tips(node):
    if not node.children:
        return [node]
    out = []
    for child in node.children:
        out.extend(tips(child))
    return out


def to_newick(node, with_lengths=True):
    if node.children:
        body = "(" + ",".join(to_newick(c, with_lengths) for c in node.children) + ")"
    else:
        body = node.name
    if with_lengths and node.length is not None:
        body += ":%g" % node.length
    return body


def jc69_p(t):
    if t < 0:
        raise ValueError("negative branch length")
    e = math.exp(-4.0 * t / 3.0)
    same = 0.25 + 0.75 * e
    diff = 0.25 - 0.25 * e
    return same, diff


def jc69_prob(parent, child, t):
    same, diff = jc69_p(t)
    return same if parent == child else diff


def log_likelihood(root, sequences):
    """Felsenstein pruning for a reversible 4-state JC69 model."""
    names = [tip.name for tip in tips(root)]
    if sorted(names) != sorted(sequences):
        raise ValueError("tree tips and alignment names differ")
    letters = "ACGT"
    index = {c: i for i, c in enumerate(letters)}
    encoded = {}
    for name, text in sequences.items():
        for ch in text:
            if ch not in index:
                raise ValueError("unsupported nucleotide %r" % ch)
        encoded[name] = [index[ch] for ch in text]
    width = len(next(iter(encoded.values())))
    if any(len(v) != width for v in encoded.values()):
        raise ValueError("alignment rows differ in length")
    total = 0.0
    for site in range(width):
        def partial(node):
            if not node.children:
                vec = np.zeros(4)
                vec[encoded[node.name][site]] = 1.0
                return vec
            vec = np.ones(4)
            for child in node.children:
                sub = partial(child)
                t = child.length if child.length is not None else 0.0
                same, diff = jc69_p(t)
                vec *= same * sub + diff * (sub.sum() - sub)
            return vec
        total += math.log(0.25 * float(partial(root).sum()))
    return total, len(names), width


def reroot_at_tip(root, outgroup):
    target = None
    for tip in tips(root):
        if tip.name == outgroup:
            target = tip
            break
    if target is None:
        raise ValueError("outgroup %r not found" % outgroup)
    # The new root splits the edge above the outgroup: outgroup on one side,
    # the remaining tree (without that edge) on the other.
    def prune(node):
        if node is target:
            return None
        kept = []
        for child in node.children:
            sub = prune(child)
            if sub is not None:
                kept.append(sub)
        if node.children and not kept:
            return None
        return Node(node.name, node.length, kept)

    rest = prune(root)
    if rest is None:
        raise ValueError("outgroup is the whole tree")
    rest.length = 0.0
    new_root = Node("", None, [Node(outgroup, target.length, []), rest])
    return new_root
