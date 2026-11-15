"""Static foreign-process lowering into the shared RunPlan invocation ABI.

There is no scheduler here. File edges become the same unit bindings consumed
by RunPlanExecutor; the existing unit_dependencies validator owns DAG checks.
"""
from __future__ import annotations

from dataclasses import dataclass
from copy import deepcopy
import hashlib
from pathlib import Path, PurePosixPath
import re
from typing import Any, Mapping, TYPE_CHECKING

from pydantic import Field, field_validator

from operon.contracts.base import ContractModel, _freeze, domain_digest, sha256_hex
from operon.contracts.workflow import FrozenParameters, WorkflowSpec
from operon.contracts.run_plan import (
    CodeRef, EnvironmentRequirement, InvocationSpec, OutputContract, ParametersRef,
    PlacementPolicy, ResourceRequestSpec, RunPlan, TargetSpec, UnitSpec,
    validate_relative_path,
)

if TYPE_CHECKING:
    from .authoring_v2 import AuthoringDocument, Profile


FOREIGN_RUNNERS = frozenset(('python_script', 'r_script', 'command'))


class EnvironmentDeclaration(ContractModel):
    requirement: EnvironmentRequirement
    executable: str = Field(min_length=1, max_length=2048)

    @field_validator('executable')
    @classmethod
    def _relative_executable(cls, value):
        validate_relative_path(value)
        if value in ('.', './') or '\\' in value:
            raise ValueError('Executable must use a package-relative file path with forward slashes')
        return value


@dataclass(frozen=True)
class NormalizedForeignWorkflow:
    document: 'AuthoringDocument'
    parameters: Mapping[str, Any]
    inputs: Mapping[str, str]
    environments: Mapping[str, Any]
    profile: 'Profile'
    directory: str
    ui: Mapping[str, Any]

    def compile(self, catalog=None, *, root=None, require_files=False):
        from .compiler import WorkflowCompiler
        return WorkflowCompiler().compile_authoring(self, catalog, root=root, require_files=require_files)


@dataclass(frozen=True)
class NormalizedMixedWorkflow(NormalizedForeignWorkflow):
    native_specs: Mapping[str, WorkflowSpec]
    native_bindings: Mapping[str, Any]
    foreign: NormalizedForeignWorkflow
    foreign_boundaries: Mapping[str, Any]


def _helpers():
    # Lazy import keeps authoring model import and the shared compiler acyclic.
    from . import authoring_v2 as author
    return author


def _script(process, process_name):
    author = _helpers()
    from operon.script_operators import validate_script
    try:
        snapshot = validate_script(author._plain(process.script))
    except (ValueError, TypeError, KeyError) as exc:
        raise author._error(str(exc), ('processes', process_name, 'script'), code='invalid_script') from exc
    expected = 'python' if process.runner == 'python_script' else 'r'
    if snapshot['language'] != expected:
        raise author._error('Script language differs from the declared runner',
                            ('processes', process_name, 'script', 'language'))
    for group, declared in (('inputs', process.input), ('outputs', process.output)):
        if set(snapshot[group]) != set(declared):
            raise author._error('Script file-port names differ from process declarations',
                                ('processes', process_name, group), code='incompatible_port')
        for name, port in declared.items():
            if port.format and snapshot[group][name]['format'] != port.format:
                raise author._error('Script file-port format differs from process declaration',
                                    ('processes', process_name, group, name), code='incompatible_port')
    return snapshot


def _parameters_for_script(snapshot, values, path):
    # Validation never adds defaults or coerces numeric-looking strings.
    from jsonschema import Draft202012Validator
    author = _helpers()
    errors = sorted(Draft202012Validator(snapshot['parameters_schema']).iter_errors(author._plain(values)),
                    key=lambda error: tuple(str(x) for x in error.path))
    if errors:
        raise author._error('Script parameters do not satisfy their frozen schema', path,
                            code='invalid_parameters', errors=[{
                                'path': list(path) + list(error.path), 'message': error.message,
                                'type': error.validator} for error in errors])


def _port_reference(value, document, path):
    """Resolve a named file endpoint; no ordering, expansion or execution."""
    author = _helpers()
    node, handle, descriptor = author._reference(value, document, path)
    if node in document.workflow.take:
        return node, None, descriptor
    process = document.processes[document.workflow.steps[node].process]
    matches = [name for index, (name, port) in enumerate(process.output.items())
               if author._handle(port, index, output=True, total=len(process.output)) == handle]
    if len(matches) != 1:
        raise author._error('Output port cannot be mapped uniquely', path, code='ambiguous_reference')
    return node, matches[0], descriptor


def normalize_foreign(document, directory, *, parameters, inputs, environments, profile, initial=False, ui=None, catalog=None):
    author = _helpers()
    selected = {step.process for step in document.workflow.steps.values()}
    for name in selected:
        if name not in document.processes:
            raise author._error('Step references an unknown process', ('processes', name), code='unknown_reference')
    native = sorted(name for name in selected if document.processes[name].runner not in FOREIGN_RUNNERS)
    if native:
        return normalize_mixed(document, directory, parameters=parameters, inputs=inputs, environments=environments,
                               profile=profile, initial=initial, ui=ui, catalog=catalog)
    for name, value in (('runtime', document.workflow.runtime), ('manifest_extra', document.workflow.manifest_extra),
                        ('plugin_lock', document.workflow.plugin_lock), ('interface', document.workflow.interface)):
        if value:
            raise author._error('Native graph settings cannot silently configure a foreign invocation',
                                ('workflow', name), code='unsupported_boundary')
    if document.workflow.memory != {'enabled': True, 'auto_spill': True}:
        raise author._error('Foreign memory must be declared as a full-process resource reservation',
                            ('workflow', 'memory'), code='unsupported_boundary')
    globals_ = parameters.get('params', {})
    if not isinstance(globals_, dict):
        raise author._error('Global parameter values must be an object', ('parameters', 'params'))
    replay = parameters.get('format') == 'operon.frozen-parameters'
    if replay:
        if type(parameters.get('schema_version')) is not int:
            raise author._error('Parameter schema_version must be an integer', ('parameters', 'schema_version'))
        frozen = author._validate(FrozenParameters, parameters, ('parameters',))
        if frozen.sources or set(frozen.steps) != set(document.workflow.steps):
            raise author._error('Foreign parameters require exactly the declared steps and no Reader values',
                                ('parameters',), code='invalid_parameters')
        values = author._plain(frozen.steps)
    elif not initial:
        raise author._error('Foreign replay requires independent frozen parameter values',
                            ('params_file',), code='missing_frozen_parameters')
    elif set(parameters) - {'params'}:
        raise author._error('Initial foreign parameters accept globals or a complete frozen snapshot',
                            ('parameters',), code='invalid_parameters')
    else:
        values = {}
    declared_environments = {}
    for name, value in environments.items():
        if not re.fullmatch(author._ID, name):
            raise author._error('Environment names must be stable identifiers', ('environments', name))
        declaration = author._validate(EnvironmentDeclaration, value, ('environments', name))
        declared_environments[name] = declaration.model_dump(mode='json')
    resolved_inputs = {}
    for name, take in document.workflow.take.items():
        at = ('workflow', 'take', name)
        if take.type != 'path' and not _is_form_port(take):
            raise author._error('Foreign invocations require declared path boundaries', at, code='unsupported_boundary')
        if (take.source.reader or take.source.args or take.source.location or take.source.labels
                or take.source.dims != ('sample', 'feature')):
            raise author._error('Foreign path inputs require explicit file materialization; Reader/remote metadata is unsupported',
                                (*at, 'source'), code='unsupported_boundary')
        expression = take.source.path if take.source.path is not None else {'input': name}
        path = author._resolve(expression, globals_, inputs, (*at, 'source', 'path'))
        if not isinstance(path, str) or not path:
            raise author._error('File input must resolve to a nonempty path', (*at, 'source', 'path'))
        resolved_inputs[name] = str((Path(directory) / path).resolve())
    for node, step in document.workflow.steps.items():
        process = document.processes[step.process]
        at = ('workflow', 'steps', node)
        if step.context_params:
            raise author._error('Foreign processes use their independent parameter JSON', (*at, 'context_params'),
                                code='unsupported_boundary')
        if not process.environment or process.environment not in declared_environments:
            raise author._error('Foreign process requires a declared immutable environment',
                                ('processes', step.process, 'environment'), code='unknown_reference')
        if set(step.bindings) != set(process.input):
            raise author._error('Step bindings must exactly match process input ports', (*at, 'in'))
        if step.input_count is not None and step.input_count != len(process.input):
            raise author._error('input_count differs from declared file ports', (*at, 'input_count'))
        for group in ('input', 'output'):
            for name, port in getattr(process, group).items():
                if port.type != 'path' and not _is_form_port(port):
                    raise author._error('Foreign invocations support explicit file boundaries only',
                                        ('processes', step.process, group, name), code='unsupported_boundary')
        snapshot = _script(process, step.process) if process.runner != 'command' else None
        if not replay:
            defaults = {name: field['default'] for name, field in
                        (snapshot or {}).get('parameters_schema', {}).get('properties', {}).items() if 'default' in field}
            values[node] = author._resolve({**defaults, **process.parameters, **step.params}, globals_, inputs, (*at, 'params'))
            if process.command:
                for token in process.command.argv:
                    if isinstance(token, author.Param) and token.param not in values[node] and token.param in globals_:
                        values[node][token.param] = author._plain(globals_[token.param])
        if '_input_names' in values[node]:
            raise author._error('_input_names is engine-owned', (*at, 'params', '_input_names'))
        if snapshot:
            _parameters_for_script(snapshot, values[node], ('parameters', 'steps', node))
        for port, binding in step.bindings.items():
            reference = binding.ref if binding.ref is not None else 'workflow.' + binding.input
            producer_node, _, producer = _port_reference(reference, document, (*at, 'in', port))
            if producer_node == node:
                raise author._error('An invocation cannot consume its own unpublished output',
                                    (*at, 'in', port), code='invalid_plan_edge')
            author._type_binding(producer, process.input[port], binding, (*at, 'in', port))
            if producer.format and process.input[port].format and producer.format != process.input[port].format:
                raise author._error('File formats differ; declare an explicit converter process',
                                    (*at, 'in', port), code='incompatible_port')
            if binding.adaptation and binding.adaptation.get('mode', 'auto') != 'disabled':
                raise author._error('File conversions require an explicit converter invocation',
                                    (*at, 'in', port, 'adaptation'), code='unsupported_boundary')
    for name, reference in document.workflow.emit.items():
        node, port, _ = _port_reference(reference.ref, document, ('workflow', 'emit', name))
        if port is None:
            raise author._error('Foreign emitted results require a producing process',
                                ('workflow', 'emit', name), code='unsupported_boundary')
    canonical_document = document.model_dump(mode='json', by_alias=True)
    for name in selected:
        if document.processes[name].runner != 'command':
            canonical_document['processes'][name]['script'] = _script(document.processes[name], name)
    document = author._validate(author.AuthoringDocument, canonical_document)
    frozen = FrozenParameters(steps=values, params=globals_)
    ui = author._plain(ui or {'positions': {}})
    if (not isinstance(ui, dict) or set(ui) - {'positions', 'routes'}
            or not isinstance(ui.get('positions'), dict) or ui.get('routes')):
        raise author._error('Foreign UI metadata requires positions and no nested routes', ('ui',))
    if set(ui['positions']) - (set(document.workflow.take) | set(document.workflow.steps)):
        raise author._error('UI positions reference unknown nodes', ('ui', 'positions'))
    from .graph_models import Position
    for node, position in ui['positions'].items():
        ui['positions'][node] = author._validate(Position, position, ('ui', 'positions', node)).model_dump(mode='json')
    value = NormalizedForeignWorkflow(document, _freeze(frozen.model_dump(mode='json')),
        _freeze(resolved_inputs), _freeze(declared_environments), profile, str(Path(directory).resolve()),
        _freeze(ui))
    # Lowering is static and also validates argv, resources and the common DAG.
    lower_foreign(value)
    return value


def export_foreign_mapping(value):
    author = _helpers()
    document = value.document.model_dump(mode='json', by_alias=True, exclude_none=True)
    document['params_file'] = 'parameters.json'
    document['inputs_file'] = 'inputs.json'
    document['environments_file'] = 'environments.json'
    document['workflow']['defaults'] = value.profile.model_dump(mode='json', exclude_none=True)
    for name, take in document['workflow']['take'].items():
        take['source']['path'] = {'input': name}
        take['source']['args'] = {}
    for process in document['processes'].values():
        process.pop('parameters', None)
    for step in document['workflow']['steps'].values():
        step.pop('params', None)
        step.pop('context_params', None)
    if isinstance(value, NormalizedMixedWorkflow):
        from .parameters import split_graph
        for node, spec in value.native_specs.items():
            native = next(item for item in spec.nodes if item.id == node)
            if native.route:
                topology, _ = split_graph(native.route.graph.to_legacy_dict())
                author._extract_ui(topology)
                process = document['processes'][document['workflow']['steps'][node]['process']]
                process['route']['graph'] = topology
    return {'workflow.yaml': document, 'parameters.json': author._plain(value.parameters),
            'inputs.json': author._plain(value.inputs), 'environments.json': author._plain(value.environments),
            'ui.json': author._plain(value.ui)}


def _output_contracts(process, name):
    author = _helpers()
    result, seen = {}, set()
    for port, declaration in process.output.items():
        if _is_form_port(declaration):
            result[port] = {'path': port + '/value.bpform', 'representation': 'form',
                            'metadata': {'format': 'bpform', 'contract': author._plain(declaration.contract)}}
            continue
        extension = declaration.format or 'bin'
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}', extension):
            raise author._error('Output format must be a portable file suffix',
                                ('processes', name, 'output', port, 'format'), code='unsupported_boundary')
        path = port + '.' + extension
        if path.casefold() in seen:
            raise author._error('Declared output paths overlap', ('processes', name, 'output'), code='overlapping_outputs')
        seen.add(path.casefold())
        representation = 'json' if extension == 'json' else 'table' if extension in ('csv', 'tsv') else 'file'
        result[port] = {'path': path, 'representation': representation,
                        'metadata': {'format': extension, 'contract': author._plain(declaration.contract)}}
    if not result:
        raise author._error('Foreign invocations require a declared publishable output',
                            ('processes', name, 'output'), code='unsupported_boundary')
    return result


def _is_form_port(port):
    return port.type == 'form' and port.format == 'bpform'


def _mixed_values(parameters, document, initial):
    """Use the existing workflow parameter wire shape, including nested routes."""
    author = _helpers()
    if parameters.get('format') != 'operon.workflow-parameters':
        if not initial or set(parameters) - {'params'}:
            raise author._error('Mixed replay requires the independent workflow parameter snapshot',
                                ('parameters',), code='missing_frozen_parameters')
        if not isinstance(parameters.get('params', {}), dict):
            raise author._error('Global parameters must be an object', ('parameters', 'params'))
        return {'format': 'operon.workflow-parameters', 'schema_version': 1,
                'params': deepcopy(parameters.get('params', {})), 'steps': {}, 'sources': {}}, False
    if (set(parameters) != {'format', 'schema_version', 'params', 'steps', 'sources'}
            or type(parameters['schema_version']) is not int or parameters['schema_version'] != 1
            or any(not isinstance(parameters[key], dict) for key in ('params', 'steps', 'sources'))
            or set(parameters['steps']) != set(document.workflow.steps)
            or set(parameters['sources']) != set(document.workflow.take)):
        raise author._error('Frozen values must exactly match mixed workflow nodes', ('parameters',), code='invalid_parameters')
    for node, entry in parameters['steps'].items():
        process = document.processes[document.workflow.steps[node].process]
        expected = {'params', 'context_params'} | ({'route'} if process.route else set())
        if not isinstance(entry, dict) or set(entry) != expected or any(not isinstance(entry[key], dict) for key in expected):
            raise author._error('Invalid frozen step values', ('parameters', 'steps', node), code='invalid_parameters')
        if '_input_names' in entry['params']:
            raise author._error('_input_names is engine-owned', ('parameters', 'steps', node, 'params'))
        if process.runner in FOREIGN_RUNNERS and entry['context_params']:
            raise author._error('Foreign steps cannot consume native context values', ('parameters', 'steps', node))
        if process.route:
            author._parameter_snapshot(entry['route'], ('parameters', 'steps', node, 'route'))
    for node, entry in parameters['sources'].items():
        if not isinstance(entry, dict) or set(entry) != {'args'} or not isinstance(entry['args'], dict):
            raise author._error('Invalid frozen Reader values', ('parameters', 'sources', node), code='invalid_parameters')
    return deepcopy(parameters), True


def _exchange_schema(port):
    """Only author-declared metadata crosses the materialized Form boundary."""
    from src.core.contracts import unknown
    author = _helpers()
    schema = {**unknown(), **author._plain(port.contract)}
    if schema.get('kind', 'form') != 'form':
        raise author._error('A bpform Form port cannot declare a non-Form contract', code='incompatible_port')
    schema['kind'] = 'form'
    schema.setdefault('data_format', {'logical_type': 'form', 'representations': ['form'], 'metadata': {}})
    if schema['data_format'].get('logical_type') != 'form' or 'form' not in schema['data_format'].get('representations', []):
        raise author._error('A bpform boundary requires the native Form representation', code='incompatible_port')
    return schema


def _boundary_id(node, port):
    return 'exchange_' + hashlib.sha256((node + '/' + port).encode('utf-8')).hexdigest()[:24]


def normalize_mixed(document, directory, *, parameters, inputs, environments, profile, initial=False, ui=None, catalog=None):
    """Partition only explicit materializations; native internals stay with Graph."""
    author = _helpers()
    from .graph_models import Graph, Position
    from .parameters import freeze_graph, restore_graph, split_graph
    from .resolver import as_catalog

    directory = Path(directory).resolve()
    values, replay = _mixed_values(parameters, document, initial)
    globals_ = values['params']
    native = {node for node, step in document.workflow.steps.items()
              if document.processes[step.process].runner == 'native'}
    # These graph-wide settings cannot be copied into several native tasks.
    if document.workflow.interface or document.workflow.manifest_extra:
        raise author._error('Mixed invocations cannot duplicate a graph interface or arbitrary manifest metadata',
                            ('workflow',), code='unsupported_boundary')
    forbidden = {'exchange_inputs', 'exchange_outputs', 'exchange_aliases', 'exchange_contracts', 'workflow_outputs', 'execution'}
    if forbidden & set(document.workflow.runtime):
        raise author._error('Mixed materialization and placement fields are compiler-owned',
                            ('workflow', 'runtime'), code='unsupported_boundary')
    if document.workflow.memory.get('keep'):
        raise author._error('Mixed retention must be declared inside a native route subgraph',
                            ('workflow', 'memory', 'keep'), code='unsupported_boundary')
    ui = author._plain(ui or {'positions': {}, 'routes': {}})
    if (not isinstance(ui, dict) or set(ui) - {'positions', 'routes'}
            or not isinstance(ui.get('positions'), dict) or not isinstance(ui.get('routes', {}), dict)
            or set(ui['positions']) - (set(document.workflow.take) | set(document.workflow.steps))
            or set(ui.get('routes', {})) - native):
        raise author._error('Invalid mixed workflow UI metadata', ('ui',))
    ui.setdefault('routes', {})
    for node, position in ui['positions'].items():
        ui['positions'][node] = author._validate(Position, position, ('ui', 'positions', node)).model_dump(mode='json')
    resolved_inputs = {}
    for node, take in document.workflow.take.items():
        if take.source.location:
            raise author._error('Mixed input files require explicit deployment bindings',
                                ('workflow', 'take', node, 'source', 'location'), code='unsupported_boundary')
        path = author._resolve(take.source.path if take.source.path is not None else {'input': node},
                               globals_, inputs, ('workflow', 'take', node, 'source', 'path'))
        if not isinstance(path, str) or not path:
            raise author._error('Input must resolve to a nonempty path', ('inputs', node))
        resolved_inputs[node] = str((directory / path).resolve())
        if not replay:
            values['sources'][node] = {'args': author._resolve(take.source.args, globals_, inputs,
                                                              ('workflow', 'take', node, 'source', 'args'))}

    # Validate every boundary before catalog resolution so unsupported codecs
    # identify the actual edge, never an incidental missing operator.
    endpoints = {}
    for node, step in document.workflow.steps.items():
        process = document.processes[step.process]
        if set(step.bindings) != set(process.input):
            raise author._error('Step bindings must exactly match process input ports', ('workflow', 'steps', node, 'in'))
        for port, binding in step.bindings.items():
            at = ('workflow', 'steps', node, 'in', port)
            ref = binding.ref if binding.ref is not None else 'workflow.' + binding.input
            producer, output, declaration = _port_reference(ref, document, at)
            if producer == node:
                raise author._error('An invocation cannot consume its own unpublished output', at, code='invalid_plan_edge')
            endpoints[node, port] = (producer, output, declaration)
            if output is not None and (node in native or producer in native):
                if not _is_form_port(declaration) or not _is_form_port(process.input[port]):
                    raise author._error('Native invocation boundaries require explicit type form and format bpform on both ports',
                                        at, code='unsupported_boundary', producer=ref)
            elif node in native and not _is_form_port(declaration):
                take = document.workflow.take[producer]
                if not take.source.reader:
                    raise author._error('Native raw-file input requires an explicit Reader or a form/bpform boundary',
                                        at, code='unsupported_boundary', producer=ref)
            author._type_binding(declaration, process.input[port], binding, at)

    projected = document.model_dump(mode='json', by_alias=True)
    projected['processes'] = {name: item for name, item in projected['processes'].items()
                              if document.processes[name].runner in FOREIGN_RUNNERS}
    wf = projected['workflow']
    wf.update(steps={node: step for node, step in wf['steps'].items() if node not in native},
              take={}, emit={}, runtime={}, memory={'enabled': True, 'auto_spill': True},
              manifest_extra={}, plugin_lock={}, interface=None)
    foreign_boundaries = {}
    foreign_inputs = {}
    for node, step in wf['steps'].items():
        for port in step['in']:
            producer, output, declaration = endpoints[node, port]
            if producer in native:
                key = _boundary_id(producer, output)
                if key in document.workflow.take or key in document.workflow.steps:
                    raise author._error('Generated boundary identity collides with a workflow node', ('workflow',))
                wf['take'][key] = {'type': 'form', 'format': 'bpform', 'contract': author._plain(declaration.contract),
                                   'source': {'path': {'input': key}}}
                step['in'][port] = {**step['in'][port], 'ref': 'workflow.' + key}
                step['in'][port].pop('input', None)
                foreign_inputs[key] = str(directory / '.operon-boundaries' / (key + '.bpform'))
                foreign_boundaries[key] = (producer, output)
            elif output is None:
                wf['take'][producer] = document.workflow.take[producer].model_dump(mode='json')
                foreign_inputs[producer] = resolved_inputs[producer]
    foreign_parameters = {'params': globals_}
    if replay:
        foreign_parameters = FrozenParameters(params=globals_, steps={node: values['steps'][node]['params']
            for node in wf['steps']}).model_dump(mode='json')
    foreign_doc = author._validate(author.AuthoringDocument, projected)
    foreign = normalize_foreign(foreign_doc, directory, parameters=foreign_parameters,
        inputs={**inputs, **foreign_inputs}, environments=environments, profile=profile, initial=not replay,
        ui={'positions': {node: pos for node, pos in ui['positions'].items()
                          if node in wf['steps'] or node in wf['take']}})
    for node, params in foreign.parameters['steps'].items():
        values['steps'][node] = {'params': author._plain(params), 'context_params': {}}

    native_specs, native_bindings = {}, {}
    snapshot = as_catalog(catalog)
    mapping = {'operators': list(snapshot.operators), 'readers': list(snapshot.readers)}
    canonical_document = document.model_dump(mode='json', by_alias=True)
    for name, process in foreign.document.processes.items():
        canonical_document['processes'][name] = process.model_dump(mode='json')
    for node in document.workflow.steps:
        if node not in native:
            continue
        step = document.workflow.steps[node]
        process = document.processes[step.process]
        if not process.environment or process.environment not in foreign.environments:
            raise author._error('Native invocation requires a declared immutable environment',
                                ('processes', step.process, 'environment'), code='unknown_reference')
        if process.script:
            raise author._error('Mixed native scripts require an operator/route binding or a foreign script runner',
                                ('processes', step.process, 'script'), code='unsupported_boundary')
        kind = 'operator' if process.operator else 'route'
        payload = author._plain(getattr(process, kind))
        entry = values['steps'].get(node, {})
        if kind == 'route' and replay:
            topology, _ = split_graph(payload['graph'])
            payload['graph'] = restore_graph(topology, entry['route']).model_dump(mode='json')
        actual = {'id': node, 'kind': kind, kind: payload, 'title': step.title,
                  'position': ui['positions'].get(node, {'x': 0, 'y': 0}),
                  'params': deepcopy(entry['params']) if replay else author._resolve(
                      {**process.parameters, **step.params}, globals_, inputs, ('workflow', 'steps', node, 'params')),
                  'context_params': deepcopy(entry['context_params']) if replay else author._resolve(
                      step.context_params, globals_, inputs, ('workflow', 'steps', node, 'context_params')),
                  'input_count': step.input_count if step.input_count is not None else len(process.input)}
        sources, edges, bindings, exchange_inputs, contracts = {}, [], {}, [], {}
        for index, (port, declaration) in enumerate(process.input.items()):
            producer, output, source_port = endpoints[node, port]
            key = producer if output is None else _boundary_id(producer, output)
            if key == node or output is not None and key in (set(document.workflow.take) | set(document.workflow.steps)):
                raise author._error('Boundary identity collides with native node', ('workflow', 'steps', node))
            exchange = output is not None or _is_form_port(source_port)
            if output is None:
                take = document.workflow.take[producer]
                source = take.source.model_dump(mode='json')
                source.update(path=resolved_inputs[producer], args=deepcopy(values['sources'][producer]['args']))
                bindings[key] = 'input:' + producer
            else:
                source = {'path': str(directory / '.operon-boundaries' / (key + '.bpform')),
                          'reader': None, 'args': {}}
                bindings[key] = 'artifact:' + producer + '/' + output
            if exchange:
                if source.get('reader') or source.get('args'):
                    raise author._error('Form exchange input cannot also select a Reader or Reader parameters',
                                        ('workflow', 'steps', node, 'in', port), code='unsupported_boundary')
                exchange_inputs.append(key)
                contracts[key] = _exchange_schema(source_port)
            sources[key] = {'id': key, 'kind': 'source', 'source': source, 'position': {'x': 0, 'y': 0}}
            binding = step.bindings[port]
            edges.append({'id': binding.id or f'{key}-{node}-{port}', 'source': key, 'target': node,
                          'sourceHandle': 'out', 'targetHandle': author._handle(declaration, index),
                          **({'adaptation': author._plain(binding.adaptation)} if binding.adaptation is not None else {})})
        graph = author._validate(Graph, {'name': document.workflow.name, 'base_dir': str(directory),
            'nodes': [*sources.values(), actual], 'edges': edges, 'params': globals_,
            'memory': author._plain(document.workflow.memory), 'plugin_lock': author._plain(document.workflow.plugin_lock),
            'runtime': {**author._plain(document.workflow.runtime), 'exchange_inputs': list(dict.fromkeys(exchange_inputs)),
                        'exchange_contracts': contracts}}, ('workflow', 'steps', node))
        if not replay and catalog is not None:
            graph = freeze_graph(graph, mapping, directory)
        if node in ui['routes']:
            author._restore_ui(graph, {'positions': {}, 'routes': {node: ui['routes'][node]}})
        author._reject_engine_values(graph)
        topology, frozen = split_graph(graph)
        native_node = next(item for item in graph.nodes if item.id == node)
        entry = frozen['nodes'][node]
        values['steps'][node] = {key: entry[key] for key in ('params', 'context_params', 'route') if key in entry}
        for source in graph.nodes:
            if source.kind == 'source' and source.id in document.workflow.take:
                values['sources'][source.id] = {'args': author._plain(source.source.args)}
        if native_node.route:
            ui['routes'][node] = author._extract_ui(deepcopy(native_node.route.graph.model_dump(mode='json')))
        native_specs[node] = WorkflowSpec.from_graph(graph)
        native_bindings[node] = bindings
    return NormalizedMixedWorkflow(author._validate(author.AuthoringDocument, canonical_document),
        _freeze(values), _freeze(resolved_inputs), foreign.environments, profile, str(directory), _freeze(ui),
        _freeze(native_specs), _freeze(native_bindings), foreign, _freeze(foreign_boundaries))


def _arguments(process, parameters, outputs, name):
    author = _helpers()
    if process.runner != 'command':
        result = []
        for port in process.input:
            result.extend(['--in-' + port, {'input': port}])
        for port in process.output:
            result.extend(['--out-' + port, {'output': port}])
        return result
    arguments = []
    for index, token in enumerate(process.command.argv):
        path = ('processes', name, 'command', 'argv', index)
        if isinstance(token, author.LiteralToken):
            if '\0' in token.literal:
                raise author._error('NUL is not permitted in argv', path, code='invalid_argument')
            arguments.append(token.literal)
            continue
        raw = token.model_dump(mode='json')
        kind, key = next(iter(raw.items()))
        options = {'input': process.input, 'output': outputs, 'param': parameters,
                   'resource': {'memory_bytes': None, 'threads': None}}
        if kind not in options or key not in options[kind]:
            raise author._error('Unknown typed command argument', path, code='unknown_reference')
        if kind == 'param' and (parameters[key] is None or isinstance(parameters[key], (dict, list, tuple))):
            raise author._error('Compound/null parameters use OPERON_PARAMETERS_FILE, not argv', path, code='invalid_argument')
        arguments.append({'parameter' if kind == 'param' else kind: key})
    return arguments


def lower_foreign(value, *, compiler_version='operon-planning/1', require_files=False):
    author = _helpers()
    document, selected = value.document, value.profile
    if selected.executor is None:
        raise author._error('Foreign execution requires an explicit executor', ('workflow', 'defaults', 'executor'),
                            code='invalid_placement')
    if selected.storage:
        raise author._error('Storage defaults require shared storage binding support',
                            ('workflow', 'defaults', 'storage'), code='unsupported_boundary')
    if require_files:
        for name, path in value.inputs.items():
            if not Path(path).is_file():
                raise author._error('Workflow input file is missing', ('inputs', name), code='input_missing')
    units, edges, requirements, environment_refs = [], [], {}, {}
    for node, step in document.workflow.steps.items():
        process = document.processes[step.process]
        declaration = author._validate(EnvironmentDeclaration, value.environments[process.environment],
                                       ('environments', process.environment))
        requirement = declaration.requirement
        requirement_digest = sha256_hex(requirement)
        requirements[requirement_digest] = requirement
        environment_refs[process.environment] = requirement_digest
        if selected.target:
            requested = author._validate(TargetSpec, selected.target, ('profile', 'target'))
            if requested != requirement.target:
                raise author._error('Selected target differs from the locked process environment',
                                    ('processes', step.process, 'environment'), code='unsupported_target')
        resources = {**selected.resources.model_dump(exclude_none=True), **process.resources.model_dump(exclude_none=True)}
        if not resources.get('memory') or not resources.get('cpus'):
            raise author._error('Foreign execution requires full-process memory and CPU declarations',
                                ('processes', step.process, 'resources'), code='invalid_resource')
        if resources.get('time') is not None:
            raise author._error('Execution time limits require supervisor enforcement',
                                ('processes', step.process, 'resources', 'time'), code='unsupported_boundary')
        params = author._plain(value.parameters['steps'][node])
        outputs = _output_contracts(process, step.process)
        arguments = _arguments(process, params, outputs, step.process)
        payload = {'parameters': params, 'executable': declaration.executable, 'arguments': arguments, 'outputs': outputs}
        payload['input_contracts'] = {name: {'representation': 'form' if _is_form_port(port) else 'file',
                                            'format': port.format} for name, port in process.input.items()}
        if process.runner != 'command':
            snapshot = _script(process, step.process)
            digest = hashlib.sha256(snapshot['code'].encode('utf-8')).hexdigest()
            reference = PurePosixPath('scripts', digest[:16], snapshot['filename']).as_posix()
            code_ref = CodeRef(kind='script', ref=reference, digest=digest)
            payload['script_resource'] = {'path': reference, 'sha256': digest, 'content': snapshot['code']}
        else:
            # The executable is part of the exact locked environment closure.
            code_ref = CodeRef(kind='file', ref=declaration.executable)
        bindings = {}
        for port, binding in step.bindings.items():
            ref = binding.ref if binding.ref is not None else 'workflow.' + binding.input
            producer, output, _ = _port_reference(ref, document, ('workflow', 'steps', node, 'in', port))
            if output is None:
                bindings[port] = 'input:' + producer
            else:
                bindings[port] = 'artifact:' + producer + '/' + output
                edges.append({'id': binding.id or f'{producer}-{output}-{node}-{port}',
                              'source': producer, 'target': node,
                              'source_handle': output, 'target_handle': port})
        units.append(UnitSpec(unit_id=node, node_ids=(node,),
            invocation=InvocationSpec(kind=process.runner, argv=(declaration.executable,), code_ref=code_ref,
                parameters_ref=ParametersRef(kind='frozen-json', ref='unit.payload.parameters', digest=sha256_hex(params)),
                environment_ref=process.environment, event_protocol='none'),
            input_bindings=bindings,
            output_contracts=tuple(OutputContract(name=name, representation=contract['representation'],
                                                  metadata=contract['metadata']) for name, contract in outputs.items()),
            resource_request=ResourceRequestSpec(managed_budget_bytes=0, process_reservation_bytes=resources['memory'],
                                                cpu_threads=resources['cpus']),
            placement=PlacementPolicy(executor=selected.executor, target=requirement.target), payload=payload))
    emitted = {}
    for name, ref in document.workflow.emit.items():
        node, port, _ = _port_reference(ref.ref, document, ('workflow', 'emit', name))
        emitted[name] = 'artifact:' + node + '/' + port
    canonical = export_foreign_mapping(value)['workflow.yaml']
    plan = RunPlan(plan_id='pending', workflow_revision=domain_digest('operon:workflow-authoring:v2', canonical),
        units=tuple(units), edges=tuple(edges), parameters_digest=sha256_hex(value.parameters),
        environment_requirements=tuple(requirements.values()),
        execution_policy={'admission': 'host-pool', 'environment_refs': environment_refs,
                          'workflow_outputs': emitted, 'input_files': author._plain(value.inputs),
                          'input_contracts': {name: {'representation': 'form' if _is_form_port(port) else 'file',
                                                      'format': port.format} for name, port in document.workflow.take.items()}},
        compiler_version=compiler_version, diagnostics={'compiler': 'shared-invocation-lowering'}).with_identity()
    from operon.execution.unit_executor import unit_dependencies
    from .validation import validate_run_plan
    validate_run_plan(plan)
    unit_dependencies(plan)
    return plan


def lower_mixed(value, compiler, catalog, *, root=None, require_files=False):
    """Compile native subgraphs, then join existing invocation records only."""
    author = _helpers()
    from .graph_models import Graph
    from .graph_contracts import analyze_graph
    from .resolver import as_catalog
    from .route_expansion import output_names, port_index
    from .validation import validate_run_plan
    from operon.execution.unit_executor import unit_dependencies

    if require_files:
        for name, path in value.inputs.items():
            if not Path(path).is_file():
                raise author._error('Workflow input file is missing', ('inputs', name), code='input_missing')
    foreign_plan = lower_foreign(value.foreign, compiler_version=compiler.compiler_version)
    units = {}
    for unit in foreign_plan.units:
        bindings = {}
        for port, reference in unit.input_bindings.items():
            key = reference.removeprefix('input:')
            if reference.startswith('input:') and key in value.foreign_boundaries:
                parent, output = value.foreign_boundaries[key]
                reference = 'artifact:' + parent + '/' + output
            bindings[port] = reference
        units[unit.unit_id] = unit.model_copy(update={'input_bindings': bindings})
    requirements = {sha256_hex(item): item for item in foreign_plan.environment_requirements}
    environment_refs = author._plain(foreign_plan.execution_policy['environment_refs'])
    implementations, descriptor_audit = {}, {}
    snapshot = as_catalog(catalog)
    mapping = {'operators': list(snapshot.operators), 'readers': list(snapshot.readers)}
    registry = {item['id']: item for item in snapshot.operators}
    for node, spec in value.native_specs.items():
        step = value.document.workflow.steps[node]
        process = value.document.processes[step.process]
        declaration = author._validate(EnvironmentDeclaration, value.environments[process.environment],
                                       ('environments', process.environment))
        requirement = declaration.requirement
        if not requirement.runtime.startswith('cpython-'):
            raise author._error('Native execution requires a locked CPython environment',
                                ('processes', step.process, 'environment'), code='unsupported_target')
        if value.profile.target and author._validate(TargetSpec, value.profile.target, ('profile', 'target')) != requirement.target:
            raise author._error('Selected target differs from the native environment',
                                ('processes', step.process, 'environment'), code='unsupported_target')
        resources = {**value.profile.resources.model_dump(exclude_none=True), **process.resources.model_dump(exclude_none=True)}
        if not resources.get('memory') or not resources.get('cpus'):
            raise author._error('Mixed native units require a full-process memory and CPU reservation',
                                ('processes', step.process, 'resources'), code='invalid_resource')
        if resources.get('time') is not None:
            raise author._error('Execution time limits require supervisor enforcement',
                                ('processes', step.process, 'resources', 'time'), code='unsupported_boundary')
        graph = Graph.model_validate(spec.to_legacy_dict())
        memory = graph.memory
        reservation_mb = resources['memory'] / 1024**2
        for field in ('budget_mb', 'process_limit_mb'):
            limit = memory.get(field)
            if limit is not None and (isinstance(limit, bool) or not isinstance(limit, (int, float))
                                      or limit < 0 or limit > reservation_mb):
                raise author._error('Native memory plan exceeds the declared full-process reservation',
                                    ('workflow', 'memory', field), code='invalid_resource')
        memory.setdefault('budget_mb', reservation_mb if memory.get('enabled', True) else 0)
        memory.setdefault('process_limit_mb', reservation_mb)
        actual = next(item for item in graph.nodes if item.id == node)
        names = output_names(actual, registry)
        analysis = analyze_graph(graph, mapping, Path(value.directory))
        aliases = {}
        contracts = []
        for index, (port, descriptor) in enumerate(process.output.items()):
            at = ('processes', step.process, 'output', port)
            if not _is_form_port(descriptor):
                raise author._error('Published mixed native outputs require explicit type form and format bpform',
                                    at, code='unsupported_boundary')
            offset = port_index(author._handle(descriptor, index, output=True, total=len(process.output)))
            if offset >= len(names):
                raise author._error('Declared output does not exist on the native implementation', at, code='unknown_reference')
            schema = analysis['nodes'][node]['outputs'][offset]
            format_ = schema.get('data_format') or {}
            if (schema.get('kind') == 'file'
                    or (format_.get('logical_type') is not None and format_['logical_type'] != 'form')
                    or not (schema.get('kind') == 'form' or format_.get('logical_type') == 'form')):
                raise author._error('Native output metadata does not prove a Form materialization; declare an explicit compatible implementation',
                                    at, code='unsupported_boundary')
            aliases[port] = names[offset]
            contracts.append(OutputContract(name=port, representation='form',
                                           metadata={'format': 'bpform', 'contract': author._plain(descriptor.contract)}))
        if not aliases:
            raise author._error('Mixed native units require a publishable Form output',
                                ('processes', step.process, 'output'), code='unsupported_boundary')
        graph.runtime['exchange_outputs'] = list(dict.fromkeys(aliases.values()))
        # Exchange placeholders do not exist until their parent publishes. All
        # actual external files were checked above; native checks still validate
        # schemas, converters, route expansion and memory without opening data.
        subplan = compiler.compile(WorkflowSpec.from_graph(graph), None, snapshot,
                                   root=root or value.directory, require_files=False, freeze_defaults=False)
        if len(subplan.units) != 1:
            raise author._error('Native graph compiler returned an unsupported unit partition',
                                ('workflow', 'steps', node), code='compiler_adapter_error')
        unit = subplan.units[0]
        payload = author._plain(unit.payload)
        # Input locations are resolved by the shared invocation binder. Never
        # retain our nonexistent exchange placeholder paths in an executable
        # payload or in its identity, including after moving an author project.
        for source, reference in value.native_bindings[node].items():
            payload['task_manifest']['sources'][source]['path'] = reference
            for source_node in payload['graph']['nodes']:
                if source_node['id'] == source and source_node.get('source'):
                    source_node['source']['path'] = reference
        payload['graph']['base_dir'] = '.'
        author._extract_ui(payload['graph'])
        runtime = payload['task_manifest']['runtime']
        expanded = runtime.get('exchange_aliases', {})
        runtime['exchange_aliases'] = {port: expanded.get(actual_name, actual_name) for port, actual_name in aliases.items()}
        payload['executable'] = declaration.executable
        digest = sha256_hex(requirement)
        payload['native_environment_requirement_digest'] = digest
        environment_refs[process.environment] = digest
        requirements[digest] = requirement
        requested = unit.resource_request.model_copy(update={'process_reservation_bytes': resources['memory'],
            'managed_budget_bytes': unit.resource_request.managed_budget_bytes if memory.get('enabled', True) else 0,
            'cpu_threads': resources['cpus']})
        units[node] = unit.model_copy(update={'unit_id': node,
            'invocation': unit.invocation.model_copy(update={'environment_ref': process.environment}),
            'input_bindings': author._plain(value.native_bindings[node]), 'output_contracts': tuple(contracts),
            'resource_request': requested,
            'placement': PlacementPolicy(executor=value.profile.executor, target=requirement.target), 'payload': payload})
        for identifier, implementation in subplan.implementations.items():
            if identifier in implementations and implementations[identifier] != implementation:
                raise author._error('Native subgraphs disagree about an implementation identity',
                                    ('implementations', identifier), code='implementation_conflict')
            implementations[identifier] = author._plain(implementation)
        descriptor_audit.update(author._plain(subplan.diagnostics.get('native_descriptor_audit', {})))

    # Original authoring edges describe the cross-unit dependency graph. Native
    # route internals remain solely in their compiler-produced task payload.
    edges = []
    for node, step in value.document.workflow.steps.items():
        for port, binding in step.bindings.items():
            ref = binding.ref if binding.ref is not None else 'workflow.' + binding.input
            producer, output, _ = _port_reference(ref, value.document, ('workflow', 'steps', node, 'in', port))
            if output is not None:
                edges.append({'id': binding.id or f'{producer}-{output}-{node}-{port}',
                    'source': units[producer].node_ids[0], 'target': units[node].node_ids[0],
                    'source_handle': output, 'target_handle': port})
    emitted = {}
    for name, ref in value.document.workflow.emit.items():
        producer, port, _ = _port_reference(ref.ref, value.document, ('workflow', 'emit', name))
        if port is None:
            raise author._error('Mixed emitted results require a producing invocation',
                                ('workflow', 'emit', name), code='unsupported_boundary')
        emitted[name] = 'artifact:' + producer + '/' + port
    plan = RunPlan(plan_id='pending',
        workflow_revision=domain_digest('operon:workflow-authoring:v2', export_foreign_mapping(value)['workflow.yaml']),
        units=tuple(units[node] for node in value.document.workflow.steps), edges=tuple(edges),
        parameters_digest=sha256_hex(value.parameters), implementations=implementations,
        environment_requirements=tuple(requirements.values()),
        execution_policy={'admission': 'host-pool', 'environment_refs': environment_refs,
                          'workflow_outputs': emitted, 'input_files': author._plain(value.inputs),
                          'input_contracts': {name: {'representation': 'form' if _is_form_port(port) else 'file',
                                                      'format': port.format} for name, port in value.document.workflow.take.items()}},
        compiler_version=compiler.compiler_version,
        diagnostics={'compiler': 'shared-graph-and-invocation-lowering',
                     'native_descriptor_audit': descriptor_audit}).with_identity()
    validate_run_plan(plan)
    unit_dependencies(plan)
    return plan


def lower_native_authoring(value, compiler, catalog, *, root=None, require_files=False):
    """Bind one fused native graph to one explicitly declared exact environment."""
    author = _helpers()
    selected = value.profile
    if selected.storage or selected.resources.time is not None:
        raise author._error('Native storage/time policies require explicit runtime enforcement',
                            ('workflow', 'defaults'), code='unsupported_boundary')
    declarations, resource_sets = {}, []
    for node, step in value.document.workflow.steps.items():
        process = value.document.processes[step.process]
        if not process.environment or process.environment not in value.environments:
            raise author._error('Every process in a native environment group must declare its exact environment',
                                ('processes', step.process, 'environment'), code='unsupported_boundary')
        declaration = author._validate(EnvironmentDeclaration, value.environments[process.environment],
                                       ('environments', process.environment))
        if not declaration.requirement.runtime.startswith('cpython-'):
            raise author._error('Native execution requires a locked CPython environment',
                                ('processes', step.process, 'environment'), code='unsupported_target')
        declarations[process.environment] = declaration
        resources = {**selected.resources.model_dump(exclude_none=True), **process.resources.model_dump(exclude_none=True)}
        if resources.get('time') is not None:
            raise author._error('Native time limits require supervisor enforcement',
                                ('processes', step.process, 'resources', 'time'), code='unsupported_boundary')
        resource_sets.append(resources)
    identities = {(sha256_hex(item.requirement), item.executable) for item in declarations.values()}
    if len(identities) != 1 or any(item != resource_sets[0] for item in resource_sets[1:]):
        raise author._error('A fused native graph requires one exact environment and resource policy; split at explicit materialized boundaries',
                            ('processes',), code='unsupported_boundary')
    name, declaration = next(iter(declarations.items()))
    if selected.target and author._validate(TargetSpec, selected.target, ('workflow', 'defaults', 'target')) != declaration.requirement.target:
        raise author._error('Selected target differs from the locked native environment',
                            ('workflow', 'defaults', 'target'), code='unsupported_target')
    resources = resource_sets[0]
    graph = value.spec.to_legacy_dict()
    memory = graph['memory']
    memory_bytes = resources.get('memory')
    if memory_bytes is None:
        mb = memory.get('process_limit_mb', memory.get('budget_mb'))
        if isinstance(mb, bool) or not isinstance(mb, (float, int)) or mb <= 0:
            raise author._error('Native environment binding requires a declared full-process memory reservation',
                                ('workflow', 'defaults', 'resources', 'memory'), code='invalid_resource')
        memory_bytes = int(mb * 1024**2)
    for field in ('budget_mb', 'process_limit_mb'):
        limit = memory.get(field)
        if limit is not None and (isinstance(limit, bool) or not isinstance(limit, (float, int))
                                  or limit < 0 or limit * 1024**2 > memory_bytes):
            raise author._error('Native memory plan exceeds full-process reservation',
                                ('workflow', 'memory', field), code='invalid_resource')
    if memory.get('enabled', True):
        memory.setdefault('budget_mb', memory_bytes / 1024**2)
    memory.setdefault('process_limit_mb', memory_bytes / 1024**2)
    plan = compiler.compile(WorkflowSpec.from_graph(graph), None, catalog,
                            root=root or value.spec.base_dir, require_files=require_files, freeze_defaults=False)
    if len(plan.units) != 1:
        raise author._error('Native graph is not one environment group', code='unsupported_boundary')
    unit = plan.units[0]
    digest = sha256_hex(declaration.requirement)
    payload = author._plain(unit.payload)
    payload.update(executable=declaration.executable, native_environment_requirement_digest=digest)
    from operon.execution.native_bootstrap import validate_native_descriptors
    validate_native_descriptors(payload['native_descriptors'], plan.implementations, payload['task_manifest'],
                                 environment_requirement_digest=digest)
    unit = unit.model_copy(update={'payload': payload,
        'invocation': unit.invocation.model_copy(update={'environment_ref': name}),
        'placement': PlacementPolicy(executor=selected.executor or 'local', target=declaration.requirement.target),
        'resource_request': unit.resource_request.model_copy(update={'process_reservation_bytes': memory_bytes,
            'managed_budget_bytes': unit.resource_request.managed_budget_bytes if memory.get('enabled', True) else 0,
            'cpu_threads': resources.get('cpus', 1)})})
    policy = author._plain(plan.execution_policy)
    policy.update(target=declaration.requirement.target.model_dump(mode='json'),
                  environment_refs={reference: digest for reference in declarations})
    return plan.model_copy(update={'units': (unit,), 'environment_requirements': (declaration.requirement,),
                                  'execution_policy': policy}).with_identity()
