"""Versioned workflow and frozen-parameter models.

``WorkflowSpec`` is the planning-side, metadata-only workflow record.  It can be
created from the existing canvas ``Graph`` shape through ``from_graph`` without
importing the web layer, and it can be projected back to that shape at the
application compatibility boundary.
"""
from __future__ import annotations

from copy import deepcopy
import json
import re
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator, model_serializer
from .storage import StorageInputRef, storage_input_path

from .base import ContractError, ContractModel, sha256_hex


_ID = re.compile(r'^[A-Za-z_][A-Za-z0-9_.-]{0,79}$')
_ROUTE_ID = re.compile(r'^route_[a-f0-9]{12}$')
_OUTPUT_HANDLE = re.compile(r'^out(?:-\d+)?$')


class SourceSpec(ContractModel):
    reader: str | None = Field(default=None, pattern=r'^[A-Za-z_][A-Za-z0-9_.-]{0,79}$')
    path: str = Field(default='', max_length=2048)
    dims: tuple[str, ...] = ('sample', 'feature')
    labels: dict[str, Any] = Field(default_factory=dict)
    args: dict[str, Any] = Field(default_factory=dict)
    location: dict[str, Any] | None = None
    storage_ref: StorageInputRef | None = None

    @model_validator(mode='after')
    def _storage_identity(self):
        if self.storage_ref is not None and (self.path != storage_input_path(self.storage_ref) or self.location is not None):
            raise ValueError('Storage inputs use their reference URI and configured mount location')
        return self

    @model_serializer(mode='wrap')
    def _legacy_shape(self, handler):
        value = handler(self)
        if self.storage_ref is None:
            value.pop('storage_ref', None)
        return value

    @field_validator('dims')
    @classmethod
    def _dims(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value or len(value) > 8 or any(not isinstance(item, str) or not item for item in value):
            raise ValueError('dims must contain one to eight nonempty names')
        return value


class WorkflowEdge(ContractModel):
    id: str = Field(min_length=1, max_length=200)
    source: str = Field(min_length=1, max_length=80)
    target: str = Field(min_length=1, max_length=80)
    source_handle: str = Field(default='out', max_length=100)
    target_handle: str = Field(default='in-0', pattern=r'^in-\d+$')
    adaptation: dict[str, Any] | None = None


class WorkflowNode(ContractModel):
    id: str = Field(min_length=1, max_length=80)
    kind: Literal['source', 'operator', 'route', 'script']
    operator: str | None = Field(default=None, pattern=r'^[A-Za-z_][A-Za-z0-9_.-]{0,79}$')
    source: SourceSpec | None = None
    route: 'RouteSpec | None' = None
    script: dict[str, Any] | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    context_params: dict[str, Any] = Field(default_factory=dict)
    input_count: int = Field(default=1, ge=0, le=20)
    title: str = Field(default='', max_length=120)
    position: dict[str, float] | None = None

    @model_validator(mode='after')
    def _kind_payload(self):
        if self.kind == 'source' and self.source is None:
            raise ValueError('A source node requires source metadata')
        if self.kind == 'source' and self.operator is not None:
            raise ValueError('A source node cannot have an operator')
        if self.kind == 'operator' and not self.operator:
            raise ValueError('An operator node requires an operator id')
        if self.kind == 'route' and self.route is None:
            raise ValueError('A route node requires a route snapshot')
        if self.kind == 'script' and not self.script:
            raise ValueError('A script node requires a script snapshot')
        return self


class RouteSpec(ContractModel):
    id: str
    version: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=120)
    graph: 'WorkflowSpec'

    @field_validator('id')
    @classmethod
    def _id(cls, value: str) -> str:
        if not _ROUTE_ID.fullmatch(value):
            raise ValueError('route id must be route_ plus 12 lowercase hex characters')
        return value


class WorkflowSpec(ContractModel):
    format: Literal['operon.workflow'] = 'operon.workflow'
    schema_version: Literal[2] = 2
    name: str = Field(default='workflow', min_length=1, max_length=120)
    base_dir: str = Field(default='.', max_length=2048)
    nodes: tuple[WorkflowNode, ...] = Field(min_length=1, max_length=1000)
    edges: tuple[WorkflowEdge, ...] = Field(default_factory=tuple, max_length=5000)
    params: dict[str, Any] = Field(default_factory=dict)
    runtime: dict[str, Any] = Field(default_factory=dict)
    manifest_extra: dict[str, Any] = Field(default_factory=dict)
    plugin_lock: dict[str, Any] = Field(default_factory=dict)
    interface: dict[str, Any] | None = None

    @model_validator(mode='after')
    def _graph_shape(self):
        ids = [node.id for node in self.nodes]
        if len(set(ids)) != len(ids):
            raise ValueError('Workflow node ids must be unique')
        if not any(node.kind != 'source' for node in self.nodes):
            raise ValueError('A workflow requires at least one processing node')
        edges = [edge.id for edge in self.edges]
        if len(set(edges)) != len(edges):
            raise ValueError('Workflow edge ids must be unique')
        for edge in self.edges:
            if edge.source not in ids or edge.target not in ids:
                raise ValueError(f'Edge {edge.id!r} references an unknown node')
            if not _OUTPUT_HANDLE.fullmatch(edge.source_handle):
                raise ValueError(f'Edge {edge.id!r} has an invalid source handle')
        return self

    # -- compatibility projection ------------------------------------
    @classmethod
    def from_graph(cls, graph: Any) -> 'WorkflowSpec':
        """Normalize the existing canvas Graph (or its dict) to WorkflowSpec."""
        value = graph.model_dump(mode='json') if hasattr(graph, 'model_dump') else deepcopy(graph)
        if not isinstance(value, dict):
            raise ContractError('Workflow graph must be an object', code='invalid_workflow')
        if value.get('format') == 'operon.workflow':
            return cls.model_validate(value)
        if value.get('schema_version') not in (None, 2):
            raise ContractError('Legacy graph schema_version must be 2', code='unsupported_workflow_version',
                                details={'schema_version': value.get('schema_version')})
        nodes, edges = [], []
        for raw in value.get('nodes', []):
            kind = raw.get('kind')
            source = None
            if raw.get('source') is not None:
                raw_source = deepcopy(raw['source'])
                source = SourceSpec.model_validate({
                    'reader': raw_source.get('reader'),
                    'path': raw_source.get('path', ''),
                    'dims': tuple(raw_source.get('dims', ('sample', 'feature'))),
                    'labels': raw_source.get('labels', {}),
                    'args': raw_source.get('args', {}),
                    'location': raw_source.get('location'),
                    'storage_ref': raw_source.get('storage_ref'),
                })
            route = None
            if raw.get('route') is not None:
                raw_route = raw['route']
                route = RouteSpec.model_validate({
                    'id': raw_route.get('id'),
                    'version': raw_route.get('version', 1),
                    'name': raw_route.get('name', 'route'),
                    'graph': cls.from_graph(raw_route.get('graph')).model_dump(mode='json'),
                })
            nodes.append(WorkflowNode.model_validate({
                'id': raw.get('id'), 'kind': kind, 'operator': raw.get('operator'),
                'source': source.model_dump(mode='json') if source else None,
                'route': route.model_dump(mode='json') if route else None,
                'script': deepcopy(raw.get('script')),
                'params': deepcopy(raw.get('params') or {}),
                'context_params': deepcopy(raw.get('context_params') or {}),
                'input_count': raw.get('input_count', 1),
                'title': raw.get('title', ''),
                'position': deepcopy(raw.get('position')),
            }))
        for raw in value.get('edges', []):
            edges.append(WorkflowEdge.model_validate({
                'id': raw.get('id'), 'source': raw.get('source'), 'target': raw.get('target'),
                'source_handle': raw.get('sourceHandle', 'out'),
                'target_handle': raw.get('targetHandle', 'in-0'),
                'adaptation': deepcopy(raw.get('adaptation')),
            }))
        runtime = deepcopy(value.get('runtime') or {})
        if isinstance(value.get('memory'), dict) and value['memory']:
            runtime['memory'] = deepcopy(value['memory'])
        return cls.model_validate({
            'name': value.get('name', 'workflow'), 'base_dir': value.get('base_dir', '.'),
            'nodes': [node.model_dump(mode='json') for node in nodes],
            'edges': [edge.model_dump(mode='json') for edge in edges],
            'params': deepcopy(value.get('params') or {}),
            'runtime': runtime,
            'manifest_extra': deepcopy(value.get('manifest_extra') or {}),
            'plugin_lock': deepcopy(value.get('plugin_lock') or {}),
            'interface': deepcopy(value.get('interface')),
        })

    @classmethod
    def from_yaml_mapping(cls, value: dict[str, Any]) -> 'WorkflowSpec':
        """Accept either the durable graph shape or the new v2 vocabulary.

        This is deliberately a *normalizer*, not a second YAML evaluator.  The
        existing safe YAML loader remains the parser.
        """
        if not isinstance(value, dict):
            raise ContractError('Workflow must be an object', code='invalid_workflow')
        if value.get('format') == 'operon.workflow' and 'nodes' not in value:
            raise ContractError('The new authoring vocabulary requires a normalizer before compilation',
                                code='unsupported_authoring_v2')
        return cls.from_graph(value)

    def to_legacy_dict(self) -> dict[str, Any]:
        """Project to the existing Graph shape for compatibility entry points."""
        nodes = []
        for node in self.nodes:
            route = None
            if node.route is not None:
                route = {'id': node.route.id, 'version': node.route.version,
                         'name': node.route.name,
                         'graph': node.route.graph.to_legacy_dict()}
            value = {
                'id': node.id, 'kind': node.kind, 'operator': node.operator,
                'script': deepcopy(node.script),
                'title': node.title,
                'position': deepcopy(node.position) or {'x': 0, 'y': 0},
                'params': deepcopy(node.params), 'context_params': deepcopy(node.context_params),
                'source': node.source.model_dump(mode='json') if node.source else None,
                'input_count': node.input_count,
                'route': route,
            }
            nodes.append(value)
        edges = []
        for edge in self.edges:
            value = {'id': edge.id, 'source': edge.source, 'target': edge.target,
                     'sourceHandle': edge.source_handle, 'targetHandle': edge.target_handle}
            if edge.adaptation is not None:
                value['adaptation'] = deepcopy(edge.adaptation)
            edges.append(value)
        value = {'schema_version': 2, 'name': self.name, 'base_dir': self.base_dir,
                'nodes': nodes, 'edges': edges, 'memory': deepcopy(self.runtime.get('memory', {'enabled': True})),
                'params': deepcopy(self.params), 'runtime': deepcopy(self.runtime),
                'manifest_extra': deepcopy(self.manifest_extra),
                'plugin_lock': deepcopy(self.plugin_lock),
                'interface': deepcopy(self.interface)}
        # The compatibility API consumes JSON lists, not our immutable tuples.
        return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))

    def apply_values(self, values: Any) -> 'WorkflowSpec':
        """Apply an independent frozen value snapshot without falling back."""
        snapshot = values if isinstance(values, FrozenParameters) else FrozenParameters.from_values(values)
        nodes = []
        consumed = set()
        for node in self.nodes:
            entry = snapshot.sources.get(node.id) if node.kind == 'source' else snapshot.steps.get(node.id)
            if entry is None:
                nodes.append(node)
                continue
            consumed.add(node.id)
            if node.kind == 'source':
                nodes.append(node.model_copy(update={'source': node.source.model_copy(
                    update={'args': deepcopy(entry)}), }))
            else:
                # An independent saved snapshot is authoritative for this
                # node. Merging resurrects values removed from that snapshot
                # (including defaults that now exist only in the graph).
                nodes.append(node.model_copy(update={'params': deepcopy(entry)}))
        unknown = set(snapshot.sources) | set(snapshot.steps)
        unknown -= {node.id for node in self.nodes}
        if unknown:
            raise ContractError('Frozen values reference unknown workflow nodes',
                                code='unknown_parameter_node',
                                details={'nodes': sorted(unknown)})
        return self.model_copy(update={'nodes': tuple(nodes)})

    def values_digest(self) -> str:
        return sha256_hex({'params': self.params,
                           'sources': {node.id: node.source.args for node in self.nodes if node.source},
                           'steps': {node.id: node.params for node in self.nodes if node.kind != 'source'}})


class FrozenParameters(ContractModel):
    """An independent saved-value snapshot.

    Values are keyed by stable node IDs.  A missing key means "not supplied";
    the compiler must not substitute a current library default.  The legacy
    task-parameter shape is accepted only through ``from_values``.
    """

    format: Literal['operon.frozen-parameters'] = 'operon.frozen-parameters'
    schema_version: Literal[1] = 1
    sources: dict[str, dict[str, Any]] = Field(default_factory=dict)
    steps: dict[str, dict[str, Any]] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_values(cls, values: Any) -> 'FrozenParameters':
        if isinstance(values, FrozenParameters):
            return values
        if not isinstance(values, dict):
            raise ContractError('Frozen parameter values must be an object',
                                code='invalid_parameters')
        fmt = values.get('format')
        if fmt == 'operon.frozen-parameters' or fmt == 'operon.workflow-parameters':
            sources = values.get('sources') or {}
            steps = values.get('steps') or {}
            normalized = {}
            for key, value in steps.items():
                if not isinstance(value, dict):
                    raise ContractError('Step parameter entries must be objects', code='invalid_parameters')
                normalized[key] = deepcopy(value.get('params', value))
            source_values = {}
            for key, value in sources.items():
                if not isinstance(value, dict):
                    raise ContractError('Source parameter entries must be objects', code='invalid_parameters')
                source_values[key] = deepcopy(value.get('args', value))
            return cls.model_validate({'sources': source_values, 'steps': normalized,
                                       'params': deepcopy(values.get('params') or {})})
        if fmt == 'operon.task-parameters':
            sources = values.get('sources') or {}
            steps = values.get('steps') or []
            return cls.model_validate({
                'sources': {key: deepcopy(value) for key, value in sources.items()},
                'steps': {entry['name']: deepcopy(entry.get('params') or {}) for entry in steps},
                'params': deepcopy(values.get('params') or {})})
        # A plain mapping is accepted only for node-id keyed values, never as a
        # silently merged list of library defaults.
        if all(isinstance(value, dict) for value in values.values()):
            return cls.model_validate({'steps': deepcopy(values)})
        raise ContractError('Unsupported frozen parameter format', code='invalid_parameters',
                            details={'format': fmt})


WorkflowNode.model_rebuild()
RouteSpec.model_rebuild()
WorkflowSpec.model_rebuild()
