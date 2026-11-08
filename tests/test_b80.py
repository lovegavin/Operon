import numpy as np

from src.core import Form
from src.task.step.steps.phylogenetics_gtr_likelihood import PhylogeneticsGtrLikelihoodStep
from src.task.step.steps.ms2_spectral_angle import Ms2SpectralAngleStep


class Ctx(dict):
    pass


def tree_form(text):
    f = Form(data=np.asarray([[0.0]]), dims=["row", "field"],
             labels={"row": {"t0": 0}, "field": {"newick": 0}},
             info={"encoders": {"field": {"newick": {0: text}}}})
    return f


def alignment_form(rows):
    names = list(rows)
    width = len(rows[names[0]])
    letters = "ACGT"
    table = np.zeros((len(names), width), dtype=float)
    encoders = {}
    for j in range(width):
        encoders["s%d" % (j + 1)] = {i: c for i, c in enumerate(letters)}
        for i, name in enumerate(names):
            table[i, j] = letters.index(rows[name][j])
    return Form(data=table, dims=["taxon", "site"],
                labels={"taxon": {n: i for i, n in enumerate(names)},
                        "site": {"s%d" % (j + 1): j for j in range(width)}},
                info={"encoders": {"site": encoders}})


def peak_form(peaks):
    data = np.asarray([[mz, intensity] for mz, intensity in peaks], dtype=float)
    return Form(data=data, dims=["peak", "field"],
                labels={"peak": {"p%d" % i: i for i in range(len(peaks))},
                        "field": {"mz": 0, "intensity": 1}})


def ctx(**params):
    c = Ctx()
    c.step_params = params
    return c


def test_gtr_likelihood():
    tree = tree_form("((A:0.1,B:0.2):0.3,(C:0.15,D:0.25):0.35);")
    aln = alignment_form({"A": "ACGTAC", "B": "ACGTAC", "C": "ACGTGC", "D": "ATGTAC"})
    c = ctx(output="out", tree_dim="row", field_dim="field", taxon_dim="taxon",
            site_dim="site", tree_column="newick",
            base_freqs="0.25,0.25,0.25,0.25", rates="1.0,2.0,0.5,0.5,2.0,1.0")
    PhylogeneticsGtrLikelihoodStep().run(c, [tree, aln])
    out = c["out"]
    assert out.data.shape == (1, 3)
    assert abs(out.data[0, 0] - (-19.315181699274824)) < 1e-9
    assert out.data[0, 1] == 4
    assert out.data[0, 2] == 6


def test_spectral_angle():
    q = peak_form([(100.0, 10.0), (200.0, 40.0), (300.0, 90.0)])
    lib = peak_form([(100.02, 90.0), (200.01, 10.0), (400.0, 50.0)])
    c = ctx(output="out", mz_tolerance=0.02)
    Ms2SpectralAngleStep().run(c, [q, lib])
    out = c["out"]
    assert out.data.shape == (1, 3)
    assert abs(out.data[0, 1] - 45.0) < 1e-9
    assert out.data[0, 2] == 2
