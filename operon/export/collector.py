"""Explicit payload collection with hash verification and dynamic resource hooks."""
from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
import shutil

from operon.contracts.base import ContractError
from operon.bytecode import io_path
from operon.environment_store.verification import confined, file_digest, inventory

# This is a kernel entry/dependency manifest, not a copy of the application tree.
# AST traversal expands ordinary local imports; dynamic worker/SDK resources are
# required separately from selected implementation manifests below.
KERNEL_MODULES = (
    'operon.export.kernel', 'operon.execution.unit_executor',
    'operon.execution.worker_main', 'operon.execution.containment',
    'operon.runtime_bootstrap', 'operon.worker',
    'operon.isolated_worker', 'operon.env_worker',
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
CODE_CLOSURE_ABI = 'operon-code-closure-v3'


def source_imports(source, module):
    """Yield module candidates and whether absence is an error for local code.

    from package import Name may name an attribute, not a submodule. Literal
    importlib calls are supported without executing code. Computed imports and
    non-code resources still need the explicit provider/resource contract.
    """
    package = module if source.name == '__init__.py' else module.rpartition('.')[0]
    tree = ast.parse(io_path(source).read_text(encoding='utf-8-sig'), filename=str(source))
    importlib_aliases = {'importlib'}
    import_function_aliases = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            importlib_aliases.update(item.asname or item.name for item in node.names if item.name == 'importlib')
        elif isinstance(node, ast.ImportFrom) and node.module == 'importlib' and not node.level:
            import_function_aliases.update(item.asname or item.name for item in node.names
                                           if item.name == 'import_module')
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for item in node.names:
                yield item.name, True
        elif isinstance(node, ast.ImportFrom):
            name = node.module or ''
            if node.level:
                try:
                    name = importlib.util.resolve_name('.' * node.level + name, package)
                except (ImportError, ValueError) as exc:
                    raise ContractError('Cannot resolve relative import in ' + str(source),
                                        code='export_missing_resource') from exc
            if name:
                yield name, True
                for item in node.names:
                    if item.name != '*':
                        yield name + '.' + item.name, False
        elif isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Constant):
            function = node.func
            recognized = (isinstance(function, ast.Name) and function.id in import_function_aliases | {'__import__'}
                          or isinstance(function, ast.Attribute) and function.attr == 'import_module'
                          and isinstance(function.value, ast.Name) and function.value.id in importlib_aliases)
            name = node.args[0].value
            if recognized and isinstance(name, str) and name and not name.startswith('.'):
                yield name, True


def checked_source(root, source):
    """Reject source aliases at every component, not only the final file."""
    root, source = Path(root).absolute(), Path(source).absolute()
    if not source.is_relative_to(root):
        raise ContractError('Code dependency escapes its root', code='export_missing_resource')
    current = root
    for part in (None, *source.relative_to(root).parts):
        if part is not None:
            current /= part
        info = io_path(current).lstat()
        if current.is_symlink() or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ContractError('Code dependency contains a filesystem alias: ' + str(current),
                                code='export_missing_resource')
    return source


def expand_local_dependencies(owners, *, application_root, roots, entry_files=None):
    """Expand selected code's imports into an owned, content-addressed closure.

    owners maps relative names to (source root, manifest record). Application
    namespaces resolve against the authoritative app first; explicit provider
    roots resolve other local modules. Never inspect Python site-packages.
    owners is the retained payload, not the traversal frontier. With explicit
    entry_files only selected entry points/kernel files and their imports are
    inspected; unrelated retained provider files are not dependency roots.
    """
    application_root = Path(application_root)
    roots = list(dict.fromkeys([application_root, *map(Path, roots)]))
    owners = dict(owners)
    local_prefixes = set(LOCAL_PREFIXES) | {name.split('/')[0].removesuffix('.py') for name in owners}
    entries = set(owners if entry_files is None else entry_files)
    if entries - owners.keys():
        raise ContractError('Dependency entry is outside the selected payload',
                            code='export_missing_resource')
    pending = [name for name in entries if name.endswith('.py')]
    visited, resolutions = set(), {}

    def resolve(module, required, source):
        if not module or not all(part.isidentifier() for part in module.split('.')):
            return None
        if module not in resolutions:
            choices = []
            # An explicitly selected/frozen provider namespace owns its entries,
            # including legacy src.reader.readers package initializers. Only
            # unowned dependencies fall back to the application/provider roots.
            selected = next((key for key in
                             (module.replace('.', '/') + '.py', module.replace('.', '/') + '/__init__.py')
                             if key in owners), None)
            if selected is not None:
                selected_root, _ = owners[selected]
                choices.append((selected_root, checked_source(selected_root, selected_root / selected)))
            for root in (() if choices else roots):
                path = module_file(root, module)
                if path is not None:
                    checked_source(root, path)
                    choices.append((root, path))
                    if root == application_root and module.split('.')[0] in LOCAL_PREFIXES:
                        break
            if len({file_digest(path) for _, path in choices}) > 1:
                raise ContractError('Ambiguous local dependency ' + module + ' imported by ' + source,
                                    code='export_missing_resource')
            resolutions[module] = choices[0] if choices else None
        found = resolutions[module]
        if found is None and required and module.split('.')[0] in local_prefixes:
            # A bare namespace parent may intentionally have no __init__.py.
            if not any(io_path(root.joinpath(*module.split('.'))).is_dir() for root in roots):
                raise ContractError('Missing local dependency ' + module + ' imported by ' + source,
                                    code='export_missing_resource')
        return found

    while pending:
        relative = pending.pop()
        if relative in visited:
            continue
        visited.add(relative)
        root, _ = owners[relative]
        source = checked_source(root, root / relative)
        parts = list(Path(relative).with_suffix('').parts)
        if parts[-1] == '__init__':
            parts.pop()
        module = '.'.join(parts)
        imports = list(source_imports(source, module))
        imports.extend(('.'.join(parts[:size]), False) for size in range(1, len(parts)))
        for name, required in imports:
            match = resolve(name, required, relative)
            if match is None:
                continue  # external distribution or from-import attribute
            dep_root, path = match
            local_prefixes.add(name.split('.')[0])
            dep_relative = path.relative_to(dep_root).as_posix()
            item = {'path': dep_relative, 'sha256': file_digest(path), 'role': 'dependency'}
            if dep_relative in owners:
                if owners[dep_relative][1]['sha256'] != item['sha256']:
                    raise ContractError('Conflicting local dependency: ' + dep_relative,
                                        code='export_missing_resource')
            else:
                owners[dep_relative] = (dep_root, item)
            if dep_relative not in visited:
                pending.append(dep_relative)
    return owners


def module_file(root, module):
    # Import attributes such as ``Context`` are not filesystem modules. Windows
    # exists() is case-insensitive, but Python's module spelling is not; using
    # that false match would stage Context/ and hide the real context/ package.
    parent = root
    parts = module.split('.')
    for part in parts[:-1]:
        if not io_path(parent).is_dir() or part not in {item.name for item in io_path(parent).iterdir()}:
            return None
        parent = parent / part
    if not io_path(parent).is_dir():
        return None
    names = {item.name for item in io_path(parent).iterdir()}
    if parts[-1] not in names and parts[-1] + '.py' not in names:
        return None
    base = root.joinpath(*module.split('.'))
    if io_path(base.with_suffix('.py')).is_file():
        return base.with_suffix('.py')
    if io_path(base / '__init__.py').is_file():
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
        tree = ast.parse(io_path(source).read_text(encoding='utf-8-sig'), filename=relative)
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
        if not io_path(source).is_file() or io_path(source).is_symlink() or file_digest(source) != record['sha256']:
            raise ContractError('Required source/resource differs from its manifest: ' + relative,
                                code='export_missing_resource')
        io_path(target.parent).mkdir(parents=True, exist_ok=True)
        shutil.copy2(io_path(source), io_path(target))
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
