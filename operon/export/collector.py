"""Explicit payload collection with hash verification and dynamic resource hooks."""
from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
import shutil

from operon.contracts.base import ContractError
from operon.environment_store.verification import confined, file_digest, inventory

# This is a kernel entry/dependency manifest, not a copy of the application tree.
# AST traversal expands ordinary local imports; dynamic worker/SDK resources are
# required separately from selected implementation manifests below.
KERNEL_MODULES = (
    'operon.export.kernel', 'operon.execution.unit_executor',
    'operon.execution.worker_main', 'operon.execution.containment',
    'operon.runtime_bootstrap', 'operon.worker',
    'operon.engine.coordinator', 'operon.engine.artifacts', 'operon.engine.state',
    'operon.planning.compiler', 'operon.planning.graph_compiler',
    'operon_sdk.declarations', 'operon_sdk.protocol', 'src.task', 'src.reader',
    # src.task exposes these through a string-based lazy public API; following
    # import statements alone cannot discover the Context/runner boundary.
    'src.task.context', 'src.task.manifest', 'src.task.runner', 'src.task.step',
    'operon_sdk.native_array', 'operon_sdk.resources', 'operon_sdk.operator',
    'operon_sdk.figures', 'src.reader.disk',
)
LOCAL_PREFIXES = ('operon', 'operon_sdk', 'src')


def module_file(root, module):
    # Import attributes such as ``Context`` are not filesystem modules. Windows
    # exists() is case-insensitive, but Python's module spelling is not; using
    # that false match would stage Context/ and hide the real context/ package.
    parent = root
    parts = module.split('.')
    for part in parts[:-1]:
        if not parent.is_dir() or part not in {item.name for item in parent.iterdir()}:
            return None
        parent = parent / part
    if not parent.is_dir():
        return None
    names = {item.name for item in parent.iterdir()}
    if parts[-1] not in names and parts[-1] + '.py' not in names:
        return None
    base = root.joinpath(*module.split('.'))
    if base.with_suffix('.py').is_file():
        return base.with_suffix('.py')
    if (base / '__init__.py').is_file():
        return base / '__init__.py'
    return None


def kernel_files(root, modules=KERNEL_MODULES):
    """Metadata-only closure, complemented by explicit dynamic resource records."""
    root = Path(root).resolve()
    missing = [name for name in modules if module_file(root, name) is None]
    if missing:
        raise ContractError('Required kernel modules are missing: ' + ', '.join(missing), code='export_missing_resource')
    pending, visited, result = list(modules), set(), {}
    while pending:
        module = pending.pop()
        if module in visited:
            continue
        visited.add(module)
        source = module_file(root, module)
        if source is None:
            continue  # from package import attribute, or third-party distribution
        relative = source.relative_to(root).as_posix()
        result[relative] = {'path': relative, 'sha256': file_digest(source), 'role': 'kernel'}
        package = module if source.name == '__init__.py' else module.rpartition('.')[0]
        for size in range(1, len(module.split('.'))):
            pending.append('.'.join(module.split('.')[:size]))
        tree = ast.parse(source.read_text(encoding='utf-8-sig'), filename=relative)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                pending.extend(item.name for item in node.names if item.name.split('.')[0] in LOCAL_PREFIXES)
            elif isinstance(node, ast.ImportFrom):
                name = node.module or ''
                if node.level:
                    try:
                        name = importlib.util.resolve_name('.' * node.level + name, package)
                    except (ImportError, ValueError):
                        raise ContractError('Cannot resolve kernel relative import', code='export_missing_resource')
                if name.split('.')[0] in LOCAL_PREFIXES:
                    pending.append(name)
                    pending.extend(name + '.' + item.name for item in node.names if item.name != '*')
    return result


def collect(root, destination, manifest, *, cancel=None):
    """manifest keys are destination-relative names; paths remain under source root."""
    root, destination = Path(root).resolve(), Path(destination).resolve()
    for relative, record in sorted(manifest.items()):
        if cancel and cancel():
            raise InterruptedError('Payload collection cancelled')
        source, target = confined(root, record['path']), confined(destination, relative)
        if not source.is_file() or source.is_symlink() or file_digest(source) != record['sha256']:
            raise ContractError('Required source/resource differs from its manifest: ' + relative,
                                code='export_missing_resource')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        if file_digest(target) != record['sha256']:
            raise ContractError('Copied resource failed verification', code='artifact_mismatch')
    return inventory(destination)


def validate_coverage(plan, implementations):
    missing = sorted(set(plan.implementations) - set(implementations))
    if missing:
        raise ContractError('Implementation/resource manifests missing: ' + ', '.join(missing),
                            code='export_missing_resource', details={'operators': missing})
    for identifier, expected in plan.implementations.items():
        supplied = implementations[identifier]
        from operon.pins import equivalent
        lhs = expected.get('implementation') or {}
        rhs = supplied['implementation']
        # Old exact pins may omit execution_sha. The shared pin semantics
        # compare their archive SHA rather than treating audit fields as code.
        if (not equivalent(lhs, rhs, bundled=expected.get('origin') == 'bundled')
                or any(lhs.get(key) != rhs.get(key) for key in ('resource_digest', 'sdk_abi'))):
            raise ContractError('Implementation manifest differs from frozen plan: ' + identifier,
                                code='implementation_unavailable')
        if not supplied.get('files'):
            raise ContractError('Implementation has no explicit payload/resources: ' + identifier,
                                code='export_missing_resource')
