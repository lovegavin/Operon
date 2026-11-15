"""Explicit, workspace-confined preparation hints; never install or launch."""
from pathlib import Path
from typing import Literal
from pydantic import Field, field_validator
from .contracts.base import ContractModel, ContractError, sha256_hex
from .contracts.run_plan import RunPlan
from .contracts.plan_operations import binding_path
from .environment_store import EnvironmentStore
from .environment_store.verification import confined, file_digest
from .bytecode import io_path
from .planning.validation import validate_run_plan


class InputChoice(ContractModel):
    path: str
    representation: Literal['form', 'file', 'table', 'json', 'npy', 'report', 'figure'] = 'file'
    _path = field_validator('path')(binding_path)


class BindingOptionsRequest(ContractModel):
    plan: RunPlan
    package_root: str = '.'
    environment_store: str = 'environments'
    input_paths: dict[str, InputChoice] = Field(default_factory=dict, max_length=128)
    _paths = field_validator('package_root', 'environment_store')(binding_path)


def prepare_options(root, request):
    request = BindingOptionsRequest.model_validate(request)
    plan = validate_run_plan(request.plan)
    confined(root, request.package_root)
    store_root = confined(root, request.environment_store)
    store = EnvironmentStore(store_root, create=False)
    requirements = {sha256_hex(r): r for r in plan.environment_requirements}
    refs = {u.invocation.environment_ref for u in plan.units}
    result = dict(package_root=request.package_root, environment_store=request.environment_store,
                  environments={}, storage={}, inputs={}, missing=[])
    for ref in sorted(refs, key=str):
        digest = plan.execution_policy.get('environment_refs', {}).get(ref)
        if digest is None and len(requirements) == 1:
            digest = next(iter(requirements))
        choices = []
        if digest in requirements and store_root.is_dir():
            try:
                binding = store.resolve(requirements[digest])
                if binding:
                    directory, manifest, _ = store._manifest(binding.generation_id)
                    executable = manifest['identity']['builder'].get('executable')
                    if executable and io_path(confined(directory / 'payload', executable)).is_file():
                        choices.append(dict(generation_id=binding.generation_id, executable=executable,
                                            verified=True, target=binding.target.model_dump(mode='json')))
            except (ContractError, OSError):
                pass
        result['environments'][str(ref)] = choices
        if not choices:
            result['missing'].append('environment:' + str(ref))
    needed = {v[6:] for u in plan.units for v in u.input_bindings.values() if v.startswith('input:')}
    if set(request.input_paths) - needed:
        raise ContractError('Unknown input binding names', code='invalid_binding')
    for name in sorted(needed):
        choice = request.input_paths.get(name)
        if choice is None:
            result['missing'].append('input:' + name)
            continue
        path = io_path(confined(root, choice.path))
        before = path.stat()
        if not path.is_file():
            raise ContractError('Input must be a regular file', code='invalid_binding')
        digest = file_digest(path)
        after = path.stat()
        if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
            raise ContractError('Input changed while fingerprinting', code='input_changed')
        result['inputs'][name] = dict(path=choice.path, representation=choice.representation,
                                     size_bytes=after.st_size, sha256=digest, metadata={})
    result['missing'].extend('storage:' + s.storage_id for s in plan.storage_bindings)
    return result


def mount_binding_options(app, application, bridge):
    from fastapi import Request
    from .storage.configuration import PROFILE_OWNER

    @app.post('/api/v1/plans/binding-options')
    async def binding_options(request: Request, payload: BindingOptionsRequest):
        bridge.actor(request, 'context')
        return await application.storage_dispatch.run(
            lambda: prepare_options(application.service.root, payload), principal=PROFILE_OWNER)
