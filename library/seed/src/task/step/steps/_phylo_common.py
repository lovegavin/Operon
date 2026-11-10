"""Shared tree helpers for phylogeny-aware operators.

A tree reaches an operator as the node x field table produced by the
tree readers (``NewickReader``, ``PhyloXmlReader``): one row per node
with ``parent`` (encoded), ``branch_length``, ``depth`` and ``is_leaf``
columns. These helpers rebuild the parent/child structure once and
then provide the abundance propagation used by Faith's PD and the
UniFrac distances.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from src.core import StepError
from src.task.step.steps._ext_common import labels_in_order, reorder


@dataclass
class Tree:
    names: list[str]
    parent: np.ndarray
    length: np.ndarray
    children: list[list[int]]
    root: int
    tips: list[int]

    def postorder(self) -> list[int]:
        """Nodes with every child before its parent."""
        order: list[int] = []
        stack = [(self.root, False)]
        while stack:
            node, expanded = stack.pop()
            if expanded:
                order.append(node)
                continue
            stack.append((node, True))
            for child in reversed(self.children[node]):
                stack.append((child, False))
        return order


def load_tree(form, node_dim: str = "node", field_dim: str = "field", label: str = "tree") -> Tree:
    """Validate a tree table and return its parent/child structure."""
    if form.data.ndim != 2:
        raise StepError(f"{label}: expected a 2-D tree table, got {form.data.ndim} dims")
    if node_dim not in form.dims or field_dim not in form.dims:
        raise StepError(
            f"{label}: expected dims {node_dim!r} and {field_dim!r}, got {list(form.dims)}"
        )
    node_labels = form.labels.get(node_dim) or {}
    field_labels = form.labels.get(field_dim) or {}
    if not node_labels:
        raise StepError(f"{label}: tree has no node labels")
    n = len(node_labels)
    names: list[str | None] = [None] * n
    for name, position in node_labels.items():
        position = int(position)
        if position < 0 or position >= n or names[position] is not None:
            raise StepError(f"{label}: node labels are not a contiguous 0..{n - 1} mapping")
        names[position] = str(name)
    fields = {str(key): int(value) for key, value in field_labels.items()}
    for required in ("parent", "branch_length", "is_leaf"):
        if required not in fields:
            raise StepError(f"{label}: tree table is missing the {required!r} field")

    data = reorder(form, node_dim, field_dim).astype(np.float64)
    encoders = form.info.get("encoders") or {}
    parent_encoder = (encoders.get(field_dim) or {}).get("parent")
    if parent_encoder is None or not hasattr(parent_encoder, "inverse_transform"):
        raise StepError(f"{label}: tree table has no encoded parent column")
    codes = data[:, fields["parent"]]
    if not np.all(np.isfinite(codes)):
        raise StepError(f"{label}: parent codes contain missing values")
    decoded = parent_encoder.inverse_transform(np.rint(codes).astype(np.int64))
    parent_names = [None if value is None else str(value) for value in decoded]

    positions = {name: index for index, name in enumerate(names)}
    parent = np.full(n, -1, dtype=np.int64)
    for index, parent_name in enumerate(parent_names):
        if parent_name is None or parent_name in ("None", "null", ""):
            continue
        if parent_name not in positions:
            raise StepError(
                f"{label}: parent {parent_name!r} of {names[index]!r} is not a node in this tree"
            )
        parent[index] = positions[parent_name]
        if parent[index] == index:
            raise StepError(f"{label}: node {names[index]!r} is its own parent")
    roots = np.flatnonzero(parent < 0)
    if roots.size != 1:
        raise StepError(f"{label}: expected exactly one root, found {int(roots.size)}")
    root = int(roots[0])

    lengths = data[:, fields["branch_length"]]
    flags = data[:, fields["is_leaf"]]
    if not np.all(np.isfinite(flags)):
        raise StepError(f"{label}: is_leaf column contains missing values")
    children: list[list[int]] = [[] for _ in range(n)]
    for index in range(n):
        if parent[index] >= 0:
            children[int(parent[index])].append(index)
    length = np.zeros(n, dtype=np.float64)
    for index in range(n):
        value = lengths[index]
        if index == root:
            if np.isfinite(value) and value != 0.0:
                raise StepError(f"{label}: the root must not carry a branch length")
            continue
        if not np.isfinite(value):
            raise StepError(f"{label}: node {names[index]!r} has no branch length")
        if value < 0:
            raise StepError(f"{label}: node {names[index]!r} has a negative branch length")
        length[index] = float(value)
    for index in range(n):
        marked = flags[index] > 0.5
        if marked != (not children[index]):
            raise StepError(f"{label}: is_leaf flag is inconsistent for {names[index]!r}")

    tree = Tree(
        names=[str(name) for name in names],
        parent=parent,
        length=length,
        children=children,
        root=root,
        tips=[index for index in range(n) if not children[index]],
    )
    if len(tree.postorder()) != n:
        raise StepError(f"{label}: the tree is not one connected rooted structure")
    return tree


def abundance_matrix(form, sample_dim: str, taxon_dim: str, label: str = "abundance"):
    """Return (matrix [sample, taxon] float64, sample labels, taxon labels)."""
    if form.data.ndim != 2:
        raise StepError(f"{label}: expected a 2-D abundance table, got {form.data.ndim} dims")
    if sample_dim not in form.dims or taxon_dim not in form.dims:
        raise StepError(
            f"{label}: expected dims {sample_dim!r} and {taxon_dim!r}, got {list(form.dims)}"
        )
    data = reorder(form, sample_dim, taxon_dim).astype(np.float64)
    missing = form.info.get("missing_code", np.nan)
    if isinstance(missing, float) and np.isnan(missing):
        absent = np.isnan(data)
    else:
        absent = data == missing
    data = np.where(absent, 0.0, data)
    if not np.all(np.isfinite(data)):
        raise StepError(f"{label}: abundances are not finite even after filling missing values")
    if np.any(data < 0):
        raise StepError(f"{label}: abundances must be non-negative")
    return data, labels_in_order(form, sample_dim), labels_in_order(form, taxon_dim)


def node_counts(counts: np.ndarray, taxa: list[str], tree: Tree, label: str = "tree") -> np.ndarray:
    """Propagate tip abundances to every node, as scikit-bio does."""
    tips = {tree.names[index]: index for index in tree.tips}
    missing = [str(name) for name in taxa if str(name) not in tips]
    if missing:
        preview = ", ".join(missing[:5])
        if len(missing) > 5:
            preview += ", ..."
        raise StepError(
            f"{label}: {len(missing)} taxa are not tips in the tree: {preview}"
        )
    result = np.zeros((counts.shape[0], len(tree.names)), dtype=np.float64)
    for column, name in enumerate(taxa):
        result[:, tips[str(name)]] = counts[:, column]
    for node in tree.postorder():
        parent = int(tree.parent[node])
        if parent >= 0:
            result[:, parent] += result[:, node]
    return result


def faith_pd_values(by_node: np.ndarray, length: np.ndarray) -> np.ndarray:
    """Faith's PD: sum of branch lengths on the union of root-to-tip paths."""
    return (length[None, :] * (by_node > 0)).sum(axis=1)


def unifrac_matrix(
    by_node: np.ndarray,
    length: np.ndarray,
    weighted: bool = False,
    totals: np.ndarray | None = None,
) -> np.ndarray:
    """Pairwise UniFrac distances between the rows of ``by_node``.

    ``by_node`` repeats every count at each ancestor, so weighted UniFrac
    must divide by the original per-sample totals, never by a row sum.
    """
    n = by_node.shape[0]
    if n == 0:
        raise StepError("unifrac: the abundance table has no samples")
    out = np.zeros((n, n), dtype=np.float64)
    if weighted:
        if totals is None:
            totals = by_node.sum(axis=1)
        totals = np.asarray(totals, dtype=np.float64)
        if totals.shape != (n,):
            raise StepError("unifrac: totals must hold one value per sample")
        proportions = np.zeros_like(by_node)
        nonzero = totals > 0
        proportions[nonzero] = by_node[nonzero] / totals[nonzero, None]
        for i in range(n):
            for j in range(i + 1, n):
                value = float(np.sum(length * np.abs(proportions[i] - proportions[j])))
                out[i, j] = out[j, i] = value
        return out
    present = by_node > 0
    for i in range(n):
        for j in range(i + 1, n):
            unique = np.logical_xor(present[i], present[j])
            observed = np.logical_or(present[i], present[j])
            observed_length = float(np.sum(length[observed]))
            value = 0.0 if observed_length == 0.0 else float(np.sum(length[unique])) / observed_length
            out[i, j] = out[j, i] = value
    return out


def tip_distances(tree: Tree) -> np.ndarray:
    """Patristic distance matrix between tips, in tip order."""
    order = tree.postorder()
    root_distance = np.zeros(len(tree.names), dtype=np.float64)
    depth = np.zeros(len(tree.names), dtype=np.int64)
    for node in reversed(order):
        parent = int(tree.parent[node])
        if parent >= 0:
            root_distance[node] = root_distance[parent] + tree.length[node]
            depth[node] = depth[parent] + 1
    tips = tree.tips
    n = len(tips)
    out = np.zeros((n, n), dtype=np.float64)
    for i in range(n):
        for j in range(i + 1, n):
            left, right = tips[i], tips[j]
            while depth[left] > depth[right]:
                left = int(tree.parent[left])
            while depth[right] > depth[left]:
                right = int(tree.parent[right])
            while left != right:
                left = int(tree.parent[left])
                right = int(tree.parent[right])
            out[i, j] = out[j, i] = (
                root_distance[tips[i]] + root_distance[tips[j]] - 2.0 * root_distance[left]
            )
    return out


# --- Post-1001 additions: Newick parsing, JC69 likelihood, RF distance ---

"""Small Newick parser and JC69 helpers shared by the b78 phylogenetics operators."""

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
