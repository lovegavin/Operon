"""Readable input-validation errors for the operator-library coverage defects.

These tests call the guards directly: they never touch the network, a full
workflow or a heavy dependency, so they stay fast.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core import Form  # noqa: E402
from src.reader.readers._encoder import LabelEncoder  # noqa: E402
from src.task.step.steps._b91_common import embed, resolve_weights  # noqa: E402
from src.task.step.steps._go_utils import require_ontology_inputs  # noqa: E402
from src.task.step.steps._phylo_common import load_tree, parse_newick, tips  # noqa: E402
from src.task.step.steps.gwas_top_hits import GwasTopHitsStep  # noqa: E402
from src.task.step.steps.go_gene_similarity import GoGeneSimilarityStep  # noqa: E402
from src.task.step.steps.go_ic_profile import GoIcProfileStep  # noqa: E402
from src.task.step.steps.go_term_similarity import GoTermSimilarityStep  # noqa: E402
from src.task.step.steps.structure_contacts import StructureContactsStep  # noqa: E402
from src.task.step.steps.structure_hbonds import _residues  # noqa: E402
from src.task.step.steps.structure_ligand_geometry_qc import ligand_block  # noqa: E402
from src.task.step.steps.structure_ligand_pose_qc import split_complex  # noqa: E402

STEPS = ROOT / "library" / "seed" / "src" / "task" / "step" / "steps"


class Ctx(dict):
    """Minimal step context: ``run`` only reads ``step_params`` and writes outputs."""

    def __init__(self, params):
        super().__init__()
        self.step_params = dict(params)


def structure_form(labels, rows=4):
    """A PDB-like form with exactly the named field columns."""
    return Form(
        data=np.zeros((rows, len(labels)), dtype=float),
        dims=["atom", "field"],
        labels={"atom": {"a%d" % index: index for index in range(rows)}, "field": dict(labels)},
        info={"encoders": {}, "format": "pdb"},
    )


def tree_form(names, parents, lengths, leaves):
    """A tree form that records parent *labels* through a label encoder."""
    encoder = LabelEncoder()
    codes = encoder.fit_transform(list(parents))
    rows = [[codes[index], float(lengths[index]), float(leaves[index])] for index in range(len(names))]
    return Form(
        data=np.asarray(rows, dtype=float),
        dims=["node", "field"],
        labels={
            "node": {name: index for index, name in enumerate(names)},
            "field": {"parent": 0, "branch_length": 1, "is_leaf": 2},
        },
        info={"encoders": {"field": {"parent": encoder}}},
    )


def association_form(labels):
    return Form(
        data=np.asarray([[1e-12, 0.1, 0.02]], dtype=float),
        dims=["variant", "statistic"],
        labels={
            "variant": {label: index for index, label in enumerate(labels)},
            "statistic": {"p": 0, "beta": 1, "se": 2},
        },
        info={},
    )


def raises_value_error(call, *expected):
    with pytest.raises(ValueError) as excinfo:
        call()
    message = str(excinfo.value)
    for fragment in expected:
        assert fragment in message, (fragment, message)
    return message


# --------------------------------------------------------------- group 1
def test_gwas_top_hits_names_a_variant_without_a_position():
    message = raises_value_error(
        lambda: GwasTopHitsStep().run(Ctx({"output": "hits"}), [association_form(["variant0"])]),
        "gwas_top_hits",
        "chrom",
        "position",
    )
    assert "'variant0'" in message


def test_gwas_top_hits_names_a_non_numeric_position():
    raises_value_error(
        lambda: GwasTopHitsStep().run(Ctx({"output": "hits"}), [association_form(["22:abc"])]),
        "gwas_top_hits",
        "'22:abc'",
    )


def test_gwas_top_hits_still_parses_chrom_position_labels():
    ctx = Ctx({"output": "hits"})
    GwasTopHitsStep().run(ctx, [association_form(["22:100:A:G"])])
    assert np.asarray(ctx["hits"].data).shape[0] == 1


# --------------------------------------------------------------- group 2
def test_structure_hbonds_names_the_missing_coordinate_columns():
    form = structure_form({"chain": 0, "resname": 1, "residue_number": 2, "atom_name": 3})
    raises_value_error(lambda: _residues(form, "atom", "field"), "structure_hbonds", "'z'", "PDB reader")


# --------------------------------------------------------------- group 3
def test_structure_ligand_geometry_qc_names_the_missing_columns():
    form = structure_form({"x": 0, "y": 1, "z": 2})
    raises_value_error(
        lambda: ligand_block(form, "atom", "field", {"LIG"}),
        "structure_ligand_geometry_qc",
        "'resname'",
    )


def test_structure_contacts_names_the_missing_columns():
    form = structure_form({"x": 0, "y": 1, "z": 2})
    raises_value_error(
        lambda: StructureContactsStep().run(Ctx({"output": "contacts"}), [form]),
        "structure_contacts",
        "'resname'",
        "'chain'",
    )


# --------------------------------------------------------------- group 4
def test_structure_ligand_pose_qc_names_the_missing_columns():
    form = structure_form({"x": 0, "y": 1, "z": 2})
    raises_value_error(
        lambda: split_complex(form, "field", "LIG"),
        "structure_ligand_pose_qc",
        "'resname'",
        "'element'",
    )


# --------------------------------------------------------------- group 5
def _harness_tree():
    names = ["0", "1", "2", "3", "4"]
    parents = ["n1", "n2", "n1", None, "n2"]
    return tree_form(names, parents, [1.0, 1.0, 2.0, 0.0, 2.0], [1, 1, 0, 0, 0])


def test_tree_loader_names_the_offending_parent_and_child():
    raises_value_error(
        lambda: load_tree(_harness_tree(), label="faith_pd"),
        "faith_pd",
        "parent 'n1'",
        "node '0'",
        "0-based node index",
    )


def test_tree_loader_accepts_parent_labels():
    names = ["A", "B", "n1", "C", "D", "n2", "root"]
    parents = ["n1", "n1", "root", "n2", "n2", "root", None]
    tree = load_tree(
        tree_form(names, parents, [1.0, 1.0, 2.0, 1.0, 1.0, 2.0, 0.0], [1, 1, 0, 1, 1, 0, 0]),
        label="faith_pd",
    )
    assert tree.names[tree.root] == "root"
    assert sorted(tree.names[index] for index in tree.tips) == ["A", "B", "C", "D"]


def test_tree_loader_accepts_zero_based_parent_indices():
    names = ["A", "B", "n1", "C", "D", "n2", "root"]
    parents = ["2", "2", "6", "5", "5", "6", "-1"]
    tree = load_tree(
        tree_form(names, parents, [1.0, 1.0, 2.0, 1.0, 1.0, 2.0, 0.0], [1, 1, 0, 1, 1, 0, 0]),
        label="faith_pd",
    )
    assert tree.names[tree.root] == "root"


# --------------------------------------------------------------- group 6
def test_newick_parser_accepts_a_redundant_trailing_parenthesis():
    root = parse_newick("((A:0.1,B:0.2):0.3,(C:0.4,D:0.5):0.6));", "tree_outgroup_root")
    assert sorted(tip.name for tip in tips(root)) == ["A", "B", "C", "D"]


def test_newick_parser_reports_empty_text_and_trailing_tokens():
    raises_value_error(lambda: parse_newick("", "tree_outgroup_root"), "tree_outgroup_root", "empty")
    raises_value_error(
        lambda: parse_newick("(A:1,B:2),", "phylo_lambda"),
        "phylo_lambda",
        "trailing Newick text ','",
        "position 9",
    )


# --------------------------------------------------------------- group 7
def test_nucleotide_transformer_names_the_weights_path(tmp_path, monkeypatch):
    monkeypatch.delenv("OPERON_NT_WEIGHTS", raising=False)
    missing = tmp_path / "sample.pdb"
    message = raises_value_error(
        lambda: resolve_weights(str(missing), "nucleotide_transformer_embedding"),
        "nucleotide_transformer_embedding",
        "model_path",
        "sample.pdb",
        str(missing / "config.json"),
    )
    assert "OPERON_NT_WEIGHTS" in message
    raises_value_error(
        lambda: embed(["ACGT"], str(missing), operator="nucleotide_transformer_variant_effect"),
        "nucleotide_transformer_variant_effect",
        str(missing / "config.json"),
    )


# --------------------------------------------------------------- group 8
def test_go_operators_name_the_empty_ontology_parameters():
    raises_value_error(
        lambda: require_ontology_inputs("", "", "go_term_similarity"),
        "go_term_similarity",
        "'obo_path'",
        "absolute path",
    )
    for step, name in (
        (GoGeneSimilarityStep(), "go_gene_similarity"),
        (GoIcProfileStep(), "go_ic_profile"),
        (GoTermSimilarityStep(), "go_term_similarity"),
    ):
        raises_value_error(
            lambda step=step, name=name: step.run(Ctx({"output": "out"}), [structure_form({"x": 0})]),
            name,
            "'obo_path'",
            "absolute path",
        )


def test_go_parameter_sidecars_require_explicit_absolute_paths():
    for name in ("go_gene_similarity", "go_ic_profile", "go_term_similarity"):
        payload = json.loads((STEPS / (name + ".parameters.json")).read_text(encoding="utf-8"))
        for field in ("obo_path", "gaf_path"):
            spec = payload["properties"][field]
            assert spec["default"] == "", (name, field, spec)
            assert "b40_route" not in json.dumps(spec)
            assert "absolute path" in spec.get("description", ""), (name, field, spec)
