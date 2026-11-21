"""Plan-selected native registrations and frozen isolation; no live discovery."""
from __future__ import annotations

from copy import deepcopy
import importlib
from importlib.machinery import ModuleSpec
import json
import os
from pathlib import Path
import re
import sys
from types import ModuleType

from pydantic import Field, field_validator

from operon.contracts.base import ContractError, ContractModel, canonical_json, sha256_hex


class NativeRuntimeSnapshot(ContractModel):
    format: str = 'operon.native-runtime'
    schema_version: int = 1
    descriptors: tuple[dict, ...]
    implementations: dict[str, dict]
    audit_descriptors: dict[str, dict] = Field(default_factory=dict)
    isolation_targets: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    environment_requirement_digest: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')

    @field_validator('isolation_targets', mode='before')
    @classmethod
    def normalize_isolation_targets(cls, value):
        if isinstance(value, dict):
            return {key: tuple(paths) if isinstance(paths, (list, tuple)) else paths for key, paths in value.items()}
        return value


def validate_native_descriptors(descriptors, implementations, manifest, *, environment_requirement_digest=None):
    """Match selected full declarations to the plan's executable identities."""
    from operon.execution.invocation import verify_implementations
    selected = {}
    for descriptor in descriptors:
        key = descriptor.get('id')
        if not isinstance(key, str) or key in selected or descriptor.get('kind') not in ('operator', 'reader', 'converter'):
            raise ContractError('Invalid or duplicate native descriptor', code='implementation_unavailable')
        if key not in implementations:
            raise ContractError('Native descriptor is absent from the frozen plan: ' + key,
                                code='implementation_unavailable')
        selected[key] = descriptor
        environment = (descriptor.get('resources') or {}).get('environment')
        isolated = (descriptor.get('execution') or {}).get('mode') == 'isolated'
        if (environment or isolated) and not environment_requirement_digest:
            raise ContractError('Native descriptor requires explicit unit environment lowering: ' + key,
                                code='unsupported_boundary', details={'implementation': key, 'environment': environment})
    if not selected:
        raise ContractError('Native invocation has no frozen implementation descriptors', code='implementation_unavailable')
    # Preserve the established four-key executable identity comparison. A
    # documentation/declaration audit field is not an alternate code identity.
    catalog = {'operators': [d for d in selected.values() if d['kind'] != 'reader'],
               'readers': [d for d in selected.values() if d['kind'] == 'reader']}
    expected = {key: implementations[key] for key in selected}
    for key, descriptor in selected.items():
        record = expected[key]
        if record.get('kind') != descriptor['kind']:
            raise ContractError('Native descriptor kind differs from plan: ' + key, code='implementation_unavailable')
        for field in ('execution_sha', 'resource_digest', 'sdk_abi'):
            if (descriptor.get('implementation') or {}).get(field) != (record.get('implementation') or {}).get(field):
                raise ContractError('Native executable resource identity differs from plan: ' + key, code='implementation_unavailable')
        if record.get('origin') != descriptor.get('origin'):
            raise ContractError('Native implementation origin differs from plan: ' + key, code='implementation_unavailable')
        # Converters have the same frozen implementation projection but are
        # executed by the existing conversion engine, not the Step registry.
        if descriptor['kind'] == 'converter':
            fields = ('version', 'package', 'sha256', 'code_sha')
            if any((descriptor.get('implementation') or {}).get(k) != (record.get('implementation') or {}).get(k) for k in fields):
                raise ContractError('Converter identity differs from plan: ' + key, code='implementation_unavailable')
        else:
            verify_implementations({key: record}, catalog)
    operators = {key for key, item in selected.items() if item['kind'] == 'operator'}
    readers = {key for key, item in selected.items() if item['kind'] == 'reader'}
    for step in manifest.get('steps', []):
        if step['name'] not in operators:
            raise ContractError('Native task references an unselected operator: ' + step['name'], code='implementation_unavailable')
        if step['name'].startswith('operon.script.'):
            from operon.script_operators import validate_script
            # RunPlan freezes nested arrays as tuples. Script validation consumes
            # the JSON wire contract, just like the worker's deserialized task;
            # do not loosen the public script/SDK schema to accept arbitrary types.
            snapshot = validate_script(json.loads(canonical_json(step['params']['script'])))
            if snapshot['code_sha'] != selected[step['name']]['implementation'].get('code_sha'):
                raise ContractError('Native script differs from its frozen descriptor', code='implementation_unavailable')
    exchanges = set((manifest.get('runtime') or {}).get('exchange_inputs', []))
    for name, source in manifest.get('sources', {}).items():
        if name in exchanges:
            continue
        if source.get('reader') and source['reader'] not in readers:
            raise ContractError('Native task references an unselected Reader: ' + source['reader'], code='implementation_unavailable')
        if not source.get('reader'):
            from operon.reader_selection import candidates
            matches = candidates(catalog['readers'], Path(source['path']), check_siblings=False)
            if len(matches) != 1:
                raise ContractError('Native input does not resolve to exactly one frozen Reader',
                                    code='implementation_unavailable', details={'source': name})
    return selected


def _module_root(entry, roots):
    if not isinstance(entry, str) or not re.fullmatch(r'[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*:[A-Za-z_]\w*', entry):
        raise ContractError('Native entry point must name one explicit module/class', code='implementation_unavailable')
    module = entry.split(':')[0]
    relative = Path(*module.split('.'))
    for base in roots:
        root = Path(base).resolve()
        for path in (root / relative.with_suffix('.py'), root / relative / '__init__.py'):
            if path.is_file():
                if path.is_symlink() or not path.resolve().is_relative_to(root):
                    raise ContractError('Native implementation escapes its frozen code root', code='implementation_unavailable')
                return root
    raise ContractError('Selected native implementation is absent from frozen code roots: ' + module,
                        code='implementation_unavailable')


def _bind_legacy_namespace(entry, root):
    """Keep stable v3 entry points without consulting an installed seed."""
    for prefix in ('src.task.step.steps', 'src.reader.readers'):
        if entry.startswith(prefix + '.'):
            parent, _, child = prefix.rpartition('.')
            owner = importlib.import_module(parent)
            namespace = ModuleType(prefix)
            namespace.__path__ = [str(root.joinpath(*prefix.split('.')))]
            namespace.__package__ = prefix
            namespace.__spec__ = ModuleSpec(prefix, loader=None, is_package=True)
            namespace.__spec__.submodule_search_locations = namespace.__path__
            sys.modules[prefix] = namespace
            setattr(owner, child, namespace)


def environment_binding(descriptor):
    """Return the declared environment binding, but only for operators.

    A reader that declares an environment still has to answer ``read``/``probe``
    on the frozen code root: the environment names the dependencies the
    preparation step verified, it does not replace the Reader interface.  Only
    an operator can be swapped for the environment bridge, which exposes
    ``run``/``export`` instead.
    """
    if descriptor.get('kind') != 'operator':
        return None
    return (descriptor.get('resources') or {}).get('environment')


def register_native_runtime(snapshot, manifest, *, code_roots=None):
    snapshot = NativeRuntimeSnapshot.model_validate(snapshot)
    if snapshot.format != 'operon.native-runtime' or snapshot.schema_version != 1:
        raise ContractError('Unsupported native runtime snapshot', code='implementation_unavailable')
    wire = snapshot.model_dump(mode='json')
    descriptors = wire['descriptors']
    selected = validate_native_descriptors(descriptors, snapshot.implementations, manifest,
        environment_requirement_digest=snapshot.environment_requirement_digest)
    from operon.planning.descriptor_snapshot import execution_descriptor
    if set(wire['audit_descriptors']) != set(selected) or any(
            sha256_hex(execution_descriptor(wire['audit_descriptors'][key])) != sha256_hex(descriptor)
            for key, descriptor in selected.items()):
        raise ContractError('Native audit descriptors differ from the executable snapshot', code='implementation_unavailable')
    if code_roots is None:
        code_roots = json.loads(os.environ.get('OPERON_BASE_PATHS', '[]'))
    if not isinstance(code_roots, (list, tuple)) or not code_roots or any(not isinstance(p, str) or not Path(p).is_absolute() for p in code_roots):
        raise ContractError('Native invocation requires explicit frozen code roots', code='implementation_unavailable')
    # Set before either module is imported. Their ordinary legacy initializer
    # discovers bundled providers unless maintenance mode is selected.
    os.environ['OPERON_REGISTRY_MAINTENANCE'] = '1'
    from src.task.step import STEPS
    from src.reader import READERS
    from operon.lazy import LazyRegistry, reader_proxy
    from operon_sdk.declarations import load_class, bind_class, declaration_hash
    if not isinstance(STEPS, LazyRegistry):
        raise ContractError('Native registry is not descriptor backed', code='implementation_unavailable')
    STEPS.clear()
    READERS.clear()
    for key, descriptor in selected.items():
        if descriptor['kind'] == 'converter' or key.startswith('operon.script.'):
            continue  # Existing runner owns frozen script/converter adapters.
        root = _module_root(descriptor.get('entry_point'), code_roots)
        _bind_legacy_namespace(descriptor['entry_point'], root)
        def factory(d=descriptor, r=root, audit=deepcopy(wire['audit_descriptors'][key])):
            binding = environment_binding(d)
            if binding:
                from operon.environments import proxy_step
                name = binding
                if not os.environ.get('OPERON_ENV_' + name.upper()):
                    raise ContractError('Declared environment binding missing', code='environment_unverified')
                return proxy_step(audit, paths=code_roots)
            if (d.get('execution') or {}).get('mode') == 'isolated':
                from operon.environment_store.verification import confined
                from operon.isolation import proxy_reader, proxy_step
                target_paths = snapshot.isolation_targets.get(d['id'])
                envroot = os.environ.get('OPERON_ENVIRONMENT_ROOT')
                if not target_paths or not envroot:
                    raise ContractError('Isolated dependency binding missing', code='environment_unverified')
                for path in target_paths:
                    confined(envroot, path)
                frozen = deepcopy(audit)
                frozen['execution'] = {'mode': 'isolated', 'paths': list(target_paths)}
                state = {'_runtime_root': envroot, 'code_paths': []}
                return (proxy_reader if d['kind'] == 'reader' else proxy_step)(frozen, state)
            # The original declaration verifies the provider's frozen code.
            # Execution binds only the projected schema and IO capabilities.
            loaded = load_class(audit, root=r)
            runtime = deepcopy(d)
            runtime['title'] = runtime['id']
            runtime['declaration_sha'] = declaration_hash(runtime)
            return bind_class(loaded, runtime)
        if descriptor['kind'] == 'operator':
            STEPS.register(key, factory, descriptor)
        else:
            proxy = reader_proxy(descriptor, factory)
            READERS.append(proxy)
