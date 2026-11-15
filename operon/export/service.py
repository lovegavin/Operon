"""Cancellable, receipt-based portable builds with mandatory relocation probes."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import tempfile
import uuid

from operon.contracts.base import ContractError, sha256_hex
from operon.contracts.run_plan import RunPlan
from operon.engine.fs import atomic_json, FileLock
from operon.environment_store import EnvironmentStore
from operon.environment_store.verification import confined, inventory, file_digest
from operon.environment_store.builders import probe, temporary_directory
from operon.bytecode import io_path
from .collector import collect, kernel_files, validate_coverage
from .planner import bindable_plan


BOOTSTRAP = '''import runpy,sys
from pathlib import Path
root = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(root / 'payload' / 'code'))
import json
manifest = json.loads((root / 'bundle.json').read_text(encoding='utf-8'))
sys.path.insert(1, str(root / manifest['management_packages']))
sys.argv = ['operon.export.kernel', '--bundle', str(root), *sys.argv[1:]]
runpy.run_module('operon.export.kernel', run_name='__main__')
'''


class ExportService:
    def __init__(self, source_root, environment_store, receipt_root):
        self.source_root = Path(source_root).resolve()
        self.environments = environment_store
        self.receipts = Path(receipt_root).resolve()
        self.receipts.mkdir(parents=True, exist_ok=True)

    def build(self, plan, output, *, implementations, environments, extra_files=None,
              management_environment=None, input_bindings=None, input_formats=None, cancel=None):
        """Materialized managed generations are mandatory; no requirements-only ZIP.

        implementations maps frozen operator IDs to code/resource file manifests.
        environments maps invocation environment_ref to generation_id/executable.
        Source locations may vary; destination-relative manifest keys are stable.
        """
        plan = RunPlan.model_validate(plan)
        validate_coverage(plan, implementations)
        portable, inputs = bindable_plan(plan)
        inputs.update(input_bindings or {})
        foreign_inputs = {source[len('input:'):] for unit in portable.units
                          for source in unit.input_bindings.values() if source.startswith('input:')}
        if not foreign_inputs <= inputs.keys():
            raise ContractError('Foreign input bindings are missing', code='missing_binding')
        output = Path(output).resolve()
        if output.exists() and any(output.iterdir()):
            raise ContractError('Export destination must be empty', code='output_exists')
        output.parent.mkdir(parents=True, exist_ok=True)
        build_id = uuid.uuid4().hex
        receipt = {'id': build_id, 'status': 'building', 'phase': 'plan', 'output': str(output),
                   'source_plan': plan.plan_id, 'portable_plan': portable.plan_id}
        receipt_path = self.receipts / (build_id + '.json')
        def phase(value):
            receipt['phase'] = value
            atomic_json(receipt_path, receipt)
            if cancel and cancel():
                raise InterruptedError('Portable build cancelled')
        temporary = output.with_name('.' + output.name + '.partial-' + build_id)
        temporary.mkdir()
        try:
            phase('plan')
            selected = {unit.invocation.environment_ref for unit in portable.units}
            if not selected <= environments.keys():
                raise ContractError('An execution unit has no materialized environment', code='environment_unavailable')
            required = {sha256_hex(item) for item in plan.environment_requirements}
            for key in selected:
                binding = self.environments.binding(environments[key]['generation_id'])
                expected = plan.execution_policy.get('environment_refs', {}).get(key)
                if expected is None and len(required) == 1:
                    expected = next(iter(required))
                if expected not in required or binding.requirement_digest != expected:
                    raise ContractError('Generation differs from plan requirement', code='environment_unverified')
            phase('acquire')
            code_manifest = kernel_files(self.source_root)
            for name, item in (extra_files or {}).items():
                if name in code_manifest and code_manifest[name]['sha256'] != item['sha256']:
                    raise ContractError('Extra payload conflicts with kernel: ' + name, code='export_missing_resource')
                code_manifest[name] = item
            for descriptor in implementations.values():
                for name, item in descriptor['files'].items():
                    if name in code_manifest and code_manifest[name]['sha256'] != item['sha256']:
                        raise ContractError('Conflicting code/resource destination: ' + name, code='export_missing_resource')
                    code_manifest[name] = item
            payload = temporary / 'payload'
            code = payload / 'code'
            collect(self.source_root, code, code_manifest, cancel=cancel)
            # Inline authoring scripts are explicit, hash-bound resources. They
            # are materialized once; later execution never reads the checkout.
            import hashlib
            for unit in portable.units:
                resource = unit.payload.get('script_resource')
                if resource:
                    content = resource['content'].encode('utf-8')
                    if (hashlib.sha256(content).hexdigest() != resource['sha256']
                            or resource['sha256'] != unit.invocation.code_ref.digest
                            or resource['path'] != unit.invocation.code_ref.ref):
                        raise ContractError('Script resource differs from code identity', code='implementation_unavailable')
                    target = confined(code, resource['path'])
                    if target.exists() and file_digest(target) != resource['sha256']:
                        raise ContractError('Script conflicts with another payload', code='export_missing_resource')
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(content)
            phase('prepare_environments')
            management = management_environment or next(iter(environments))
            needs_destination_preparation = False
            if management not in environments:
                raise ContractError('Management environment was not provided', code='environment_unavailable')
            for item in environments.values():
                generation = item['generation_id']
                path, generation_manifest, _ = self.environments._manifest(generation)
                self.environments.binding(generation)
                if generation_manifest['identity']['builder'].get('fixups'):
                    needs_destination_preparation = True
                    if generation == environments[management]['generation_id']:
                        raise ContractError('Management Python must start before destination environment preparation',
                                            code='environment_preparation_required')
                    from .environments import collect_packed_inputs
                    collect_packed_inputs(self.environments, payload / 'environments', generation)
                target = payload / 'environments' / 'generations' / generation
                if not target.exists():
                    shutil.copytree(io_path(path), io_path(target), symlinks=True)
            phase('assemble')
            atomic_json(payload / 'plan.json', portable.model_dump(mode='json'))
            atomic_json(payload / 'bindings.json', {'environments': environments, 'inputs': {},
                'required_inputs': sorted(inputs), 'input_formats': input_formats or {}})
            parameters = {}
            for unit in portable.units:
                if unit.invocation.kind == 'native':
                    parameters[unit.unit_id] = {node: step['params'] for node, step in zip(
                        unit.node_ids, unit.payload['task_manifest']['steps'], strict=True)}
                else:
                    parameters[unit.unit_id] = unit.payload.get('parameters', {})
            atomic_json(temporary / 'parameters.json', parameters)
            atomic_json(temporary / 'inputs.json', inputs)
            (temporary / 'run.py').write_text(BOOTSTRAP, encoding='utf-8')
            control = environments[management]
            executable = 'payload/environments/generations/' + control['generation_id'] + '/payload/' + control['executable']
            confined(temporary, executable)
            (temporary / 'run.cmd').write_text('@echo off\r\n"%~dp0' + executable.replace('/', '\\') +
                '" -I -B "%~dp0run.py" %*\r\nexit /b %errorlevel%\r\n', encoding='utf-8')
            (temporary / 'run.sh').write_text('#!/bin/sh\nset -eu\nROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)\nexec "$ROOT/' +
                executable + '" -I -B "$ROOT/run.py" "$@"\n', encoding='utf-8')
            (temporary / 'run.sh').chmod(0o755)
            phase('structural_verification')
            manifest = {'format': 'operon.portable', 'schema_version': 1, 'status': 'complete',
                        'plan_id': portable.plan_id, 'files': inventory(payload),
                        'management_executable': executable, 'implementation_manifests': implementations,
                        'management_packages': 'payload/environments/generations/' + control['generation_id'] + '/payload/packages',
                        'launchers': {name: file_digest(temporary / name) for name in ('run.py', 'run.cmd', 'run.sh')},
                        'network_resolution': False}
            atomic_json(temporary / 'bundle.json', manifest)
            phase('relocation_probe')
            # Offline check does not read scientific data into memory; it verifies
            # content identities/import paths/environment and all input bindings.
            with temporary_directory('operon-export-relocate-') as test:
                moved = Path(test) / 'moved package'
                shutil.copytree(io_path(temporary), io_path(moved), symlinks=True)
                # Prefix-independent runtimes are already runnable in payload.
                # Copying all of them into work/ merely to check relocation adds
                # a second environment deployment (and antivirus scan) on Windows.
                # Packed runtimes with prefix fixups still require real preparation.
                if needs_destination_preparation:
                    probe(moved, (executable, '-I', '-B', 'run.py', '--prepare-only'), timeout=600,
                          cancel=cancel, environment={'OPERON_EXPORT_PROBE': '1'})
                probe(moved, (executable, '-I', '-B', 'run.py', '--check'), timeout=180,
                      cancel=cancel, environment={'OPERON_EXPORT_PROBE': '1'})
            phase('publish')
            if output.exists():
                output.rmdir()
            os.replace(temporary, output)
            receipt.update(status='complete', phase='complete', bundle_identity=sha256_hex(manifest))
            atomic_json(receipt_path, receipt)
            return receipt
        except BaseException as exc:
            receipt.update(status='cancelled' if isinstance(exc, InterruptedError) else 'failed', error=f'{type(exc).__name__}: {exc}')
            atomic_json(receipt_path, receipt)
            # Retain partial build evidence; never leave a complete marker in it.
            (temporary / 'bundle.json').unlink(missing_ok=True)
            raise
