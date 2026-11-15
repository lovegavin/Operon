"""Strict, static YAML v2 authoring normalized to the existing graph compiler.

Import/save is explicit: ``initial=True`` may extract defaults once. Replay
requires the independent graph-parameter snapshot and never asks the catalog
for values. This module owns no executor, scheduler, or graph expansion logic.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Literal, Mapping

import yaml
from pydantic import Field, ValidationError, field_validator, model_validator

from operon.contracts.base import ContractError, ContractModel, canonical_json
from operon.contracts.workflow import WorkflowSpec
from operon.workflow_spec import WorkflowLoader, resolve_resource
from .invocation_lowering import NormalizedForeignWorkflow


_ID = r'^[A-Za-z_][A-Za-z0-9_.-]{0,79}$'
_MAX_BYTES = 10 * 1024 * 1024
_MAX_DEPTH = 48
_MAX_ITEMS = 50000


def _error(message, path=(), *, code='invalid_workflow', **details):
    return ContractError(message, code=code, details={'path': list(path), **details})


def _validate(model, value, path=()):
    try:
        return model.model_validate(value)
    except ValidationError as exc:
        errors = [{'path': list(path) + list(item['loc']), 'type': item['type'],
                   'message': item['msg']} for item in exc.errors(include_url=False)]
        raise _error('Invalid workflow authoring data', path, errors=errors) from exc


def _bounded(value, path=()):
    """Bound decoded data before model validation or copying route snapshots."""
    stack, count = [(value, tuple(path), 0)], 0
    while stack:
        current, at, depth = stack.pop()
        count += 1
        if depth > _MAX_DEPTH or count > _MAX_ITEMS:
            raise _error('Workflow document exceeds its structural limit', at,
                         code='payload_too_large', max_depth=_MAX_DEPTH, max_items=_MAX_ITEMS)
        if isinstance(current, Mapping):
            if len(current) > _MAX_ITEMS:
                raise _error('Object exceeds its entry limit', at, code='payload_too_large', limit=_MAX_ITEMS)
            if any(not isinstance(key, str) for key in current):
                raise _error('Object keys must be strings', at)
            stack.extend((item, (*at, key), depth + 1) for key, item in current.items())
        elif isinstance(current, (list, tuple)):
            if len(current) > _MAX_ITEMS:
                raise _error('Array exceeds its entry limit', at, code='payload_too_large', limit=_MAX_ITEMS)
            stack.extend((item, (*at, i), depth + 1) for i, item in enumerate(current))
    try:
        canonical_json(value)
    except ContractError as exc:
        raise _error(str(exc), path) from exc


class _BoundedLoader(WorkflowLoader):
    """Retain the established duplicate-key/tag/alias policy; bound parse depth."""
    def __init__(self, stream):
        super().__init__(stream)
        self._depth = self._items = 0

    def compose_node(self, parent, index):
        self._depth += 1
        self._items += 1
        try:
            if self._depth > _MAX_DEPTH or self._items > _MAX_ITEMS:
                raise _error('Workflow YAML exceeds its structural limit',
                             code='payload_too_large', max_depth=_MAX_DEPTH, max_items=_MAX_ITEMS)
            return super().compose_node(parent, index)
        finally:
            self._depth -= 1


def parse(text: str) -> dict:
    """Parse safe YAML with bounded construction and machine-readable errors."""
    if not isinstance(text, str):
        raise _error('Workflow YAML must be text')
    try:
        size = len(text.encode('utf-8'))
    except UnicodeError as exc:
        raise _error('Workflow YAML must be valid UTF-8 text') from exc
    if size > _MAX_BYTES:
        raise _error('Workflow YAML exceeds its byte limit', code='payload_too_large', limit=_MAX_BYTES)
    try:
        value = yaml.load(text, Loader=_BoundedLoader)
    except ContractError:
        raise
    except (ValueError, TypeError, yaml.YAMLError, RecursionError) as exc:
        mark = getattr(exc, 'problem_mark', None)
        details = {'line': mark.line + 1, 'column': mark.column + 1} if mark else {}
        raise _error(f'Invalid workflow YAML: {exc}', **details) from exc
    _bounded(value)
    if not isinstance(value, dict):
        raise _error('Workflow must be an object')
    return value


class Ref(ContractModel):
    ref: str = Field(min_length=1, max_length=200)


class Param(ContractModel):
    param: str = Field(pattern=_ID)


class Input(ContractModel):
    input: str = Field(pattern=_ID)


class Output(ContractModel):
    output: str = Field(pattern=_ID)


class LiteralToken(ContractModel):
    literal: str


class ResourceToken(ContractModel):
    resource: str = Field(min_length=1, max_length=200)


class Resources(ContractModel):
    cpus: int | None = Field(default=None, ge=1)
    memory: int | str | None = None
    time: int | str | None = None

    @field_validator('memory', 'time')
    @classmethod
    def _quantity(cls, value, info):
        if value is None:
            return value
        if type(value) is int:
            if value <= 0:
                raise ValueError('Resource quantities must be positive')
            return value
        units = {'B': 1, 'KiB': 1024, 'MiB': 1024**2, 'GiB': 1024**3,
                 'TiB': 1024**4} if info.field_name == 'memory' else {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
        match = re.fullmatch(r'([1-9][0-9]*)\s*([A-Za-z]+)', value)
        if not match or match[2] not in units:
            raise ValueError('Use a positive integer or an explicit binary-memory/time unit')
        return int(match[1]) * units[match[2]]


class Profile(ContractModel):
    executor: Literal['local', 'ssh', 'slurm', 'standalone'] | None = None
    target: dict[str, Any] | None = None
    resources: Resources = Field(default_factory=Resources)
    storage: dict[str, Any] = Field(default_factory=dict)


class Port(ContractModel):
    type: Literal['form', 'path', 'val', 'tuple']
    format: str | None = None
    handle: str | None = None
    contract: dict[str, Any] = Field(default_factory=dict)


class Source(ContractModel):
    path: str | Input | Param | None = None
    reader: str | None = None
    dims: tuple[str, ...] = ('sample', 'feature')
    labels: dict[str, Any] = Field(default_factory=dict)
    args: dict[str, Any] = Field(default_factory=dict)
    location: dict[str, Any] | None = None


class Take(Port):
    source: Source = Field(default_factory=Source)
    title: str = ''


class Binding(ContractModel):
    ref: str | None = None
    input: str | None = None
    id: str | None = None
    adaptation: dict[str, Any] | None = None

    @model_validator(mode='after')
    def _single_reference(self):
        if (self.ref is None) == (self.input is None):
            raise ValueError('A data binding requires exactly one ref or input')
        return self


class Command(ContractModel):
    argv: tuple[LiteralToken | Input | Param | Output | ResourceToken, ...] = Field(max_length=1000)


class Process(ContractModel):
    runner: Literal['native', 'python_script', 'r_script', 'command'] = 'native'
    operator: str | None = None
    route: dict[str, Any] | None = None
    script: dict[str, Any] | None = None
    input: dict[str, Port] = Field(default_factory=dict)
    output: dict[str, Port] = Field(default_factory=dict)
    environment: str | None = Field(default=None, pattern=_ID)
    resources: Resources = Field(default_factory=Resources)
    parameters: dict[str, Any] = Field(default_factory=dict)
    command: Command | None = None

    @model_validator(mode='after')
    def _binding(self):
        bindings = sum(value is not None for value in (self.operator, self.route, self.script, self.command))
        if bindings != 1:
            raise ValueError('A process requires exactly one operator, route, script, or command binding')
        if self.command is not None and self.runner != 'command':
            raise ValueError('A command binding requires runner command')
        if self.runner == 'command' and self.command is None:
            raise ValueError('The command runner requires a command binding')
        if (self.operator is not None or self.route is not None) and self.runner != 'native':
            raise ValueError('Operator and route bindings require the native runner')
        if self.script is not None and self.runner in ('python_script', 'r_script'):
            expected = 'python' if self.runner == 'python_script' else 'r'
            if self.script.get('language') != expected:
                raise ValueError('Script language must match the process runner')
        return self


class Step(ContractModel):
    process: str = Field(pattern=_ID)
    bindings: dict[str, Binding] = Field(default_factory=dict, alias='in')
    params: dict[str, Any] = Field(default_factory=dict)
    context_params: dict[str, Any] = Field(default_factory=dict)
    title: str = ''
    input_count: int | None = Field(default=None, ge=0, le=20)


class Workflow(ContractModel):
    name: str = 'workflow'
    take: dict[str, Take] = Field(default_factory=dict)
    steps: dict[str, Step] = Field(min_length=1, max_length=1000)
    emit: dict[str, Ref] = Field(default_factory=dict)
    defaults: Profile = Field(default_factory=Profile)
    memory: dict[str, Any] = Field(default_factory=lambda: {'enabled': True, 'auto_spill': True})
    runtime: dict[str, Any] = Field(default_factory=dict)
    manifest_extra: dict[str, Any] = Field(default_factory=dict)
    plugin_lock: dict[str, Any] = Field(default_factory=dict)
    interface: dict[str, Any] | None = None


class AuthoringDocument(ContractModel):
    format: Literal['operon.workflow']
    schema_version: Literal[2]
    params_file: str = 'parameters.json'
    inputs_file: str | None = None
    environments_file: str | None = None
    processes: dict[str, Process] = Field(min_length=1, max_length=1000)
    workflow: Workflow
    profiles: dict[str, Profile] = Field(default_factory=dict)

    @field_validator('schema_version', mode='before')
    @classmethod
    def _integer_version(cls, value):
        if type(value) is not int:
            raise ValueError('schema_version must be an integer')
        return value

    @model_validator(mode='after')
    def _names(self):
        for entries in (self.processes, self.profiles, self.workflow.take, self.workflow.steps, self.workflow.emit):
            if any(not re.fullmatch(_ID, key) for key in entries):
                raise ValueError('Workflow, process and port names must be stable identifiers')
        if set(self.workflow.take) & set(self.workflow.steps):
            raise ValueError('Workflow input and step identifiers must be unique')
        if 'workflow' in self.workflow.steps:
            raise ValueError('The workflow identifier is reserved for workflow inputs')
        for process in self.processes.values():
            if any(not re.fullmatch(_ID, key) for key in (*process.input, *process.output)):
                raise ValueError('Process port names must be stable identifiers')
        return self


def json_schema():
    return AuthoringDocument.model_json_schema(by_alias=True)


def _resource(directory, name, path):
    try:
        return resolve_resource(directory, name)
    except ValueError as exc:
        raise _error(str(exc), path, code='workflow_resource_error') from exc


def _read_json(directory, name, path):
    resource = _resource(directory, name, path)
    try:
        if resource.stat().st_size > _MAX_BYTES:
            raise _error('Workflow resource exceeds its byte limit', path,
                         code='payload_too_large', limit=_MAX_BYTES)
        text = resource.read_text(encoding='utf-8-sig')
        def pairs(items):
            result = {}
            for key, value in items:
                if key in result:
                    raise _error('Duplicate JSON key', (*path, key))
                result[key] = value
            return result
        value = json.loads(text, object_pairs_hook=pairs)
        _bounded(value, path)
        return value
    except ContractError:
        raise
    except (OSError, UnicodeError, ValueError, RecursionError) as exc:
        raise _error(f'Cannot read workflow resource {name!r}: {exc}', path,
                     code='workflow_resource_error', resource=name) from exc


def _plain(value):
    return json.loads(canonical_json(value))


def _resolve(value, params, inputs, path):
    if isinstance(value, (Param, Input)):
        value = value.model_dump(mode='json')
    if isinstance(value, dict):
        expression = set(value) & {'param', 'input', 'ref'}
        if expression:
            if len(value) != 1 or len(expression) != 1 or 'ref' in expression:
                raise _error('Use one typed param or input expression here', path)
            kind = next(iter(expression))
            name = value[kind]
            model = Param if kind == 'param' else Input
            _validate(model, value, path)
            scope = params if kind == 'param' else inputs
            if name not in scope:
                raise _error(f'Unknown {kind} reference {name!r}', path, code='unknown_reference', reference=name)
            # Referenced values are JSON literals, never recursively evaluated.
            return deepcopy(scope[name])
        return {key: _resolve(item, params, inputs, (*path, key)) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_resolve(item, params, inputs, (*path, index)) for index, item in enumerate(value)]
    if isinstance(value, str) and '${' in value:
        raise _error('String interpolation is unsupported; use a typed reference object', path,
                     code='unsupported_expression')
    return value


def select_profile(document, profile=None, overrides=None):
    """CLI fields > one selected profile > workflow defaults, field by field."""
    if profile is not None and not isinstance(profile, str):
        raise _error('Select one profile name', ('profile',))
    selected = document.workflow.defaults.model_dump(mode='json', exclude_none=True)
    layers = []
    if profile is not None:
        if profile not in document.profiles:
            raise _error('Unknown profile', ('profiles', profile), code='unknown_profile')
        layers.append(document.profiles[profile])
    if overrides is not None:
        layers.append(_validate(Profile, overrides, ('overrides',)))
    for layer in layers:
        for key, value in layer.model_dump(mode='json', exclude_none=True).items():
            if isinstance(value, dict):
                selected[key] = {**selected.get(key, {}), **value}
            else:
                selected[key] = value
    return _validate(Profile, selected, ('profile',))


def _handle(port, index, *, output=False, total=1):
    handle = port.handle or ('out' if output and total == 1 else f'out-{index}' if output else f'in-{index}')
    pattern = r'out(?:-\d+)?' if output else r'in-\d+'
    if not re.fullmatch(pattern, handle):
        raise _error('Invalid graph port handle', ('handle',), handle=handle)
    return handle


def _reference(value, document, path):
    if value.startswith('workflow.'):
        name = value[len('workflow.'):]
        if name in document.workflow.take:
            return name, 'out', document.workflow.take[name]
    else:
        matches = []
        for node, step in document.workflow.steps.items():
            process = document.processes.get(step.process)
            if process is not None and value.startswith(node + '.'):
                port = value[len(node) + 1:]
                if port not in process.output:
                    continue
                names = list(process.output)
                descriptor = process.output[port]
                matches.append((node, _handle(descriptor, names.index(port), output=True, total=len(names)), descriptor))
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise _error('Ambiguous workflow output reference', path, code='ambiguous_reference', reference=value)
    raise _error('Unknown workflow output reference', path, code='unknown_reference', reference=value)


def _type_binding(source, target, binding, path):
    if source.type != target.type:
        raise _error('Input and output boundary types differ', path, code='incompatible_port',
                     source_type=source.type, target_type=target.type)
    # Native Form conversions remain the existing catalog compiler's decision.
    if source.type != 'form' and source.format and target.format and source.format != target.format and not binding.adaptation:
        raise _error('Input and output file formats differ', path, code='incompatible_port',
                     source_format=source.format, target_format=target.format)


@dataclass(frozen=True)
class NormalizedWorkflow:
    spec: WorkflowSpec
    document: AuthoringDocument
    parameters: Mapping[str, Any]
    inputs: Mapping[str, Any]
    environments: Mapping[str, Any]
    profile: Profile

    def compile(self, catalog, *, root=None, require_files=False):
        from .compiler import WorkflowCompiler
        return WorkflowCompiler().compile_authoring(self, catalog, root=root, require_files=require_files)

    def _check_compilation_policy(self):
        """The same native compiler, with explicit failure for unlowered policies."""
        policy = self.profile.model_dump(mode='json', exclude_none=True)
        unsupported = {key: value for key, value in policy.items()
                       if value and not (key == 'executor' and value == 'local')}
        processes = {name: process.model_dump(mode='json', exclude_none=True)
                     for name, process in self.document.processes.items()
                     if process.environment or any(value is not None for value in
                                                   process.resources.model_dump().values())}
        if unsupported or processes:
            raise _error('This execution policy requires shared compiler lowering before execution',
                         ('workflow', 'defaults'), code='unsupported_boundary',
                         policy=unsupported, processes=processes)


def _result(spec, document, parameters, inputs, environments, profile):
    # Reuse the contract container freeze, including deeply nested route values.
    from operon.contracts.base import _freeze
    return NormalizedWorkflow(spec, document, _freeze(_plain(parameters)),
                              _freeze(_plain(inputs)), _freeze(_plain(environments)), profile)


def _parameter_snapshot(value, path=('parameters',)):
    """Guard strict wire types before the legacy recursive equality checks."""
    if (not isinstance(value, dict) or set(value) != {'format', 'schema_version', 'params', 'nodes'}
            or value.get('format') != 'operon.graph-parameters'
            or type(value.get('schema_version')) is not int or value['schema_version'] != 1
            or not isinstance(value['params'], dict) or not isinstance(value['nodes'], dict)):
        raise _error('Invalid frozen graph parameter snapshot', path, code='invalid_parameters')
    for key, entry in value['nodes'].items():
        if not isinstance(entry, dict):
            raise _error('Frozen node values must be objects', (*path, 'nodes', key), code='invalid_parameters')
        if 'route' in entry:
            if type(entry.get('route_version')) is not int or entry['route_version'] < 1:
                raise _error('Frozen route_version must be a positive integer',
                             (*path, 'nodes', key, 'route_version'), code='invalid_parameters')
            _parameter_snapshot(entry['route'], (*path, 'nodes', key, 'route'))


def _extract_ui(graph):
    ui = {'positions': {}, 'routes': {}}
    for node in graph['nodes']:
        ui['positions'][node['id']] = node.get('position') or {'x': 0, 'y': 0}
        # Graph snapshots require this field; the actual coordinates live in UI.
        node['position'] = {'x': 0, 'y': 0}
        if node.get('route'):
            ui['routes'][node['id']] = _extract_ui(node['route']['graph'])
    return ui


def _restore_ui(graph, ui, path=('ui',)):
    if (not isinstance(ui, dict) or set(ui) - {'positions', 'routes'}
            or not isinstance(ui.get('positions'), dict) or not isinstance(ui.get('routes', {}), dict)):
        raise _error('ui.json requires positions and optional routes objects', path)
    nodes = {node.id: node for node in graph.nodes}
    if set(ui['positions']) - set(nodes):
        raise _error('UI positions reference unknown nodes', (*path, 'positions'))
    for key, position in ui['positions'].items():
        nodes[key].position = _validate(type(nodes[key].position), position, (*path, 'positions', key))
    for key, nested in ui.get('routes', {}).items():
        if key not in nodes or nodes[key].route is None:
            raise _error('UI route references unknown route', (*path, 'routes', key))
        _restore_ui(nodes[key].route.graph, nested, (*path, 'routes', key))


def normalize(value, directory='.', *, parameters=None, inputs=None, environments=None,
              profile=None, overrides=None, initial=False, catalog=None, ui=None):
    """Normalize v2, v1 YAML, or canvas JSON. ``initial`` is never implicit.

    Initial import may consume inline values and schema defaults. Replay requires
    the graph snapshot written by ``export_workflow``; it restores nested values
    with the existing strict restore_graph helper, without consulting defaults.
    """
    value = parse(value) if isinstance(value, str) else value
    _bounded(value)
    if not isinstance(value, dict):
        raise _error('Workflow must be an object')
    directory = Path(directory).resolve()
    if ('nodes' in value or value.get('schema_version') == 1
            or isinstance(value.get('steps'), list) and isinstance(value.get('sources'), dict)):
        return normalize_legacy(value, directory, initial=initial, catalog=catalog,
                                profile=profile, overrides=overrides)
    document = _validate(AuthoringDocument, value)
    # Validate paths even when callers inject already-loaded sidecars.
    for field in ('params_file', 'inputs_file', 'environments_file'):
        if getattr(document, field) is not None:
            _resource(directory, getattr(document, field), (field,))
    if parameters is None:
        path = _resource(directory, document.params_file, ('params_file',))
        parameters = {} if initial and not path.exists() else _read_json(directory, document.params_file, ('params_file',))
    if inputs is None:
        inputs = _read_json(directory, document.inputs_file, ('inputs_file',)) if document.inputs_file else {}
    if environments is None:
        environments = _read_json(directory, document.environments_file, ('environments_file',)) if document.environments_file else {}
    for name, data in (('parameters', parameters), ('inputs', inputs), ('environments', environments)):
        _bounded(data, (name,))
        if not isinstance(data, dict):
            raise _error(f'{name} must be an object', (name,))
    selected = select_profile(document, profile, overrides)
    for process_name, process in document.processes.items():
        for group in ('input', 'output'):
            ports = getattr(process, group)
            handles = set()
            for index, (port_name, port) in enumerate(ports.items()):
                at = ('processes', process_name, group, port_name, 'handle')
                try:
                    handle = _handle(port, index, output=group == 'output', total=len(ports))
                except ContractError as exc:
                    raise _error(str(exc), at) from exc
                if handle in handles:
                    raise _error('Duplicate process port handle', at)
                handles.add(handle)
    from .invocation_lowering import FOREIGN_RUNNERS, normalize_foreign
    if any(document.processes[step.process].runner in FOREIGN_RUNNERS
           for step in document.workflow.steps.values() if step.process in document.processes):
        return normalize_foreign(document, directory, parameters=parameters, inputs=inputs,
                                 environments=environments, profile=selected, initial=initial, ui=ui, catalog=catalog)
    globals_ = parameters.get('params', {})
    if not isinstance(globals_, dict):
        raise _error('Global parameter values must be an object', ('parameters', 'params'))
    if not initial and parameters.get('format') != 'operon.graph-parameters':
        raise _error('Replay requires the independent frozen graph parameter snapshot',
                     ('params_file',), code='missing_frozen_parameters')
    if parameters.get('format') == 'operon.graph-parameters':
        _parameter_snapshot(parameters)
    nodes, edges = [], []
    for key, take in document.workflow.take.items():
        source = take.source.model_dump(mode='json')
        path = source.pop('path')
        if path is None:
            path = {'input': key}
        source['path'] = _resolve(path, globals_, inputs, ('workflow', 'take', key, 'source', 'path'))
        if not isinstance(source['path'], str):
            raise _error('Source path must resolve to a string', ('workflow', 'take', key, 'source', 'path'))
        if (source.get('location') or {}).get('kind') != 'ssh':
            source['path'] = str((directory / source['path']).resolve())
        source['args'] = _resolve(source['args'], globals_, inputs, ('workflow', 'take', key, 'source', 'args')) if initial else {}
        nodes.append({'id': key, 'kind': 'source', 'source': source, 'title': take.title,
                      'position': {'x': 0, 'y': 0}, 'params': {}, 'context_params': {}})
    for key, step in document.workflow.steps.items():
        where = ('workflow', 'steps', key)
        process = document.processes.get(step.process)
        if process is None:
            raise _error('Step references an unknown process', (*where, 'process'), code='unknown_reference')
        if process.environment and process.environment not in environments:
            raise _error('Process references an unknown environment', ('processes', step.process, 'environment'),
                         code='unknown_reference', reference=process.environment)
        if set(step.bindings) != set(process.input):
            raise _error('Step bindings must match the declared process inputs', (*where, 'in'),
                         missing=sorted(set(process.input) - set(step.bindings)),
                         unknown=sorted(set(step.bindings) - set(process.input)))
        kind = 'operator' if process.operator is not None else 'route' if process.route is not None else 'script'
        payload = deepcopy(getattr(process, kind))
        params = _resolve({**process.parameters, **step.params}, globals_, inputs, (*where, 'params')) if initial else {}
        if '_input_names' in params:
            raise _error('_input_names is engine-owned', (*where, 'params', '_input_names'))
        context = _resolve(step.context_params, globals_, inputs, (*where, 'context_params')) if initial else {}
        nodes.append({'id': key, 'kind': kind, kind: payload, 'params': params,
                      'context_params': context, 'title': step.title, 'position': {'x': 0, 'y': 0},
                      'input_count': step.input_count if step.input_count is not None else len(process.input)})
        handles = set()
        for index, (port, descriptor) in enumerate(process.input.items()):
            binding = step.bindings[port]
            reference = binding.ref if binding.ref is not None else 'workflow.' + binding.input
            origin, output, producer = _reference(reference, document, (*where, 'in', port))
            _type_binding(producer, descriptor, binding, (*where, 'in', port))
            handle = _handle(descriptor, index)
            if handle in handles:
                raise _error('Duplicate process input handle', ('processes', step.process, 'input', port))
            handles.add(handle)
            edges.append({'id': binding.id or f'{origin}-{output}-{key}-{handle}', 'source': origin,
                          'target': key, 'sourceHandle': output, 'targetHandle': handle,
                          **({'adaptation': _plain(binding.adaptation)} if binding.adaptation is not None else {})})
    runtime = _plain(document.workflow.runtime)
    if document.workflow.emit:
        runtime['workflow_outputs'] = {}
        for name, ref in document.workflow.emit.items():
            node, handle, _ = _reference(ref.ref, document, ('workflow', 'emit', name))
            runtime['workflow_outputs'][name] = ('sources.' + node if node in document.workflow.take
                                                 else f'steps.{node}.{handle}')
    graph = {'schema_version': 2, 'name': document.workflow.name, 'base_dir': str(directory),
             'nodes': nodes, 'edges': edges, 'params': globals_ if initial else {},
             'memory': _plain(document.workflow.memory), 'runtime': runtime,
             'manifest_extra': _plain(document.workflow.manifest_extra),
             'plugin_lock': _plain(document.workflow.plugin_lock), 'interface': _plain(document.workflow.interface)}
    from .graph_models import Graph
    from .parameters import restore_graph, split_graph
    try:
        if initial:
            graph = _validate(Graph, graph, ('workflow',))
            if parameters.get('format') == 'operon.graph-parameters':
                # Existing values always win over extracted inline defaults.
                topology, _ = split_graph(graph)
                graph = restore_graph(topology, parameters)
            elif set(parameters) - {'params'}:
                raise _error('Initial parameter data accepts params or a complete frozen snapshot', ('parameters',))
            if catalog is not None:
                from .parameters import freeze_graph
                from .resolver import as_catalog
                snapshot = as_catalog(catalog)
                graph = freeze_graph(graph, {'operators': list(snapshot.operators), 'readers': list(snapshot.readers)}, directory)
        else:
            graph = restore_graph(graph, parameters)
        _reject_engine_values(graph)
        if ui is not None:
            _bounded(ui, ('ui',))
            _restore_ui(graph, ui)
        spec = WorkflowSpec.from_graph(graph)
    except ContractError:
        raise
    except (ValueError, TypeError, KeyError) as exc:
        raise _error(f'Invalid normalized graph: {exc}', ('parameters',) if not initial else ('workflow',)) from exc
    from .limits import check_graph_size
    check_graph_size(spec)
    _, frozen = split_graph(graph)
    return _result(spec, document, frozen, inputs, environments, selected)


def load_workflow(path, **options):
    path = Path(path).resolve()
    try:
        if path.stat().st_size > _MAX_BYTES:
            raise _error('Workflow YAML exceeds its byte limit', code='payload_too_large', limit=_MAX_BYTES)
        value = parse(path.read_text(encoding='utf-8-sig'))
    except (OSError, UnicodeError) as exc:
        raise _error(f'Cannot read workflow: {exc}', code='workflow_resource_error') from exc
    ui_path = path.parent / 'ui.json'
    if 'ui' not in options and ui_path.exists():
        options['ui'] = _read_json(path.parent, 'ui.json', ('ui',))
    return normalize(value, path.parent, **options)


def normalize_legacy(value, directory='.', *, initial=False, catalog=None, profile=None, overrides=None):
    """Dedicated compatibility import; legacy parsing does not create an engine."""
    try:
        if 'nodes' in value:
            if value.get('format') == 'operon.workflow':
                spec = _validate(WorkflowSpec, value)
            else:
                from .graph_models import Graph
                spec = WorkflowSpec.from_graph(_validate(Graph, value))
        elif isinstance(value.get('steps'), list):
            if not initial or catalog is None:
                raise _error('Legacy task YAML must be explicitly imported with a catalog, then saved as v2',
                             code='legacy_import_required')
            from .graph_compiler import import_manifest
            from .resolver import as_catalog
            snapshot = as_catalog(catalog)
            graph = import_manifest(yaml.safe_dump(value), '.',
                                    {'operators': list(snapshot.operators), 'readers': list(snapshot.readers)},
                                    Path(directory).resolve(), resolve_inputs=False)
            spec = WorkflowSpec.from_graph(graph)
        else:
            from operon.workflow_spec import compile_spec
            spec = WorkflowSpec.from_graph(compile_spec(value, directory))
        if initial and catalog is not None:
            from .legacy import freeze_spec
            from .resolver import as_catalog
            spec = freeze_spec(spec, as_catalog(catalog), Path(directory).resolve())
    except ContractError:
        raise
    except (ValueError, TypeError, KeyError) as exc:
        raise _error(f'Invalid legacy workflow: {exc}') from exc
    files = export_mapping(spec, directory)
    return normalize(files['workflow.yaml'], directory, parameters=files['parameters.json'],
                     inputs=files['inputs.json'], environments=files.get('environments.json', {}),
                     ui=files['ui.json'], profile=profile, overrides=overrides)


def _reject_engine_values(graph, path=('parameters', 'nodes')):
    for node in graph.nodes:
        if '_input_names' in node.params:
            raise _error('_input_names is engine-owned', (*path, node.id, 'params', '_input_names'))
        if node.source and '_input_names' in node.source.args:
            raise _error('_input_names is engine-owned', (*path, node.id, 'args', '_input_names'))
        if node.route:
            _reject_engine_values(node.route.graph, (*path, node.id, 'route', 'nodes'))


def export_mapping(workflow, directory='.'):
    """Return a canonical v2 project, without writing or loading library defaults."""
    if isinstance(workflow, NormalizedForeignWorkflow):
        from .invocation_lowering import export_foreign_mapping
        return export_foreign_mapping(workflow)
    normalized = workflow if isinstance(workflow, NormalizedWorkflow) else None
    spec = normalized.spec if normalized else workflow if isinstance(workflow, WorkflowSpec) else WorkflowSpec.from_graph(workflow)
    from .parameters import split_graph
    topology, parameters = split_graph(spec.to_legacy_dict())
    ui = _extract_ui(topology)
    processes, take, steps, inputs = {}, {}, {}, {}
    input_names, output_names = {}, {}
    for node in topology['nodes']:
        key = node['id']
        node.pop('position')
        if node['kind'] == 'source':
            source = node['source']
            path = source.pop('path')
            if path and (source.get('location') or {}).get('kind') != 'ssh':
                path = str((Path(spec.base_dir) / path).resolve())
            inputs[key] = path
            source['path'] = {'input': key}
            declaration = {'type': 'form'}
            if normalized and key in normalized.document.workflow.take:
                declaration = normalized.document.workflow.take[key].model_dump(mode='json', exclude_none=True)
            take[key] = {**declaration, 'source': source, 'title': node['title']}
            continue
        process = {'runner': 'native', node['kind']: node[node['kind']], 'input': {}, 'output': {}}
        # Retain authored boundary declarations and policy while values live only
        # in the independent snapshot. Canonical process IDs match stable nodes.
        old = None
        if normalized and key in normalized.document.workflow.steps:
            old_step = normalized.document.workflow.steps[key]
            old = normalized.document.processes[old_step.process]
            process.update({k: v for k, v in old.model_dump(mode='json', exclude_none=True).items()
                            if k in ('runner', 'environment', 'resources')})
            for group in ('input', 'output'):
                declarations = getattr(old, group)
                names = {}
                for index, (name, descriptor) in enumerate(declarations.items()):
                    handle = _handle(descriptor, index, output=group == 'output', total=len(declarations))
                    if handle in names:
                        raise _error('Duplicate declared port handle', ('processes', key, group, name))
                    names[handle] = name
                    process[group][name] = {**descriptor.model_dump(mode='json', exclude_none=True), 'handle': handle}
                (input_names if group == 'input' else output_names)[key] = names
        processes[key] = process
        steps[key] = {'process': key, 'in': {}, 'title': node['title'], 'input_count': node['input_count']}
    node_kinds = {node['id']: node['kind'] for node in topology['nodes']}
    def output_name(node, handle):
        if node_kinds[node] == 'source':
            return 'workflow.' + node
        port = output_names.get(node, {}).get(handle, handle)
        processes[node]['output'].setdefault(port, {'type': 'form', 'handle': handle})
        return node + '.' + port
    for edge in topology['edges']:
        target, handle = edge['target'], edge.get('targetHandle', 'in-0')
        port = input_names.get(target, {}).get(handle, handle)
        processes[target]['input'].setdefault(port, {'type': 'form', 'handle': handle})
        binding = {'ref': output_name(edge['source'], edge.get('sourceHandle', 'out')), 'id': edge['id']}
        if edge.get('adaptation') is not None:
            binding['adaptation'] = edge['adaptation']
        steps[target]['in'][port] = binding
    emit = {}
    runtime = deepcopy(topology.get('runtime') or {})
    for name, reference in runtime.pop('workflow_outputs', {}).items():
        if not isinstance(reference, str):
            raise _error('Legacy workflow output is not representable', ('runtime', 'workflow_outputs', name), code='unsupported_export')
        if reference.startswith('sources.') and reference[8:] in take:
            emit[name] = {'ref': 'workflow.' + reference[8:]}
        elif reference.startswith('steps.'):
            node, _, handle = reference[6:].rpartition('.')
            if node not in processes:
                raise _error('Legacy output references unknown node', ('runtime', 'workflow_outputs', name), code='unknown_reference')
            emit[name] = {'ref': output_name(node, handle)}
        else:
            raise _error('Legacy workflow output cannot be represented', ('runtime', 'workflow_outputs', name), code='unsupported_export')
    body = {'name': spec.name, 'take': take, 'steps': steps, 'emit': emit,
            'memory': deepcopy(topology['memory']), 'runtime': runtime,
            'manifest_extra': deepcopy(topology['manifest_extra']),
            'plugin_lock': deepcopy(topology['plugin_lock']), 'interface': deepcopy(topology['interface'])}
    document = {'format': 'operon.workflow', 'schema_version': 2, 'params_file': 'parameters.json',
                'inputs_file': 'inputs.json', 'processes': processes, 'workflow': body, 'profiles': {}}
    files = {'parameters.json': parameters, 'inputs.json': inputs, 'ui.json': ui}
    if normalized:
        body['defaults'] = normalized.profile.model_dump(mode='json', exclude_none=True)
        document['profiles'] = {key: value.model_dump(mode='json', exclude_none=True)
                                for key, value in normalized.document.profiles.items()}
        if normalized.environments:
            document['environments_file'] = 'environments.json'
            files['environments.json'] = _plain(normalized.environments)
    _validate(AuthoringDocument, document)
    files['workflow.yaml'] = document
    return files


def export_workflow(workflow, directory, *, legacy=False):
    """Write a new project only; never overwrite saved values or existing files."""
    directory = Path(directory).resolve()
    if legacy:
        if isinstance(workflow, NormalizedForeignWorkflow):
            raise _error('Legacy graph YAML cannot represent foreign invocation units', code='unsupported_export')
        if isinstance(workflow, NormalizedWorkflow):
            for name, process in workflow.document.processes.items():
                for group in ('input', 'output'):
                    ports = getattr(process, group)
                    for index, (port_name, port) in enumerate(ports.items()):
                        handle = _handle(port, index, output=group == 'output', total=len(ports))
                        if port.type != 'form' or port.format or port.contract or port_name != handle:
                            raise _error('Legacy export cannot preserve named or typed authoring ports',
                                         ('processes', name, group, port_name), code='unsupported_export')
            if workflow.document.profiles or workflow.environments or any(
                    process.environment or any(v is not None for v in process.resources.model_dump().values())
                    for process in workflow.document.processes.values()) or any(
                    value for value in workflow.document.workflow.defaults.model_dump(exclude_none=True).values()):
                raise _error('Legacy export cannot preserve v2 execution policy', code='unsupported_export')
            workflow = workflow.spec
        from operon.workflow_spec import export_workflow as export_v1
        return export_v1(workflow.to_legacy_dict() if isinstance(workflow, WorkflowSpec) else workflow, directory)
    files = export_mapping(workflow, directory)
    if directory.exists() and any(directory.iterdir()):
        raise _error('Export directory must be empty; existing files were preserved', code='export_exists')
    directory.mkdir(parents=True, exist_ok=True)
    for name, value in files.items():
        text = yaml.safe_dump(value, sort_keys=False, allow_unicode=True) if name.endswith('.yaml') else json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
        # Exclusive creation protects against a concurrently created project.
        with (directory / name).open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(text)
    return {'path': str(directory / 'workflow.yaml'), 'files': sorted(files)}
