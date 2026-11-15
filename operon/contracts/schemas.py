"""Generated wire schemas and stable schema bundle."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .run_plan import (ArtifactRef, AttemptReceipt, EnvironmentRequirement, RunPlan,
                       StorageRef)
from .workflow import FrozenParameters, WorkflowSpec
from .plan_operations import PlanCompileRequest, PlanSubmitRequest, PlanExecutionBinding
from .plan_export import PlanExportRequest


PUBLIC_MODELS = {
    'run-plan-v1': RunPlan,
    'workflow-v2': WorkflowSpec,
    'frozen-parameters-v1': FrozenParameters,
    'environment-requirement-v1': EnvironmentRequirement,
    'attempt-receipt-v1': AttemptReceipt,
    'artifact-ref-v1': ArtifactRef,
    'storage-ref-v1': StorageRef,
    'plan-compile-request-v1': PlanCompileRequest,
    'plan-submit-request-v1': PlanSubmitRequest,
    'plan-execution-binding-v1': PlanExecutionBinding,
    'plan-export-request-v1': PlanExportRequest,
}


def schemas() -> dict[str, dict[str, Any]]:
    return {name: model.model_json_schema(mode='validation')
            for name, model in PUBLIC_MODELS.items()}


def write_schemas(directory: str | Path) -> list[Path]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    for name, schema in schemas().items():
        path = directory / f'{name}.json'
        import json
        path.write_text(json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + '\n',
                        encoding='utf-8')
        written.append(path)
    return written
