"""Dinucleotide composition and CpG observed/expected ratio for nucleotide sequences."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step
from src.task.step.steps._sequence_common import decode_sequences

DINUCLEOTIDES = (
    "AA", "AC", "AG", "AT",
    "CA", "CC", "CG", "CT",
    "GA", "GC", "GG", "GT",
    "TA", "TC", "TG", "TT",
)
STATISTICS = ("count", "frequency", "cpg_observed_expected")
ACGT = "ACGT"


def dinucleotide_profile(sequences: list[str]) -> dict:
    """Count overlapping dinucleotides over ACGT-only sequence content."""
    counts = dict.fromkeys(DINUCLEOTIDES, 0)
    bases = dict.fromkeys(ACGT, 0)
    windows = 0
    for sequence in sequences:
        seq = "".join(char for char in str(sequence).upper() if char in ACGT)
        windows += max(0, len(seq) - 1)
        for char in seq:
            bases[char] += 1
        for index in range(len(seq) - 1):
            counts[seq[index:index + 2]] += 1
    total_bases = sum(bases.values())
    freq_c = bases["C"] / total_bases if total_bases else 0.0
    freq_g = bases["G"] / total_bases if total_bases else 0.0
    expected_cpg = freq_c * freq_g
    observed_cpg = counts["CG"] / windows if windows else 0.0
    cpg_ratio = observed_cpg / expected_cpg if expected_cpg > 0.0 else 0.0
    rows = []
    for name in DINUCLEOTIDES:
        frequency = counts[name] / windows if windows else 0.0
        rows.append([
            float(counts[name]),
            float(frequency),
            float(cpg_ratio) if name == "CG" else 0.0,
        ])
    return {
        "rows": rows,
        "windows": windows,
        "bases": total_bases,
        "cpg_ratio": float(cpg_ratio),
    }


class SequenceDinucleotideFrequencyStep(Step):
    provider = "operon-core"
    parameters_file = "sequence_dinucleotide_frequency.SequenceDinucleotideFrequencyStep.parameters.json"

    definition = {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "sequence_dinucleotide_frequency",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Dinucleotide frequency",
        "description": "Counts overlapping dinucleotides, reports their frequencies and the CpG observed/expected ratio.",
        "category": "Machine Learning",
        "icon": "GridNine",
        "inputs_arity": 1,
        "output_parameter": "output",
        "outputs": [],
        "contracts": {
            "version": 1,
            "inputs": [{
                "version": 1,
                "numeric": True,
                "ndim": 2,
                "dims": [
                    {"param": "sequence_dim", "default": "sequence"},
                    {"param": "position_dim", "default": "position"},
                ],
                "labels": [],
                "parallel": [],
                "info": {
                    "representation": {"type": "string", "const": "sequence_codes"},
                },
            }],
            "output": {
                "mode": "declare",
                "schema": {
                    "ndim": 2,
                    "numeric": True,
                    "info_open": True,
                    "axis_info_open": True,
                },
            },
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": [],
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
            "outputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
        },
    }

    def run(self, ctx, inputs) -> None:
        if not inputs:
            raise StepError("sequence_dinucleotide_frequency: a sequence form input is required")
        form = inputs[0]
        params = ctx.step_params
        sequence_dim = str(params.get("sequence_dim") or "sequence")
        position_dim = str(params.get("position_dim") or "position")
        out_name = str(params.get("output") or "dinucleotide_frequency")

        if len(form.dims) != 2 or list(form.dims) != [sequence_dim, position_dim]:
            raise StepError(
                "sequence_dinucleotide_frequency: a sequence form with dims "
                f"[{sequence_dim}, {position_dim}] is required, got {list(form.dims)}"
            )

        sequences = decode_sequences(form, sequence_dim, position_dim)
        profile = dinucleotide_profile(sequences)
        output = Form(
            data=np.asarray(profile["rows"], dtype=np.float64),
            dims=["dinucleotide", "statistic"],
            labels={
                "dinucleotide": {name: index for index, name in enumerate(DINUCLEOTIDES)},
                "statistic": {name: index for index, name in enumerate(STATISTICS)},
            },
            info={
                "missing_code": float("nan"),
                "alphabet": ACGT,
                "n_sequences": len(sequences),
                "n_windows": profile["windows"],
                "n_bases": profile["bases"],
                "cpg_observed_expected": profile["cpg_ratio"],
            },
            axis_info={},
        )
        output.validate()
        ctx[out_name] = output
        self._export_data = {
            "n_sequences": len(sequences),
            "n_windows": profile["windows"],
            "n_bases": profile["bases"],
            "cpg_observed_expected": profile["cpg_ratio"],
        }
        print(
            f"[sequence_dinucleotide_frequency] {len(sequences)} sequences, "
            f"{profile['windows']} dinucleotide windows, {profile['bases']} bases"
        )

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
