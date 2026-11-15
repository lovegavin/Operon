"""Literal argv adapters for Python, R and native executables.

Every required executable comes from a verified generation. Values are resolved
as separate argv items; shells and arbitrary JSON-to-code interpolation are not
used. The existing coordinator/supervisor controls execution and cancellation.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re

from operon.contracts.base import ContractError, canonical_json
from operon.engine.fs import atomic_json
from operon.environment_store.builders import isolated_environment
from operon.environment_store.verification import confined, file_digest
from ..invocation import PreparedInvocation, OutputManifest
from ..codecs import file_reference, validate_reference
from operon.bytecode import io_path, executable_path
from ..foreign_paths import r_path, validate_r_generation


def resolve_argv(tokens, *, inputs, outputs, parameters, resources):
    values = {'input': inputs, 'output': outputs, 'parameter': parameters, 'resource': resources}
    result = []
    for token in tokens:
        if isinstance(token, str):
            result.append(token)
            continue
        if not isinstance(token, dict) or len(token) != 1:
            raise ContractError('Argument must be literal text or one typed reference', code='invalid_argument')
        kind, key = next(iter(token.items()))
        if not isinstance(kind, str) or not isinstance(key, str) or kind not in values or key not in values[kind]:
            raise ContractError('Unbound invocation argument', code='invalid_argument')
        value = values[kind][key]
        if isinstance(value, (list, tuple, dict)) or value is None:
            raise ContractError('Compound/null arguments require a JSON file interface', code='invalid_argument')
        result.append(str(value).lower() if isinstance(value, bool) else str(value))
    if any('\0' in value for value in result):
        raise ContractError('NUL is not allowed in argv', code='invalid_argument')
    return tuple(result)


class CommandInvocationAdapter:
    def __init__(self, store, generation_id, *, package_root):
        self.store, self.generation_id = store, generation_id
        self.package_root = Path(package_root).resolve()

    def prepare(self, invocation, context):
        binding = self.store.binding(self.generation_id)
        root = context.attempt_root.resolve()
        root.mkdir(parents=True, exist_ok=True)
        for name in ('outputs', 'scratch', 'logs'):
            (root / name).mkdir(exist_ok=True)
        payload = context.payload
        params = payload.get('parameters', {})
        refs = payload.get('inputs', {})
        inputs = {name: str(validate_reference(ref)) for name, ref in refs.items()}
        declared = payload.get('outputs', {})
        outputs = {}
        resolved_outputs = []
        for name, contract in declared.items():
            if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.-]{0,79}', name):
                raise ContractError('Invalid output port name', code='invalid_argument')
            relative = contract.get('path')
            if not isinstance(relative, str) or not relative or relative in ('.', './'):
                raise ContractError('Output path must name a file', code='invalid_argument',
                                    details={'path': ['outputs', name, 'path']})
            output = confined(root / 'outputs', relative)
            resolved = output.resolve()
            for prior_name, prior in resolved_outputs:
                if resolved == prior or resolved.is_relative_to(prior) or prior.is_relative_to(resolved):
                    raise ContractError('Declared output paths overlap', code='overlapping_outputs',
                                        details={'outputs': [prior_name, name]})
            resolved_outputs.append((name, resolved))
            outputs[name] = str(output)
        for output in outputs.values():
            Path(output).parent.mkdir(parents=True, exist_ok=True)
        for name, value in (('parameters.json', params), ('inputs.json', refs),
                            ('environment.json', binding.model_dump(mode='json'))):
            atomic_json(root / name, value)
        generation = self.store.root / 'generations' / self.generation_id / 'payload'
        executable = confined(generation, payload['executable'])
        if not io_path(executable).is_file():
            raise ContractError('Locked executable is unavailable', code='environment_unverified')
        # R normalizes junctions and cannot reliably use an extended executable
        # spelling. Validate its physical layout before launching. Python/native
        # executables retain canonical extended paths; no runtime is copied here.
        windows_r = os.name == 'nt' and invocation.kind == 'r_script'
        launch_generation = (validate_r_generation(self.store, self.generation_id) if windows_r
                             else io_path(generation))
        executable = launch_generation / payload['executable']
        launch_inputs = {key: str(r_path(value, role='input')) for key, value in inputs.items()} if windows_r else inputs
        launch_outputs = {key: str(r_path(value, role='output')) for key, value in outputs.items()} if windows_r else outputs
        arguments = resolve_argv(payload.get('arguments', invocation.argv), inputs=launch_inputs, outputs=launch_outputs,
                                 parameters=params, resources={'memory_bytes': context.memory_bytes, 'threads': context.threads})
        if invocation.kind in ('python_script', 'r_script'):
            script = confined(self.package_root, invocation.code_ref.ref)
            if not invocation.code_ref.digest or file_digest(script) != invocation.code_ref.digest:
                raise ContractError('Script differs from frozen code identity', code='implementation_unavailable')
            if invocation.kind == 'python_script':
                bootstrap = root / 'script_bootstrap.py'
                bootstrap.write_text('import runpy,sys\nsys.path[:0] = ' + repr([
                    str(self.package_root), str(launch_generation / 'packages')]) +
                    '\nsys.argv = [' + repr(str(script)) + ', *sys.argv[1:]]\nrunpy.run_path(' +
                    repr(str(script)) + ', run_name="__main__")\n', encoding='utf-8')
                arguments = ('-I', '-B', str(io_path(bootstrap)), *arguments)
            else:
                arguments = ('--vanilla', str(r_path(script, role='script') if windows_r else script), *arguments)
        elif invocation.kind != 'command':
            raise ContractError('Foreign adapter cannot execute a native chain', code='unsupported_boundary')
        environment = isolated_environment(launch_generation)
        path = r_path if windows_r else lambda value: value
        scratch = (r_path(root / 'scratch', role='temporary', reserve=32, allow_spaces=False)
                   if windows_r else root / 'scratch')
        environment.update(OPERON_PARAMETERS_FILE=str(path(root / 'parameters.json')),
            OPERON_INPUTS_FILE=str(path(root / 'inputs.json')), OPERON_OUTPUTS_FILE=str(path(root / 'outputs.json')),
            OPERON_ATTEMPT_ID=context.attempt_id, OPERON_RUN_ID=context.run_id,
            OPERON_RESOURCE_FENCE=str(context.fence), OPERON_MEMORY_BYTES=str(context.memory_bytes),
            OMP_NUM_THREADS=str(context.threads), OPENBLAS_NUM_THREADS=str(context.threads),
            MKL_NUM_THREADS=str(context.threads), TMP=str(scratch), TEMP=str(scratch), TMPDIR=str(scratch))
        if windows_r:
            atomic_json(root / 'inputs.canonical.json', refs)
            atomic_json(root / 'inputs.json', {key: {**value, 'path': launch_inputs[key]}
                                              for key, value in refs.items()})
        atomic_json(root / 'outputs.json', launch_outputs)
        record = {'format': 'operon.foreign-invocation', 'schema_version': 1,
                  'spec': invocation.model_dump(mode='json'), 'environment': binding.model_dump(mode='json'),
                  'run_id': context.run_id, 'attempt_id': context.attempt_id, 'fence': context.fence,
                  'argv': [str(executable), *arguments], 'outputs': declared,
                  'limits': {'memory_bytes': context.memory_bytes, 'threads': context.threads,
                             'foreign_heap_spill': False}}
        atomic_json(root / 'invocation.json', record)
        launch_executable = executable_path(executable) if windows_r else str(io_path(executable))
        return PreparedInvocation(invocation, context, root, root / 'invocation.json', root / 'outputs',
                                  (launch_executable, *arguments), environment)

    def collect(self, prepared, exit_receipt):
        if exit_receipt.state != 'succeeded' or exit_receipt.exit_code != 0 or exit_receipt.tree_alive:
            return OutputManifest('failed', str(prepared.output_dir), None, error='Successful tree exit is required')
        try:
            refs = {}
            for name, contract in prepared.context.payload.get('outputs', {}).items():
                path = confined(prepared.output_dir, contract['path'])
                if not path.exists() and not contract.get('required', True):
                    continue
                metadata = dict(contract.get('metadata') or {})
                if contract['representation'] == 'form':
                    if path.parent.resolve() == prepared.output_dir.resolve():
                        raise ContractError('Form attachments require a dedicated output folder', code='unsupported_boundary')
                    from operon.environment_store.verification import inventory
                    metadata['inventory'] = inventory(path.parent)
                if contract['representation'] == 'npy':
                    import numpy as np
                    array = np.load(path, allow_pickle=False, mmap_mode='r')
                    metadata.update(shape=list(array.shape), dtype=array.dtype.str)
                    del array
                refs[name] = file_reference(path, representation=contract['representation'], metadata=metadata)
                if contract['representation'] in ('json', 'npy', 'form'):
                    from ..codecs import load
                    load(refs[name])
            # This manifest is adapter-owned after actual exit and schema checks.
            atomic_json(prepared.context.attempt_root / prepared.spec.output_manifest,
                        {'format': 'operon.foreign-outputs', 'schema_version': 1, 'status': 'complete', 'outputs': refs})
            return OutputManifest('complete', str(prepared.output_dir), None, tuple(ref['path'] for ref in refs.values()))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            return OutputManifest('failed', str(prepared.output_dir), None, error=str(exc))
