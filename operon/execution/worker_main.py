"""Invocation ABI worker, using the normal frozen-plugin/logging bootstrap."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import traceback

from operon.contracts.base import ContractModel
from operon.contracts.run_plan import InvocationSpec, NonNegativeInt, validate_relative_path
from pydantic import Field, field_validator, model_validator


class WorkerInvocation(ContractModel):
    format: str
    schema_version: int
    invocation: InvocationSpec
    run_id: str
    unit_id: str
    attempt_id: str
    fence: NonNegativeInt
    task_ref: str
    parameters_ref: dict
    environment: dict[str, str]
    memory_bytes: NonNegativeInt
    threads: NonNegativeInt
    output_dir: str | None = None
    native_runtime_ref: str | None = None
    native_runtime_digest: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')

    _relative = field_validator('task_ref')(validate_relative_path)

    @model_validator(mode='after')
    def _runtime_reference(self):
        if (self.native_runtime_ref is None) != (self.native_runtime_digest is None):
            raise ValueError('Native runtime reference and digest are required together')
        if self.native_runtime_ref is not None:
            validate_relative_path(self.native_runtime_ref)
        return self


def read_native_runtime(directory, value):
    if value.native_runtime_ref is None:
        return None  # Existing K02 JobService invocations keep plugins.lock.
    directory = Path(directory).resolve()
    raw_path = directory / value.native_runtime_ref
    path = raw_path.resolve()
    if not path.is_relative_to(directory) or raw_path.is_symlink() or not path.is_file():
        raise ValueError('Native runtime snapshot escapes the owned attempt')
    if path.stat().st_size > 64 * 1024**2:
        raise ValueError('Native runtime snapshot exceeds the bounded input size')
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != value.native_runtime_digest:
        raise ValueError('Native runtime snapshot hash differs from the prepared invocation')
    from .native_bootstrap import NativeRuntimeSnapshot
    return NativeRuntimeSnapshot.model_validate(json.loads(content)).model_dump(mode='json')


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--invocation', type=Path, required=True)
    path = parser.parse_args(argv).invocation.resolve()
    value = WorkerInvocation.model_validate_json(path.read_text(encoding='utf-8'))
    if value.format != 'operon.invocation' or value.schema_version != 1:
        raise ValueError('Unsupported invocation format/version')
    if value.invocation.kind != 'native' or value.invocation.entrypoint != 'operon.execution.worker_main':
        raise ValueError('This worker accepts only the native Context bridge invocation')
    task_path = (path.parent / value.task_ref).resolve()
    if not task_path.is_relative_to(path.parent):
        raise ValueError('Task file escapes the attempt directory')
    if task_path.name != 'task.yaml':
        raise ValueError('Native Context bridge requires the prepared task.yaml manifest')
    out_dir = Path(value.output_dir).resolve() if value.output_dir else path.parent / 'outputs'
    status, error = 'failed', None
    try:
        from operon.worker import execute_task
        native_runtime = read_native_runtime(path.parent, value)
        overrides = {'budget_mb': value.memory_bytes / (1024 * 1024), 'enabled': True} if value.memory_bytes else None
        execute_task(task_path.parent, out_dir, overrides=overrides, use_bridge=True, native_runtime=native_runtime)
        status = 'complete'
    except BaseException as exc:
        error = f'{type(exc).__name__}: {exc}'
        traceback.print_exc(file=sys.stderr)
    finally:
        from .context_bridge import write_output_manifest
        output_manifest = path.parent / value.invocation.output_manifest
        if not output_manifest.resolve().is_relative_to(path.parent):
            raise ValueError('Output manifest escapes the attempt directory')
        output_manifest.parent.mkdir(parents=True, exist_ok=True)
        write_output_manifest(out_dir, output_manifest, status=status, error=error)
    return 0 if status == 'complete' else 1


if __name__ == '__main__':
    raise SystemExit(main())
