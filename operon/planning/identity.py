"""Deterministic workflow, parameter and plan identities."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from operon.contracts.base import canonical_json, domain_digest, sha256_hex
from operon.contracts.workflow import FrozenParameters, WorkflowSpec


def _normalized_source_path(value: str) -> str:
    """Keep local input roots out of code identity.

    Absolute input roots are machine bindings, not workflow code.  Local paths
    are represented by their basename; remote namespace paths remain intact so
    a remote intent cannot silently collide with a local file.
    """
    if not isinstance(value, str):
        return ''
    path = Path(value)
    return path.name if path.is_absolute() else value.replace('\\', '/')


def _strip_presentation(value: dict[str, Any]) -> dict[str, Any]:
    value.pop('base_dir', None)
    value.pop('interface', None)
    for node in value.get('nodes', []):
        node.pop('position', None)
        node.pop('title', None)
        if node.get('source'):
            node['source']['path'] = _normalized_source_path(node['source'].get('path', ''))
        route = node.get('route')
        if isinstance(route, dict) and isinstance(route.get('graph'), dict):
            route['graph'] = _strip_presentation(route['graph'])
            route['graph'].pop('format', None)
            route['graph'].pop('schema_version', None)
    return value


def workflow_identity_payload(spec: WorkflowSpec) -> dict[str, Any]:
    return _strip_presentation(spec.model_dump(mode='json'))


def workflow_revision(spec: WorkflowSpec) -> str:
    return domain_digest('operon:workflow-revision:v1', workflow_identity_payload(spec))


def frozen_parameters_payload(values: FrozenParameters) -> dict[str, Any]:
    # Keep the independent values exactly, including explicit nulls/empty
    # collections; no schema defaults and no live operator state are consulted.
    return values.model_dump(mode='json')


def parameters_digest(values: FrozenParameters) -> str:
    return domain_digest('operon:frozen-parameters:v1', frozen_parameters_payload(values))


def implementation_digest(descriptor: dict[str, Any]) -> str:
    from operon.pins import identity
    implementation = descriptor.get('implementation') or {}
    return sha256_hex({'id': descriptor.get('id'), 'kind': descriptor.get('kind'),
                       'implementation': dict(identity(implementation, bundled=descriptor.get('origin') == 'bundled')),
                       'resource_digest': implementation.get('resource_digest'),
                       'sdk_abi': implementation.get('sdk_abi')})


def environment_requirement_digest(requirement: Any) -> str:
    value = requirement.model_dump(mode='json') if hasattr(requirement, 'model_dump') else requirement
    return domain_digest('operon:environment-requirement:v1', value)


def plan_identity(plan: Any) -> str:
    from operon.contracts.run_plan import RunPlan
    record = plan if isinstance(plan, RunPlan) else RunPlan.model_validate(plan)
    return record.compute_id()
