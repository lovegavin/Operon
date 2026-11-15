"""Metadata-only catalog and parameter resolution.

No module in this file imports an operator implementation.  A catalog snapshot
is a plain descriptor mapping supplied by the application/library layer.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from operon.contracts.base import ContractError
from operon.contracts.workflow import FrozenParameters, WorkflowSpec


@dataclass(frozen=True)
class CatalogSnapshot:
    operators: tuple[dict[str, Any], ...]
    readers: tuple[dict[str, Any], ...]
    generation: str = ''

    @classmethod
    def from_mapping(cls, catalog: Mapping[str, Any] | None) -> 'CatalogSnapshot':
        catalog = catalog or {}
        return cls(operators=tuple(deepcopy(catalog.get('operators') or ())),
                   readers=tuple(deepcopy(catalog.get('readers') or ())),
                   generation=str(catalog.get('generation') or ''))

    def operator(self, operator_id: str) -> dict[str, Any] | None:
        return next((item for item in self.operators if item.get('id') == operator_id), None)

    def reader(self, reader_id: str) -> dict[str, Any] | None:
        return next((item for item in self.readers if item.get('id') == reader_id), None)

    def descriptor(self, kind: str, identifier: str) -> dict[str, Any] | None:
        return self.operator(identifier) if kind == 'operator' else self.reader(identifier)


def as_catalog(value: Mapping[str, Any] | CatalogSnapshot | None) -> CatalogSnapshot:
    return value if isinstance(value, CatalogSnapshot) else CatalogSnapshot.from_mapping(value)


def resolve_workflow(spec: WorkflowSpec | Mapping[str, Any], values: FrozenParameters | Mapping[str, Any] | None,
                     catalog: Mapping[str, Any] | CatalogSnapshot | None) -> tuple[WorkflowSpec, FrozenParameters, CatalogSnapshot]:
    """Return the frozen workflow, values and metadata snapshot.

    Missing values are not replaced by a current schema default here.  The
    compatibility adapter that uses the existing compiler performs the existing
    declared-default freeze explicitly; the new planning path keeps the
    supplied snapshot untouched.
    """
    from .limits import check_graph_size
    check_graph_size(spec)
    if not isinstance(spec, WorkflowSpec):
        spec = WorkflowSpec.from_graph(spec)
    snapshot = values if isinstance(values, FrozenParameters) else FrozenParameters.from_values(values or {})
    catalog_snapshot = as_catalog(catalog)
    unknown = (set(snapshot.sources) | set(snapshot.steps)) - {node.id for node in spec.nodes}
    if unknown:
        raise ContractError('Frozen values reference unknown nodes',
                            code='unknown_parameter_node', details={'nodes': sorted(unknown)})
    return spec.apply_values(snapshot), snapshot, catalog_snapshot


def selected_descriptors(spec: WorkflowSpec, catalog: CatalogSnapshot) -> tuple[dict[str, Any], ...]:
    result = []
    seen = set()
    for node in spec.nodes:
        if node.kind == 'route' and node.route is not None:
            for nested in selected_descriptors(node.route.graph, catalog):
                key = (nested.get('kind'), nested.get('id'))
                if key not in seen:
                    seen.add(key)
                    result.append(nested)
            continue
        if node.kind == 'operator':
            descriptor = catalog.operator(node.operator)
            if descriptor is None:
                raise ContractError(f'Operator {node.operator!r} is missing from the catalog snapshot',
                                    code='unknown_operator', details={'node': node.id})
            key = ('operator', node.operator)
        elif node.kind == 'source' and node.source and node.source.reader:
            descriptor = catalog.reader(node.source.reader)
            if descriptor is None:
                raise ContractError(f'Reader {node.source.reader!r} is missing from the catalog snapshot',
                                    code='unknown_reader', details={'node': node.id})
            key = ('reader', node.source.reader)
        else:
            continue
        if key not in seen:
            seen.add(key)
            result.append(descriptor)
    return tuple(result)
