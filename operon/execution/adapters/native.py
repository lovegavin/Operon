"""Native SDK invocation adapter.

It prepares an attempt-local task directory and delegates command construction to
the existing process executor.  Inputs remain path references; no Form data is
copied across the interpreter boundary by this adapter.
"""
from __future__ import annotations

import json
import hashlib
from pathlib import Path
import sys
from typing import Any

import yaml

from operon.bytecode import io_path
from operon.contracts.run_plan import InvocationSpec
from ..invocation import ExitReceipt, InvocationContext, OutputManifest, PreparedInvocation


class NativeInvocationAdapter:
    def prepare(self, invocation: InvocationSpec, context: InvocationContext) -> PreparedInvocation:
        task_dir = context.attempt_root / 'task'
        output_dir = context.attempt_root / 'outputs'
        task_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        manifest = context.payload.get('task_manifest')
        if not isinstance(manifest, dict):
            raise ValueError('Native invocation payload is missing task_manifest')
        manifest = json.loads(json.dumps(manifest, ensure_ascii=False, allow_nan=False))
        # Explicit input bindings are independent of the frozen plan.  They
        # replace source paths without copying scientific data.
        bindings = context.payload.get('input_bindings') or {}
        for name, path in bindings.items():
            if name not in manifest.get('sources', {}):
                raise ValueError(f'Input binding references unknown source: {name}')
            manifest['sources'][name]['path'] = str(path)
        if context.memory_bytes:
            memory = manifest.setdefault('runtime', {}).setdefault('memory', {})
            memory.setdefault('enabled', True)
        task_path = task_dir / 'task.yaml'
        io_path(task_dir).mkdir(parents=True, exist_ok=True)
        task_path.write_text(yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True),
                             encoding='utf-8')
        invocation_path = context.attempt_root / 'invocation.json'
        value = {
            'format': 'operon.invocation', 'schema_version': 1,
            'invocation': invocation.model_dump(mode='json'),
            'run_id': context.run_id, 'unit_id': context.unit_id,
            'attempt_id': context.attempt_id, 'fence': context.fence,
            'task_ref': task_path.relative_to(context.attempt_root).as_posix(),
            'parameters_ref': invocation.parameters_ref.model_dump(mode='json'),
            'environment': dict(context.environment),
            'memory_bytes': context.memory_bytes, 'threads': context.threads,
        }
        if 'native_descriptors' in context.payload:
            from operon.contracts.base import canonical_json
            from ..native_bootstrap import NativeRuntimeSnapshot
            snapshot = NativeRuntimeSnapshot(descriptors=context.payload['native_descriptors'],
                implementations=context.payload.get('native_implementations', {}),
                audit_descriptors=context.payload.get('native_descriptor_audit', {}),
                isolation_targets=context.payload.get('native_isolation_targets', {}),
                environment_requirement_digest=context.payload.get('native_environment_requirement_digest'))
            content = (canonical_json(snapshot) + '\n').encode('utf-8')
            runtime_path = context.attempt_root / 'native-runtime.json'
            runtime_path.write_bytes(content)
            value['native_runtime_ref'] = runtime_path.name
            value['native_runtime_digest'] = hashlib.sha256(content).hexdigest()
        invocation_path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
        command = (sys.executable, '-m', 'operon.execution.worker_main', '--invocation',
                   str(invocation_path))
        environment = dict(context.environment)
        environment.setdefault('OPERON_ATTEMPT_ID', context.attempt_id)
        environment.setdefault('OPERON_RUN_ID', context.run_id)
        environment.setdefault('OPERON_RESOURCE_FENCE', str(context.fence))
        environment.setdefault('PYTHONNOUSERSITE', '1')
        environment.setdefault('PYTHONPATH', str(Path(__file__).resolve().parents[3]))
        return PreparedInvocation(spec=invocation, context=context, task_dir=task_dir,
                                  task_manifest_path=task_path, output_dir=output_dir,
                                  command=command, environment=environment)

    def collect(self, prepared: PreparedInvocation, exit_receipt: ExitReceipt) -> OutputManifest:
        manifest_path = prepared.context.attempt_root / prepared.spec.output_manifest
        summary_path = prepared.output_dir / 'run_summary.json'
        files = ()
        try:
            if exit_receipt.exit_code != 0 or exit_receipt.state != 'succeeded' or exit_receipt.tree_alive:
                raise ValueError(exit_receipt.error or 'Successful process-tree exit has not been confirmed')
            value = json.loads(manifest_path.read_text(encoding='utf-8'))
            if (value.get('format'), value.get('schema_version'), value.get('status')) != (
                    'operon.output-manifest', 1, 'complete'):
                raise ValueError('Worker output manifest is not complete')
            root = prepared.output_dir.resolve()
            if Path(value['output_dir']).resolve() != root:
                raise ValueError('Output manifest belongs to another output directory')
            files = tuple(value['files'])
            if len(set(files)) != len(files) or 'run_summary.json' not in files:
                raise ValueError('Output file inventory is invalid')
            inventory = {item.relative_to(root).as_posix() for item in root.rglob('*') if item.is_file()}
            if inventory != set(files) or set(value['hashes']) != set(files):
                raise ValueError('Output file inventory changed after worker completion')
            from operon.contracts.run_plan import validate_relative_path
            for name in files:
                validate_relative_path(name)
                path = (root / name).resolve()
                if not path.is_relative_to(root):
                    raise ValueError('Output file escapes its owned directory')
                record = value['hashes'][name]
                digest = hashlib.sha256()
                with path.open('rb') as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b''):
                        digest.update(block)
                if path.stat().st_size != record['size'] or digest.hexdigest() != record['sha256']:
                    raise ValueError(f'Output file failed integrity verification: {name}')
            summary = json.loads(summary_path.read_text(encoding='utf-8'))
            if summary.get('status') != 'complete':
                raise ValueError('Run summary is not complete')
        except (OSError, ValueError, KeyError, TypeError) as exc:
            return OutputManifest('failed', str(prepared.output_dir), None, files, str(exc))
        # Collection is read-only: never fabricate/repair the worker's evidence.
        return OutputManifest('complete', str(prepared.output_dir), str(summary_path), files)
