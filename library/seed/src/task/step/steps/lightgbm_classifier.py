"""Operator lightgbm_classifier."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.core.errors import StepError
from src.task.step.base import Step

from src.task.step.steps._b90_common import column, matrix, table


class LightgbmClassifierStep(Step):
    parameters_file = "lightgbm_classifier.LightgbmClassifierStep.parameters.json"

    definition = {'id': 'lightgbm_classifier', 'version': '1.0.0', 'title': 'LightGBM binary classifier', 'description': 'Fit a deterministic LightGBM gradient-boosted classifier and report training diagnostics.', 'category': 'Machine Learning', 'kind': 'operator', 'protocol_version': 3, 'protocol_revision': '3.7', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': []}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}}

    def run(self, ctx, inputs):
        """Execute the operator."""
        import lightgbm as lgb

        params = dict(ctx.step_params)
        label_column = str(params.get("label_column", "label"))
        names = inputs[0].labels.get(inputs[0].dims[1], {})
        if label_column not in names:
            raise StepError("input table has no label column %r" % label_column)
        data = matrix(inputs[0])
        feature_idx = [v for k, v in sorted(names.items(), key=lambda kv: kv[1]) if k != label_column]
        y = data[:, names[label_column]].astype(int)
        X = data[:, feature_idx]
        n_estimators = int(params.get("n_estimators", 30))
        model = lgb.LGBMClassifier(
            n_estimators=n_estimators,
            num_leaves=int(params.get("num_leaves", 7)),
            learning_rate=float(params.get("learning_rate", 0.3)),
            min_child_samples=int(params.get("min_child_samples", 1)),
            random_state=int(params.get("seed", 7)),
            deterministic=True,
            force_row_wise=True,
            n_jobs=1,
            verbose=-1,
        )
        model.fit(X, y)
        prob = model.predict_proba(X)
        pred = model.predict(X)
        acc = float((pred == y).mean())
        eps = 1e-12
        ll = float(-np.mean(np.log(np.clip(prob[np.arange(len(y)), y], eps, 1.0))))
        ctx[params["output"]] = table(
            {"accuracy": acc, "log_loss": ll, "n_train": len(y), "n_classes": int(len(np.unique(y))),
             "n_features": len(feature_idx), "n_estimators": n_estimators},
            ["accuracy", "log_loss", "n_train", "n_classes", "n_features", "n_estimators"],
        )
