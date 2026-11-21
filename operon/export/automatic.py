"""Metadata-only provider collection for canvas execution and portable export.

Collect whole *selected provider namespaces*, including data files, because an
AST cannot discover arbitrary importlib/resource access. Never import providers
or guess that a user parameter is a file. External resources still require a
declaration; missing resources fail with the owning implementation ID.
"""
from pathlib import Path
import ast
import os

from operon.contracts.base import ContractError
from operon.environment_store.verification import confined, file_digest
from .collector import KERNEL_MODULES, LOCAL_PREFIXES, kernel_files, module_file, collect, validate_coverage


def provider_roots(manager, state, application_root):
    roots = [Path(application_root)]
    base = Path(state.get('_runtime_root') or manager.directory)
    roots.extend(confined(base, value) for value in state.get('code_paths', []))
    if manager.source_root:
        roots.append(Path(manager.source_root))
    return list(dict.fromkeys(path.resolve() for path in roots if path.is_dir()))


def _files(directory):
    for parent, dirs, files in os.walk(directory, followlinks=False):
        dirs[:] = [name for name in dirs if name not in ('__pycache__', '.git', '.pytest_cache')]
        for name in dirs + files:
            path = Path(parent) / name
            if path.is_symlink() or getattr(path.lstat(), 'st_file_attributes', 0) & 0x400:
                raise ContractError('Provider aliases must be declared and materialized: ' + str(path),
                                    code='export_missing_resource')
        for name in files:
            if not name.endswith(('.pyc', '.pyo')):
                yield Path(parent) / name


def local_import_modules(paths, root):
    """Modules under LOCAL_PREFIXES that these provider files import by name."""
    found = set()
    for path in paths:
        try:
            tree = ast.parse(Path(path).read_text(encoding='utf-8-sig', errors='replace'))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [item.name for item in node.names]
            elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
                names = [node.module, *(node.module + '.' + item.name for item in node.names if item.name != '*')]
            for name in names:
                if name.split('.')[0] in LOCAL_PREFIXES and module_file(root, name) is not None:
                    found.add(name)
    return found


def provider_kernel_modules(plan, roots, application_root):
    """Local modules a selected provider imports but the kernel closure may miss.

    A Reader is package code that can still import the shared ``src`` namespace
    (``operon_readers.readers.csv_reader`` imports ``src.core.numeric``).  The
    kernel closure only follows the modules it starts from, so those files would
    otherwise be absent from the frozen tree and the reader fails to import.
    """
    descriptors = (plan.diagnostics or {}).get('native_descriptor_audit', {})
    files = []
    for identifier in plan.implementations:
        if identifier.startswith('operon.script.'):
            continue
        descriptor = descriptors.get(identifier) or {}
        module = descriptor.get('entry_point', '').split(':')[0]
        if not module:
            continue
        prefix = next((p for p in ('src.task.step.steps', 'src.reader.readers')
                       if module.startswith(p + '.')), module.split('.')[0])
        for root in roots:
            namespace = Path(root).joinpath(*prefix.split('.'))
            if namespace.is_dir():
                files.extend(_files(namespace))
    return local_import_modules(files, application_root)


def collect_canvas_code(plan, destination, *, application_root, roots, kernel=None):
    """Return automatically generated, hash-verified implementation manifests."""
    application_root, destination = Path(application_root), Path(destination)
    if kernel is None:
        extra = sorted(provider_kernel_modules(plan, roots, application_root))
        kernel = kernel_files(application_root, modules=(*KERNEL_MODULES, *extra))
    collect(application_root, destination, kernel)
    audit = plan.diagnostics.get('native_descriptor_audit', {})
    manifests, owners = {}, dict(kernel)
    for identifier, implementation in plan.implementations.items():
        descriptor = audit.get(identifier)
        if not descriptor:
            raise ContractError('Missing frozen declaration: ' + identifier, code='implementation_unavailable')
        if identifier.startswith('operon.script.'):
            # Source lives in the frozen task parameters. The adapter is kernel code.
            names = {name: item for name, item in kernel.items() if name.startswith('operon/script')}
            if not names:
                raise ContractError('Script adapter missing from kernel', code='export_missing_resource')
            manifests[identifier] = {'implementation': implementation['implementation'], 'files': names}
            continue
        entry = descriptor.get('entry_point', '')
        module = entry.split(':')[0]
        candidates = [(root, module_file(root, module)) for root in roots]
        candidates = [(root, path) for root, path in candidates if path is not None]
        if not candidates:
            raise ContractError('Installed implementation is missing: ' + identifier,
                                code='implementation_unavailable')
        # Verify the original audit declaration, not the execution projection.
        from operon_sdk.declarations import verify_code
        valid = []
        for root, path in candidates:
            try:
                verify_code(descriptor, root=root)
                valid.append((root, path))
            except ValueError:
                continue
        if not valid:
            raise ContractError('Installed code differs from saved route: ' + identifier,
                                code='implementation_unavailable')
        root, entry_path = valid[0]
        # Legacy namespaces share src with the kernel. Do not copy all src/web.
        prefix = next((p for p in ('src.task.step.steps', 'src.reader.readers')
                       if module.startswith(p + '.')), module.split('.')[0])
        namespace = root.joinpath(*prefix.split('.'))
        files = list(_files(namespace)) if namespace.is_dir() else [entry_path]
        # Parent package initializers are required, but kernel owns shared parents.
        for depth in range(1, len(prefix.split('.'))):
            init = root.joinpath(*prefix.split('.')[:depth], '__init__.py')
            if init.is_file() and init.relative_to(root).as_posix() not in kernel:
                files.append(init)
        manifest = {}
        for path in files:
            name = path.relative_to(root).as_posix()
            item = {'path': name, 'sha256': file_digest(path), 'role': 'implementation'}
            if name in owners and owners[name]['sha256'] != item['sha256']:
                raise ContractError('Conflicting provider namespace: ' + name, code='export_missing_resource')
            owners[name] = item
            manifest[name] = item
        collect(root, destination, manifest)
        manifests[identifier] = {'implementation': implementation['implementation'], 'files': manifest}
    validate_coverage(plan, manifests)
    return manifests


def bind_declared_resources(data, *, workspace, base_dir, input_roots):
    """Only schema-declared path values become package resources, never heuristics."""
    from operon.planning.graph_compiler import input_path
    audit = data['diagnostics'].get('native_descriptor_audit', {})
    files = {}
    def bind(values, descriptor, base):
        for name, schema in descriptor.get('parameters_schema', {}).get('properties', {}).items():
            value = values.get(name)
            if not schema.get('x-operon-path') or not value:
                continue
            if not isinstance(value, str):
                raise ContractError('Declared resource must be a file path: ' + name, code='export_missing_resource')
            source = input_path(workspace, value, base, input_roots)
            if not source.is_file() or source.is_symlink():
                raise ContractError('Declared resource is unavailable: ' + name, code='export_missing_resource')
            digest = file_digest(source)
            relative = 'resources/' + digest + '/' + source.name
            files[relative] = {'source': str(source), 'sha256': digest, 'role': 'resource'}
            values[name] = 'storage://__code__/' + relative
    for unit in data['units']:
        manifest = unit['payload'].get('task_manifest', {})
        for step in manifest.get('steps', []):
            bind(step['params'], audit.get(step['name'], {}), base_dir)
        for source in manifest.get('sources', {}).values():
            original = Path(source['path'])
            source_base = str(original.parent) if original.is_absolute() else base_dir
            bind(source.get('args', {}), audit.get(source.get('reader'), {}), source_base)
    data['execution_policy']['packaged_resources'] = {key: value['sha256'] for key, value in files.items()}
    return files
