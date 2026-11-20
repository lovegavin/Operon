"""Readable input errors for the pairwise, variant and prodigal operators.

Each test drives the operator guard directly, so no network, workflow or heavy
dependency is involved.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core import FileArtifact, StepError  # noqa: E402
from src.task.step.steps._sequence_common import encode_sequences  # noqa: E402
from src.task.step.steps.pairwise_alignment import PairwiseAlignmentStep  # noqa: E402
from src.task.step.steps.prodigal_genes import ProdigalGenesStep  # noqa: E402
from src.task.step.steps.variant_consequence import VariantConsequenceStep  # noqa: E402


class Ctx(dict):
    """Minimal step context: ``run`` reads ``step_params`` and writes outputs."""

    def __init__(self, params, root=None):
        super().__init__()
        self.step_params = dict(params)
        self._root = root

    def artifact_path(self, name):
        return str(self._root / name)


def sequence_form(sequences):
    return encode_sequences(sequences, "sequence", "position", "dna")


# --------------------------------------------------------------- pairwise
def test_pairwise_alignment_accepts_one_sequence_per_input():
    ctx = Ctx({"output": "alignment"})
    PairwiseAlignmentStep().run(
        ctx,
        [sequence_form(["AAAA"]), sequence_form(["AAAT"])],
    )
    form = ctx["alignment"]
    assert form.dims == ["statistic", "value"]
    assert form.data.shape == (9, 1)
    assert form.labels["statistic"]["score"] == 0


def test_pairwise_alignment_accepts_the_same_two_sequence_input_on_both_ports():
    shared = sequence_form(["AAAA", "AAAT"])
    ctx = Ctx({"output": "alignment"})
    PairwiseAlignmentStep().run(ctx, [shared, shared])
    assert ctx["alignment"].data.shape == (9, 1)


def test_pairwise_alignment_error_names_the_counts_and_dimensions():
    three = sequence_form(["AA", "CC", "GG"])
    two = sequence_form(["AA", "CC"])
    with pytest.raises(StepError) as excinfo:
        PairwiseAlignmentStep().run(Ctx({"output": "alignment"}), [three, two])
    message = str(excinfo.value)
    assert "exactly two sequences are required" in message
    assert "input 1 holds 3" in message
    assert "input 2 holds 2" in message
    assert "'sequence'" in message
    assert "'position'" in message


# --------------------------------------------------------------- variant
_GENOME = "CCCATGGAATTTGGGCCCAAATTTGATTAA"
_GFF = """##gff-version 3
chr1\t.\tgene\t1\t30\t.\t+\t.\tID=gene1;Name=GENE1;biotype=protein_coding
chr1\t.\tmRNA\t1\t30\t.\t+\t.\tID=tx1;Parent=gene1;biotype=protein_coding
chr1\t.\texon\t1\t30\t.\t+\t.\tID=ex1;Parent=tx1
chr1\t.\tCDS\t4\t30\t.\t+\t0\tID=cds1;Parent=tx1
"""
_VCF = """##fileformat=VCFv4.2
##contig=<ID=chr1,length=30>
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
chr1\t7\t.\tG\tT\t.\t.\t.
"""


def variant_fixtures(tmp_path, fasta_name):
    fasta = tmp_path / "reference.fa"
    fasta.write_text(f">{fasta_name}\n{_GENOME}\n", encoding="utf-8")
    gff = tmp_path / "annotation.gff3"
    gff.write_text(_GFF, encoding="utf-8")
    vcf = tmp_path / "variants.vcf"
    vcf.write_text(_VCF, encoding="utf-8")
    return fasta, gff, vcf


def variant_artifacts(paths):
    fasta, gff, vcf = paths
    return [
        FileArtifact("vcf", {"variants": str(vcf)}),
        FileArtifact("gff3", {"annotation": str(gff)}),
        FileArtifact("fasta", {"reference": str(fasta)}),
    ]


def test_variant_consequence_annotates_matching_fasta_names(tmp_path):
    ctx = Ctx({"output": "annotated"}, tmp_path)
    VariantConsequenceStep().run(
        ctx, variant_artifacts(variant_fixtures(tmp_path, "chr1"))
    )
    artifact = ctx["annotated"]
    assert artifact.format == "vcf"
    text = Path(artifact.files["annotated"]).read_text(encoding="utf-8")
    assert "CSQ=stop_gained" in text


def test_variant_consequence_names_the_missing_reference_column(tmp_path):
    ctx = Ctx({"output": "annotated"}, tmp_path)
    with pytest.raises(StepError) as excinfo:
        VariantConsequenceStep().run(
            ctx, variant_artifacts(variant_fixtures(tmp_path, "chrA"))
        )
    message = str(excinfo.value)
    assert "variant_consequence" in message
    assert "column 'chr1' is not present" in message
    assert "available columns" in message
    assert "chrA" in message


# --------------------------------------------------------------- prodigal
def test_prodigal_genes_rejects_a_data_file_as_the_binary(tmp_path):
    data = tmp_path / "proteins.faa"
    data.write_text(">protein1\nMKV\n", encoding="utf-8")
    ctx = Ctx({"output": "genes", "prodigal_path": str(data)})
    with pytest.raises(StepError) as excinfo:
        ProdigalGenesStep().run(ctx, [sequence_form(["ATGCGTAAATGA"])])
    message = str(excinfo.value)
    assert "prodigal_genes" in message
    assert "is not an executable file" in message
    assert str(data) in message
