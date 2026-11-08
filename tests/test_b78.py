import numpy as np

from src.core import Form
from src.task.step.steps.phylogenetics_jc69_likelihood import PhylogeneticsJc69LikelihoodStep
from src.task.step.steps.tree_outgroup_root import TreeOutgroupRootStep


class Ctx(dict):
    pass


def tree_form(texts):
    f = Form(data=np.asarray([[i] for i in range(len(texts))], dtype=float),
             dims=["row", "field"],
             labels={"row": {"t%d" % i: i for i in range(len(texts))}, "field": {"newick": 0}},
             info={"encoders": {}})
    f.info["encoders"] = {"field": {"newick": {i: t for i, t in enumerate(texts)}}}
    return f


def alignment_form(rows):
    names = list(rows)
    width = len(rows[names[0]])
    letters = "ACGT"
    table = np.zeros((len(names), width), dtype=float)
    encoders = {}
    for j in range(width):
        mapping = {i: c for i, c in enumerate(letters)}
        encoders["s%d" % (j + 1)] = mapping
        for i, name in enumerate(names):
            table[i, j] = letters.index(rows[name][j])
    return Form(data=table, dims=["taxon", "site"],
                labels={"taxon": {n: i for i, n in enumerate(names)},
                        "site": {"s%d" % (j + 1): j for j in range(width)}},
                info={"encoders": {"site": encoders}})


def ctx(**params):
    c = Ctx()
    c.step_params = params
    return c


def test_jc69_likelihood():
    tree = tree_form(["((A:0.1,B:0.2):0.3,(C:0.15,D:0.25):0.35);"])
    aln = alignment_form({"A": "ACGTAC", "B": "ACGTAC", "C": "AGGTAT", "D": "AGGTAT"})
    c = ctx(output="out", tree_dim="row", field_dim="field", taxon_dim="taxon", site_dim="site")
    PhylogeneticsJc69LikelihoodStep().run(c, [tree, aln])
    out = c["out"]
    assert abs(out.data[0, 0] - (-18.416477967)) < 1e-8
    assert out.info["n_sites"] == 6
    assert out.info["n_taxa"] == 4


def test_outgroup_root():
    tree = tree_form(["((A:0.1,B:0.2):0.3,(C:0.15,D:0.25):0.35);"])
    c = ctx(output="out", row_dim="row", field_dim="field", outgroup="A")
    TreeOutgroupRootStep().run(c, [tree])
    out = c["out"]
    assert out.data[0, 0] == 4
    assert out.data[0, 1] == 2
    assert abs(out.data[0, 2] - 0.1) < 1e-12
    assert out.info["newick"].startswith("(A:0.1")
