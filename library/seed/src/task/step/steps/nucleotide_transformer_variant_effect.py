"""Nucleotide Transformer variant effect from ref/alt windows."""
from __future__ import annotations

import numpy as np

from src.task.step.base import Step

from ._b91_common import embed, strings, table
from ._native_results import output_directory, remember_native, result_file


class NucleotideTransformerVariantEffectStep(Step):
    parameters_file = "nucleotide_transformer_variant_effect.NucleotideTransformerVariantEffectStep.parameters.json"
    definition = {'protocol_version': 3, 'protocol_revision': '3.7', 'kind': 'operator', 'id': 'nucleotide_transformer_variant_effect', 'version': '1.0.0', 'title': 'Nucleotide Transformer variant effect', 'description': 'Embeds reference and alternate windows and reports cosine distance and embedding shift.', 'category': 'Machine Learning', 'icon': 'dna', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': []}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}, 'dependencies': ['numpy>=1.24', 'torch>=2.4,<3', 'transformers>=4.50,<5'], 'dependency_imports': ['torch', 'transformers']}

    def run(self, ctx, inputs):
        params = ctx.step_params
        form = inputs[0]
        refs = strings(form, form.dims[1], params["ref_column"])
        alts = strings(form, form.dims[1], params["alt_column"])
        path = params.get("model_path", "")
        max_len = int(params.get("max_length", 512))
        a = embed(refs, path, max_len, 8)
        b = embed(alts, path, max_len, 8)
        na = np.linalg.norm(a, axis=1)
        nb = np.linalg.norm(b, axis=1)
        cos = np.sum(a * b, axis=1) / np.maximum(na * nb, 1e-12)
        dist = np.linalg.norm(a - b, axis=1)
        dn = np.linalg.norm(a, axis=1) - np.linalg.norm(b, axis=1)
        out = table(["variant", "cosine_shift"], {
            "ref_norm": na.tolist(), "alt_norm": nb.tolist(), "cosine": cos.tolist(),
            "euclidean": dist.tolist(), "norm_delta": dn.tolist(),
        }, ["ref_norm", "alt_norm", "cosine", "euclidean", "norm_delta"])
        out.data[:] = np.round(out.data, 3)
        out_name = params["output"]
        ctx[out_name] = out
        path = output_directory(ctx, "nucleotide_transformer_variant_effect") / "variant_effect.csv"
        header = ["variant"] + list(out.labels[out.dims[1]].keys())
        lines = [",".join(header)]
        for i, name in enumerate(out.labels[out.dims[0]]):
            lines.append(str(name) + "," + ",".join(f"{float(v):.6g}" for v in out.data[i]))
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        result_files = [result_file("variant_effect", path, "csv", "Nucleotide Transformer variant effect")]
        remember_native(ctx, out_name, result_files)
        self._result_files = result_files
        self._export_data = {"rows": int(out.data.shape[0]), "columns": int(out.data.shape[1])}

    def export(self, ctx):
        data = dict(getattr(self, "_export_data", {}))
        data["result_files"] = getattr(self, "_result_files", [])
        return data
