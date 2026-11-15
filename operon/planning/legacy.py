"""Compatibility boundary to the existing graph compiler.

This normalizes the legacy graph shape into the shared planning-domain compiler.
The web layer re-exports that same implementation; no web imports or second DAG
implementation are needed by headless compilation.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from operon.contracts.base import ContractError
from operon.contracts.workflow import FrozenParameters, WorkflowSpec
from .compiler import CompiledWorkflow
from .resolver import CatalogSnapshot


def freeze_spec(spec, catalog, root):
    """Freeze absent defaults once, preserving every explicit value, including null."""
    from .graph_models import Graph
    from .parameters import freeze_graph
    mapping = {'operators': list(catalog.operators), 'readers': list(catalog.readers)}
    graph = Graph.model_validate(spec.to_legacy_dict())
    return WorkflowSpec.from_graph(freeze_graph(graph, mapping, Path(root or '.').resolve()))


def effective_descriptors(manifest, catalog):
    """Include selected Readers, expanded scripts and inserted converters, without imports."""
    from operon.reader_selection import candidates
    result = {}
    operators = {d['id']: d for d in catalog.operators}
    exchanges = set((manifest.get('runtime') or {}).get('exchange_inputs', []))
    for name, source in manifest['sources'].items():
        if name in exchanges:
            continue
        for descriptor in candidates(list(catalog.readers), source['path'], source.get('reader')):
            result[descriptor['id']] = deepcopy(descriptor)
    for step in manifest['steps']:
        descriptor = operators.get(step['name'])
        if descriptor is None and step['name'].startswith('operon.script.'):
            script = step['params']['script']
            descriptor = {'id': step['name'], 'kind': 'operator',
                          'implementation': {'code_sha': script['code_sha']},
                          'dependencies': script.get('dependencies', []),
                          'resources': {'language': script['language'],
                                        'requires_python': script.get('requires_python')}}
        if descriptor is None:
            raise ContractError('Compiled operator is missing from the catalog',
                                code='unknown_operator', details={'operator': step['name']})
        result[descriptor['id']] = deepcopy(descriptor)
        for conversion in step.get('conversions', []):
            for converter in conversion['plan'].get('converters', []):
                key = 'converter:' + converter['id']
                result[key] = {**deepcopy(converter), 'id': key, 'kind': 'converter',
                               'implementation': {'code_sha': converter.get('code_sha'),
                                                  'version': converter.get('version')}}
    return tuple(result.values())


def compile_legacy(spec: WorkflowSpec, values: FrozenParameters, catalog: CatalogSnapshot,
                   root: Path | None, *, require_files: bool = False, freeze_defaults=True) -> CompiledWorkflow:
    from .graph_compiler import compile_graph
    from .graph_models import Graph
    from operon.parameter_values import split_task

    graph_value = spec.to_legacy_dict()
    try:
        graph = Graph.model_validate(graph_value)
    except Exception as exc:  # noqa: BLE001 - normalize as a planning failure
        raise ContractError(f'Legacy graph normalization failed: {exc}',
                            code='invalid_workflow') from exc
    catalog_mapping = {'operators': list(catalog.operators), 'readers': list(catalog.readers),
                       'generation': catalog.generation}
    base = Path(root or '.').resolve()
    try:
        manifest, step_ids = compile_graph(graph, catalog_mapping, base,
                                           require_files=require_files, freeze_defaults=freeze_defaults)
    except Exception as exc:  # noqa: BLE001 - existing compiler has stable prose/GraphError
        raise ContractError(str(exc), code='compile_failed',
                            details={'type': type(exc).__name__}) from exc
    task, task_values = split_task(deepcopy(manifest))
    frozen = FrozenParameters.from_values(task_values)
    return CompiledWorkflow(spec=spec, values=frozen, manifest=manifest,
                            step_ids=tuple(step_ids), graph=graph.model_dump(mode='json'),
                            descriptors=effective_descriptors(manifest, catalog))


class LegacyPlanAdapter:
    """Callable adapter matching ``WorkflowCompiler(legacy_compile=...)``."""

    def __call__(self, spec, values, catalog, root, *, require_files=False, freeze_defaults=True):
        return compile_legacy(spec, values, catalog, root, require_files=require_files, freeze_defaults=freeze_defaults)
