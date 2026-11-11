"""L2 (operator-level) tests for 12 Operon operators that lacked pytest coverage.

All inputs are SYNTHETIC and generated here (or written by the test into
``fixtures/l2_gap/`` next to this file).  Nothing is downloaded.

The test resolves fixtures relative to ``Path(__file__).parent`` so it can be
copied to ``tests/test_l2_gap.py`` together with
``tests/fixtures/l2_gap/`` without any path edits.  Set ``L2_GAP_FIXTURES``
or ``OPERON_REPO`` to override.

Run examples:
    python -m pytest /tmp/l2_gap/test_l2_gap.py -q
    python -m pytest /tmp/l2_gap/test_l2_gap.py::test_interval_stats -q
"""
from __future__ import annotations

import importlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(os.environ.get("OPERON_REPO", "/home/gavin/Operon-7015-native")).resolve()
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.core import FileArtifact, Form, StepError  # noqa: E402
from src.core.encoding import LabelEncoder  # noqa: E402

FIXTURES = Path(os.environ.get("L2_GAP_FIXTURES", Path(__file__).resolve().parent / "fixtures" / "l2_gap"))
FOLDSEEK_BIN = os.environ.get(
    "FOLDSEEK_BIN", "/home/gavin/tools/foldseek/foldseek/bin/foldseek"
)


# --------------------------------------------------------------------------- #
# Harness
# --------------------------------------------------------------------------- #
class Ctx(dict):
    """Minimal Context matching tests/test_extension182.py."""

    def __init__(self, params):
        super().__init__()
        self.step_params = dict(params)
        self.metadata = {}


def _run(module: str, class_name: str, params: dict, inputs, out_key: str = "out"):
    mod = importlib.import_module(f"src.task.step.steps.{module}")
    step = getattr(mod, class_name)()
    params = dict(params)
    params["output"] = out_key
    ctx = Ctx(params)
    step.run(ctx, list(inputs))
    return ctx[out_key], step.export(ctx)


def _labels(n: int, prefix: str) -> dict:
    return {f"{prefix}{i}": i for i in range(n)}


def _sequence_codes_form(seqs, alphabet_map, alphabet="dna"):
    """Form of DNA strings -> numeric code matrix with the sequence_codes info."""
    base_to_code = {b.upper(): int(c) for b, c in alphabet_map.items()}
    max_len = max(len(s) for s in seqs)
    data = np.full((len(seqs), max_len), np.nan, dtype=np.float32)
    for r, seq in enumerate(seqs):
        for c, base in enumerate(seq):
            data[r, c] = base_to_code[base.upper()]
    return Form(
        data=data,
        dims=["sequence", "position"],
        labels={"sequence": _labels(len(seqs), "seq"), "position": _labels(max_len, "p")},
        info={
            "representation": "sequence_codes",
            "alphabet": alphabet,
            "alphabet_map": dict(alphabet_map),
            "unknown_code": 4,
        },
    )


def _bed_form(rows, chrom_field="chrom", start_field="chromStart", end_field="chromEnd",
              region_dim="region", field_dim="field"):
    """rows: list of (chrom, start, end); chrom is label-encoded into a code column."""
    enc = LabelEncoder()
    codes = enc.fit_transform([r[0] for r in rows])
    data = np.zeros((len(rows), 3), dtype=np.float32)
    data[:, 0] = codes
    data[:, 1] = [r[1] for r in rows]
    data[:, 2] = [r[2] for r in rows]
    return Form(
        data=data,
        dims=[region_dim, field_dim],
        labels={
            region_dim: _labels(len(rows), "r"),
            field_dim: {chrom_field: 0, start_field: 1, end_field: 2},
        },
        info={"encoders": {field_dim: {chrom_field: enc}}},
    ), enc


def _gene_form(rows):
    """rows: (chrom, start, end, strand, type, attributes) for peak_nearest_gene."""
    dims = ["record", "field"]
    field_dim = "field"
    cols = {"seqid": 0, "start": 1, "end": 2, "strand": 3, "type": 4, "attributes": 5}
    encoders = {}
    data = np.zeros((len(rows), 6), dtype=np.float32)
    for name, idx in (("seqid", 0), ("strand", 3), ("type", 4), ("attributes", 5)):
        enc = LabelEncoder()
        data[:, idx] = enc.fit_transform([r[idx] for r in rows])
        encoders[name] = enc
    data[:, 1] = [r[1] for r in rows]
    data[:, 2] = [r[2] for r in rows]
    return Form(
        data=data,
        dims=dims,
        labels={
            "record": _labels(len(rows), "rec"),
            field_dim: dict(cols),
        },
        info={"encoders": {field_dim: encoders}},
    )


def _classifier_fixture(seed=7, n=24, d=5):
    rng = np.random.default_rng(seed)
    y = np.array([i % 2 for i in range(n)], dtype=np.float32)
    X = rng.normal(size=(n, d)).astype(np.float32)
    X[:, 0] += np.where(y == 0, -1.0, 1.0)
    X[:, 1] += np.where(y == 0, -0.5, 0.5)
    features = Form(
        data=X,
        dims=["sample", "feature"],
        labels={"sample": _labels(n, "s"), "feature": _labels(d, "f")},
        info={},
    )
    labels = Form(
        data=y.reshape(n, 1),
        dims=["sample", "label"],
        labels={"sample": _labels(n, "s"), "label": {"class": 0}},
        info={},
    )
    return features, labels


# --------------------------------------------------------------------------- #
# 1. gc_skew_profile
# --------------------------------------------------------------------------- #
def test_gc_skew_profile():
    seq = "GC" * 20 + "AT" * 20 + "GGCC" * 10  # 120 bp, synthetic
    form = _sequence_codes_form([seq], {"A": 0, "C": 1, "G": 2, "T": 3})
    out, exp = _run(
        "gc_skew_profile", "GcSkewProfileStep",
        {"window_size": 30, "step_size": 30}, [form],
    )
    assert out.dims == ["window", "statistic"]
    assert out.data.shape == (4, 7), out.data.shape
    stats = out.labels["statistic"]
    assert list(stats) == ["start", "end", "gc", "at", "gc_skew", "cumulative_skew", "cumulative_gc"]
    gc_col = stats["gc"]
    assert out.data[0, gc_col] == pytest.approx(1.0)
    assert out.data[0, stats["at"]] == pytest.approx(0.0)
    assert out.data[:, stats["start"]].tolist() == [0, 30, 60, 90]
    assert np.isfinite(out.data[:, stats["cumulative_gc"]]).all()
    assert exp["n_windows"] == 4
    assert exp["sequence_length"] == 120
    assert out.info["representation"] == "gc_skew_profile"

    with pytest.raises(StepError):
        _run(
            "gc_skew_profile", "GcSkewProfileStep",
            {"window_size": 30}, [_sequence_codes_form([seq, seq], {"A": 0, "C": 1, "G": 2, "T": 3})],
        )
    print("[gc_skew_profile] n_windows=4 sequence_length=120 first_gc=1.0")


# --------------------------------------------------------------------------- #
# 2. gene_list_to_hits
# --------------------------------------------------------------------------- #
def test_gene_list_to_hits():
    genes = ["g0", "g1", "g2", "g3", "g4", "g5"]
    terms = ["t0", "t1", "t2", "t3"]
    data = np.array([
        [1, 0, 1, 0],
        [0, 2, 0, 0],
        [1, 1, 0, 0],
        [0, 0, 3, 0],
        [0, 0, 0, 1],
        [1, 0, 0, 0],
    ], dtype=np.float32)
    universe = Form(
        data=data,
        dims=["gene", "go_term"],
        labels={"gene": {g: i for i, g in enumerate(genes)},
                "go_term": {t: i for i, t in enumerate(terms)}},
        info={},
    )
    out, exp = _run("gene_list_to_hits", "GeneListToHitsStep",
                    {"genes": ["g1", "g3"]}, [universe])
    assert out.dims == ["gene", "go_term"]
    assert out.data.shape == (2, 4)
    assert set(out.labels["gene"]) == {"g1", "g3"}
    row = out.labels["gene"]["g1"]
    assert out.data[row].tolist() == [0.0, 1.0, 0.0, 0.0]
    assert out.data[out.labels["gene"]["g3"]].tolist() == [0.0, 0.0, 1.0, 0.0]
    assert exp["n_universe_genes"] == 6
    assert exp["n_hit_genes"] == 2
    assert exp["n_hit_pairs"] == 2

    with pytest.raises(StepError):
        _run("gene_list_to_hits", "GeneListToHitsStep", {"genes": ["nope"]}, [universe])
    print("[gene_list_to_hits] n_hit_genes=2 n_hit_pairs=2")


# --------------------------------------------------------------------------- #
# 3. interval_stats
# --------------------------------------------------------------------------- #
def test_interval_stats():
    rows = [("chr1", 100, 200), ("chr1", 300, 450), ("chr2", 50, 150), ("chr3", 10, 20)]
    form, _enc = _bed_form(rows)
    out, exp = _run("interval_stats", "IntervalStatsStep", {}, [form])
    assert out.dims == ["chrom", "statistic"]
    stats = out.labels["statistic"]
    assert list(stats) == ["n_intervals", "total_bp", "mean_length", "median_length",
                           "min_length", "max_length", "span_bp"]
    chrom_rows = out.labels["chrom"]
    assert set(chrom_rows) == {"chr1", "chr2", "chr3"}
    assert out.data.shape == (3, 7)
    chr1 = out.data[chrom_rows["chr1"]]
    assert chr1[stats["n_intervals"]] == 2
    assert chr1[stats["total_bp"]] == 250
    assert chr1[stats["span_bp"]] == 350
    assert exp["n_intervals"] == 4
    assert exp["n_chromosomes"] == 3
    assert exp["total_bp"] == 360
    # Implementation semantics: chr1 median 125, chr2 100, chr3 10 -> mean 235/3.
    assert exp["median_interval_length"] == pytest.approx(235.0 / 3.0)
    assert chr1[stats["median_length"]] == pytest.approx(125.0)

    bad = Form(data=form.data, dims=form.dims, labels=form.labels, info={})
    with pytest.raises(StepError):
        _run("interval_stats", "IntervalStatsStep", {}, [bad])
    print("[interval_stats] n_chromosomes=3 n_intervals=4 total_bp=360 "
          "median_interval_length=78.333 (mean of per-chrom medians)")


# --------------------------------------------------------------------------- #
# 4. interval_overlap
# --------------------------------------------------------------------------- #
def test_interval_overlap():
    a_rows = [("chr1", 100, 200), ("chr1", 500, 600)]
    b_rows = [("chr1", 150, 250), ("chr2", 10, 20)]
    a_form, _ = _bed_form(a_rows)
    b_form, _ = _bed_form(b_rows)
    out, exp = _run("interval_overlap", "IntervalOverlapStep",
                    {"min_overlap": 1}, [a_form, b_form])
    assert out.dims == ["pair", "statistic"]
    stats = out.labels["statistic"]
    assert list(stats) == ["overlap_start", "overlap_end", "overlap_length",
                           "a_length", "b_length", "overlap_fraction_a", "overlap_fraction_b"]
    assert out.data.shape == (1, 7), out.data.shape
    row = out.data[0]
    assert row[stats["overlap_start"]] == 150
    assert row[stats["overlap_end"]] == 200
    assert row[stats["overlap_length"]] == 50
    assert row[stats["a_length"]] == 100
    assert row[stats["b_length"]] == 100
    assert row[stats["overlap_fraction_a"]] == pytest.approx(0.5)
    assert row[stats["overlap_fraction_b"]] == pytest.approx(0.5)
    assert exp["n_pairs"] == 1
    assert exp["n_chromosomes_shared"] == 1
    assert exp["total_overlap_bp"] == 50

    out2, exp2 = _run("interval_overlap", "IntervalOverlapStep",
                      {"min_overlap": 60}, [a_form, b_form])
    assert out2.data.shape[0] == 0 and exp2["n_pairs"] == 0
    print("[interval_overlap] n_pairs=1 total_overlap_bp=50; min_overlap=60 -> 0 pairs")


# --------------------------------------------------------------------------- #
# 5. motif_scan
# --------------------------------------------------------------------------- #
def test_motif_scan():
    seqs = ["ACGTACGTACGT", "AAAACGTTTT"]  # synthetic
    form = _sequence_codes_form(seqs, {"A": 0, "C": 1, "G": 2, "T": 3})
    out, exp = _run("motif_scan", "MotifScanStep",
                    {"motifs": {"acgt": "ACGT", "cg": "CG"}}, [form])
    assert out.dims[0] == "motif"
    assert out.data.shape == (2, 2), out.data.shape
    assert list(out.labels["motif"]) == ["acgt", "cg"]
    assert out.data[out.labels["motif"]["acgt"]].tolist() == [3.0, 1.0]
    assert out.data[out.labels["motif"]["cg"]].tolist() == [3.0, 1.0]
    assert exp["n_motifs"] == 2
    assert exp["n_sequences"] == 2
    assert exp["total_hits"] == 8

    with pytest.raises(StepError):
        _run("motif_scan", "MotifScanStep", {"motifs": {}}, [form])
    print("[motif_scan] n_motifs=2 n_sequences=2 total_hits=8")


# --------------------------------------------------------------------------- #
# 6. peak_nearest_gene
# --------------------------------------------------------------------------- #
def test_peak_nearest_gene():
    peaks = [("chr1", 1500, 1600), ("chr1", 5500, 5600), ("chr1", 10000, 10100)]
    genes = [
        ("chr1", 1000, 2000, "+", "gene", "gene_id=geneA"),
        ("chr1", 5000, 6000, "-", "gene", "gene_id=geneB"),
    ]
    a_form, _ = _bed_form(peaks)
    b_form = _gene_form(genes)
    out, exp = _run("peak_nearest_gene", "PeakNearestGeneStep",
                    {"feature_type": "gene", "max_distance": 10000},
                    [a_form, b_form])
    assert out.dims == ["peak", "statistic"]
    stats = out.labels["statistic"]
    assert list(stats) == ["distance", "gene_start", "gene_end", "gene_length", "strand"]
    assert out.data.shape == (3, 5), out.data.shape
    rows = [out.data[i] for i in range(out.data.shape[0])]
    assert rows[0][stats["distance"]] == 0
    assert rows[0][stats["gene_start"]] == 1000
    assert rows[0][stats["gene_end"]] == 2000
    assert rows[0][stats["gene_length"]] == 1000
    assert rows[1][stats["distance"]] == 0
    assert rows[1][stats["gene_start"]] == 5000
    assert rows[2][stats["distance"]] == 4000
    assert rows[2][stats["gene_start"]] == 5000
    assert exp["n_peaks"] == 3
    assert exp["n_kept"] == 3
    assert exp["n_overlapping_genes"] == 2
    print("[peak_nearest_gene] n_peaks=3 distances=[0,0,4000] overlapping=2")


# --------------------------------------------------------------------------- #
# 7-10. ML classifiers
# --------------------------------------------------------------------------- #
def _run_classifier(module, class_name, extra=None, expect_accuracy=0.8):
    features, labels = _classifier_fixture()
    params = {
        "target_label": "class",
        "test_size": 0.25,
        "cv_folds": 3,
        "random_state": 0,
        "scale": True,
    }
    params.update(extra or {})
    out, exp = _run(module, class_name, params, [features, labels])
    assert out.dims == ["feature", "statistic"], out.dims
    assert out.data.shape == (5, 2), out.data.shape
    assert list(out.labels["statistic"]) == ["importance", "signed_score"]
    assert exp["n_samples"] == 24
    assert exp["n_features"] == 5
    assert exp["n_train"] == 18
    assert exp["n_test"] == 6
    assert exp["classes"] == ["0", "1"]
    assert len(exp["cv_scores"]) == 3, exp["cv_scores"]
    assert exp["cv_mean"] is not None
    assert exp["test_accuracy"] >= expect_accuracy, exp
    assert out.info["missing_code"] != out.info["missing_code"]  # NaN
    return exp


def test_logistic_regression():
    exp = _run_classifier("logistic_regression", "LogisticRegressionStep",
                          {"C": 1.0, "penalty": "l2"})
    print(f"[logistic_regression] acc={exp['test_accuracy']:.3f} cv={exp['cv_mean']:.3f}")


def test_random_forest_classifier():
    exp = _run_classifier("random_forest_classifier", "RandomForestClassifierStep",
                          {"n_estimators": 25, "max_depth": 3})
    print(f"[random_forest_classifier] acc={exp['test_accuracy']:.3f} cv={exp['cv_mean']:.3f}")


def test_svm_classifier():
    exp = _run_classifier("svm_classifier", "SvmClassifierStep",
                          {"C": 1.0, "class_weight": None})
    print(f"[svm_classifier] acc={exp['test_accuracy']:.3f} cv={exp['cv_mean']:.3f}")


def test_gradient_boosting_classifier():
    exp = _run_classifier("gradient_boosting_classifier", "GradientBoostingClassifierStep",
                          {"n_estimators": 25, "learning_rate": 0.1, "max_depth": 2})
    print(f"[gradient_boosting_classifier] acc={exp['test_accuracy']:.3f} cv={exp['cv_mean']:.3f}")


# --------------------------------------------------------------------------- #
# 11. atac_peak_call (needs samtools to build a tiny BAM)
# --------------------------------------------------------------------------- #
def _build_atac_bam(path: Path):
    if shutil.which("samtools") is None:
        pytest.skip("samtools not on PATH: cannot build synthetic BAM")
    path.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(11)
    seq = "A" * 150
    lines = ["@HD\tVN:1.6\tSO:coordinate", "@SQ\tSN:chr1\tLN:20000"]
    for i in range(200):  # 200 synthetic fragments around 4.1kb, tlen 150
        start = 4000 + int(rng.integers(0, 400))
        flag = 0x1 | 0x40  # paired + first-in-pair
        lines.append(
            f"frag{i}\t{flag}\tchr1\t{start + 1}\t60\t150M\t=\t{start + 1 + 150}\t150\t{seq}\t{'I' * 150}"
        )
    sam = path.with_suffix(".sam")
    sam.write_text("\n".join(lines) + "\n")
    raw = path.with_name("raw.bam")
    subprocess.run(["samtools", "view", "-b", "-o", str(raw), str(sam)], check=True,
                   capture_output=True)
    subprocess.run(["samtools", "sort", "-o", str(path), str(raw)], check=True,
                   capture_output=True)
    subprocess.run(["samtools", "index", str(path)], check=True, capture_output=True)
    return path


def test_atac_peak_call(tmp_path):
    bam = _build_atac_bam(FIXTURES / "atac" / "synthetic_chr1.bam")
    artifact = FileArtifact(format="bam", files={"bam": str(bam)}, info={})
    out, exp = _run("atac_peak_call", "AtacPeakCallStep",
                    {"qvalue": 0.05, "min_length": 100, "extension_bp": 260,
                     "min_mapq": 30, "max_fragments": 0}, [artifact])
    assert out.dims == ["peak", "field"]
    assert out.data.shape[1] == 7
    stats = out.labels["field"]
    assert list(stats) == ["start", "end", "length", "summit", "count", "score", "fold_enrichment"]
    assert exp["n_fragments"] == 200
    assert exp["n_peaks"] >= 1, exp
    starts = out.data[:, stats["start"]]
    assert any(3900 <= s <= 4400 for s in starts), starts.tolist()
    assert np.isfinite(out.data).all()
    assert exp["peak_bp"] > 0
    print(f"[atac_peak_call] n_peaks={exp['n_peaks']} n_fragments=200 peak_bp={exp['peak_bp']}")


# --------------------------------------------------------------------------- #
# 12. foldseek_cluster (real binary + 2 small PDBs)
# --------------------------------------------------------------------------- #
def test_foldseek_cluster():
    struct_dir = FIXTURES / "foldseek"
    pdbs = sorted(struct_dir.glob("*.pdb"))
    if len(pdbs) < 2:
        pytest.skip(f"need 2 PDBs in {struct_dir}, found {len(pdbs)}")
    if not Path(FOLDSEEK_BIN).is_file():
        pytest.skip(f"foldseek binary missing: {FOLDSEEK_BIN}")
    structures = "\n".join(p.name for p in pdbs)
    out, exp = _run("foldseek_cluster", "FoldseekClusterStep",
                    {"structure_dir": str(struct_dir),
                     "foldseek_path": FOLDSEEK_BIN,
                     "tmscore_threshold": 0.6,
                     "coverage": 0.8,
                     "timeout_seconds": 300}, [])
    assert out.dims == ["structure", "statistic"]
    stats = out.labels["statistic"]
    assert list(stats) == ["cluster_id", "cluster_size", "is_representative"]
    assert out.data.shape[1] == 3
    n_struct = out.data.shape[0]
    assert n_struct >= 2, structures
    assert exp["n_structures"] == n_struct
    assert exp["n_clusters"] >= 1
    assert set(out.data[:, stats["is_representative"]].astype(int)).issubset({0, 1})
    cluster_ids = out.data[:, stats["cluster_id"]].astype(int)
    sizes = out.data[:, stats["cluster_size"]].astype(int)
    # One row per structure; cluster_size is repeated for every member of a cluster.
    assert len(set(cluster_ids.tolist())) == exp["n_clusters"]
    for cid in set(cluster_ids.tolist()):
        members = cluster_ids == cid
        assert (sizes[members] == members.sum()).all()
    assert int(out.data[:, stats["is_representative"]].sum()) == exp["n_clusters"]
    assert int(sizes.max()) >= 2, "expected at least one multi-member cluster"
    print(f"[foldseek_cluster] n_structures={n_struct} n_clusters={exp['n_clusters']} "
          f"cluster_sizes={sorted(set(sizes.tolist()))}")
