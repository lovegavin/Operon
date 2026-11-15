"""Lift machine-local locations into explicit bindings without weakening identity."""
from copy import deepcopy
from pathlib import Path

from operon.contracts.base import ContractError
from operon.contracts.run_plan import RunPlan
from operon.execution.unit_executor import unit_dependencies
from operon.planning.validation import validate_run_plan


def bindable_plan(plan):
    plan = RunPlan.model_validate(plan)
    validate_run_plan(plan)
    unit_dependencies(plan)
    value, inputs = plan.model_dump(mode='json'), {}
    inputs.update(value['execution_policy'].pop('input_files', {}))
    for unit in value['units']:
        if unit['placement']['executor'] not in ('local', 'standalone'):
            raise ContractError('Remote-only routes require a cluster deployment export', code='unsupported_target')
        unit['placement']['executor'] = 'standalone'
        payload = unit['payload']
        if unit['invocation']['kind'] == 'native':
            graph = payload.pop('graph', None)
            # Graph is redundant UI/import metadata. Its executed content is in
            # task_manifest, frozen parameters and implementation/resource locks.
            for name, source in payload['task_manifest'].get('sources', {}).items():
                prior = unit['input_bindings'].get(name, '')
                if prior.startswith(('artifact:', 'input:')):
                    source['path'] = prior
                    continue
                original = source['path']
                key = unit['unit_id'] + '-' + name
                if key in inputs and inputs[key] != original:
                    raise ContractError('Conflicting portable source binding', code='missing_binding')
                inputs[key] = original
                source['path'] = 'storage://' + key + '/' + Path(original).name
                unit['input_bindings'][name] = source['path']
            # Source names are canonical; no local path can remain unbound in the
            # native task. Workflow/path parameters need explicit manifests.
            def reject_absolute(node, trail):
                if isinstance(node, dict):
                    for key, item in node.items(): reject_absolute(item, trail + [str(key)])
                elif isinstance(node, (list, tuple)):
                    for index, item in enumerate(node): reject_absolute(item, trail + [str(index)])
                elif isinstance(node, str) and (Path(node).is_absolute() or (len(node) > 2 and node[1] == ':')):
                    raise ContractError('Explicit resource binding required: ' + '.'.join(trail),
                                        code='export_missing_resource')
            reject_absolute(payload, [unit['unit_id']])
    value['storage_bindings'] = []
    value['execution_policy'] = {**value['execution_policy'], 'admission': 'standalone-package'}
    result = RunPlan.model_validate(value).with_identity()
    return result, inputs
