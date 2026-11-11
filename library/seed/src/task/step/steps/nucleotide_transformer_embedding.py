"""Mean-pooled Nucleotide Transformer embeddings."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.step.base import Step

from ._b91_common import embed, row_names, strings
from ._native_results import output_directory, remember_native, result_file


class NucleotideTransformerEmbeddingStep(Step):
    parameters_file = "nucleotide_transformer_embedding.NucleotideTransformerEmbeddingStep.parameters.json"
    definition = {'protocol_version': 3, 'protocol_revision': '3.7', 'kind': 'operator', 'id': 'nucleotide_transformer_embedding', 'version': '1.0.0', 'title': 'Nucleotide Transformer embeddings', 'description': 'Mean-pooled 512-d embeddings from the Nucleotide Transformer v2 50M multi-species model.', 'category': 'Machine Learning', 'icon': 'dna', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': []}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}, 'dependencies': ['numpy>=1.24', 'torch>=2.4,<3', 'transformers>=4.50,<5'], 'dependency_imports': ['torch', 'transformers']}

    def run(self, ctx, inputs):
        params = ctx.step_params
        form = inputs[0]
        seqs = strings(form, form.dims[1], params["sequence_column"])
        mat = embed(seqs, params.get("model_path", ""), int(params.get("max_length", 512)), int(params.get("batch_size", 8)))
        mat = np.round(mat, 3)
        dim0 = form.dims[0]
        labels = {
            dim0: {name: i for i, name in enumerate(row_names(form))},
            "embedding": {str(i): i for i in range(mat.shape[1])},
        }
        out_name = params["output"]
        ctx[out_name] = Form(mat, dims=[dim0, "embedding"], labels=labels, info={"model": "InstaDeepAI/nucleotide-transformer-v2-50m-multi-species"})
        names = row_names(form)
        path = output_directory(ctx, "nucleotide_transformer_embedding") / "embeddings.csv"
        lines = ["sequence," + ",".join(f"embedding_{i}" for i in range(mat.shape[1]))]
        for name, row in zip(names, mat):
            lines.append(str(name) + "," + ",".join(f"{float(v):.6g}" for v in row))
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        result_files = [result_file("embeddings", path, "csv", "Nucleotide Transformer embeddings")]
        remember_native(ctx, out_name, result_files)
        self._result_files = result_files
        self._export_data = {"shape": [int(mat.shape[0]), int(mat.shape[1])], "model": "InstaDeepAI/nucleotide-transformer-v2-50m-multi-species"}

    def export(self, ctx):
        data = dict(getattr(self, "_export_data", {}))
        data["result_files"] = getattr(self, "_result_files", [])
        return data
