"""Validation helpers for the public planning records.

These helpers only inspect metadata.  They do not import an operator, read input
scientific data or install a dependency.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from operon.contracts.base import ContractError
from operon.contracts.run_plan import RunPlan
from operon.contracts.workflow import WorkflowSpec
from .resolver import as_catalog, resolve_workflow, selected_descriptors


def unsupported_boundary(node_id: str, kind: str, reason: str) -> ContractError:
    return ContractError(reason, code='unsupported_boundary',
                         details={'node': node_id, 'kind': kind},
                         next_actions=[{'action': 'choose_adapter',
                                        'message': 'Use a supported invocation adapter or remove the node'}])


def validate_workflow(spec: WorkflowSpec | Mapping[str, Any],
                      values: Any = None,
                      catalog: Mapping[str, Any] | Any = None,
                      *, root=None) -> WorkflowSpec:
    """Return the frozen workflow or raise a concrete contract error."""
    workflow, _, snapshot = resolve_workflow(spec, values, catalog)
    # Metadata-only descriptor closure.  This catches unknown operators/Readers
    # before a compiler ever asks an execution backend for capacity.
    describe = selected_descriptors(workflow, snapshot)
    if not describe:
        raise ContractError('Workflow has no resolvable processing implementation',
                            code='unsupported_boundary')
    node_ids = {node.id for node in workflow.nodes}
    for edge in workflow.edges:
        if edge.source not in node_ids or edge.target not in node_ids:
            raise ContractError(f'Edge {edge.id!r} references an unknown node',
                                code='invalid_edge')
    # Route/script nodes are valid WorkflowSpec members.  The compiler decides
    # whether the selected adapter supports them; validation must not silently
    # drop or pre-reject a boundary.
    return workflow


def validate_run_plan(plan: RunPlan) -> RunPlan:
    if plan.compute_id() != plan.plan_id:
        raise ContractError('RunPlan identity does not match its canonical content',
                            code='stale_plan_identity')
    node_ids = set()
    for unit in plan.units:
        node_ids.update(unit.node_ids)
        node_ids.update(unit.input_bindings)
        node_ids.update(node['id'] for node in unit.payload.get('graph', {}).get('nodes', ()))
    seen = set()
    for edge in plan.edges:
        source, target = edge.get('source'), edge.get('target')
        if source not in node_ids or target not in node_ids:
            raise ContractError('RunPlan edge references a node outside its units',
                                code='invalid_plan_edge')
        key = (source, target, edge.get('source_handle'), edge.get('target_handle'))
        if key in seen:
            raise ContractError('RunPlan contains a duplicate edge', code='invalid_plan_edge')
        seen.add(key)
    return plan
