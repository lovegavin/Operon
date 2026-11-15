"""Automatically capture and redeploy private Conda/R/tool closures.

Packed inputs are immutable. Prefix fixups run once at the FINAL cache path,
never on the source installation or on a staging prefix subsequently renamed.
"""
from pathlib import Path
import json
import os
import shutil
import uuid

from operon.bytecode import io_path
from operon.contracts.base import ContractError, sha256_hex
from operon.engine.fs import FileLock, atomic_json
from operon.plugins import run_process
from .verification import confined, file_digest


def conda_prefix(path):
    for parent in (Path(path), *Path(path).parents):
        if (parent / 'conda-meta').is_dir():
            return parent
    return None


def discover(info, descriptors, external, *, store_root=None, r_root=None):
    """Read receipts and explicit declarations; never import scientific code."""
    roots, tools, r = {}, {}, {}

    def bind(path, *, prefix=None, kind='tree'):
        path = Path(path).resolve(strict=True)
        conda = conda_prefix(path)
        prefix = conda or prefix
        if prefix is None:
            # An arbitrary /usr/bin program can have dlopen/data dependencies.
            # Do not pretend ldd alone proves a portable scientific closure.
            raise ContractError('External tool has no self-contained prefix: ' + str(path),
                code='portable_tool_required', next_actions=({'action': 'prepare_environment'},))
        prefix = Path(prefix).resolve(strict=True)
        key = sha256_hex(str(prefix))[:24]
        root = {'source': str(prefix), 'kind': 'conda' if conda else kind}
        roots[key] = root
        return {'closure': key, 'path': path.relative_to(prefix).as_posix()}

    python = bind(info['executable']) if conda_prefix(info['prefix']) else None
    python_packages = [bind(info['purelib'])] if python else []
    children = {}
    for name, details in external.items():
        if conda_prefix(details['prefix']):
            children[name] = bind(details['executable'])
    from operon.dependencies import find_tool
    for d in descriptors:
        resources = d.get('resources') or {}
        names = list(resources.get('external_tools') or ())
        language = (d.get('script') or {}).get('language') or resources.get('language')
        if language and language != 'python':
            names.append({'r': 'Rscript', 'c': 'cc', 'cpp': 'c++'}.get(language, language))
        for name in names:
            # The selected scientific environment wins over the editor's PATH.
            # Named environments retain their own tool selection as well.
            details = external.get(resources.get('environment'), info)
            selected_prefix = Path(details['prefix'])
            suffix = '.exe' if os.name == 'nt' else ''
            selected = next((str(selected_prefix / folder / (name + suffix))
                             for folder in ('bin', 'Scripts', 'Library/bin', '')
                             if (selected_prefix / folder / (name + suffix)).is_file()), None)
            selected = selected or find_tool(name)
            if not selected:
                raise ContractError('Missing selected external tool: ' + name, code='environment_preparation_required')
            prefix = conda_prefix(selected)
            if name == 'Rscript' and prefix is None:
                home = run_process([selected, '--vanilla', '-e', 'cat(R.home())'], timeout=45).strip()
                # Windows R_HOME owns bin; Linux system R commonly has absolute
                # launcher paths and must first use a managed R/Conda prefix.
                if Path(selected).resolve().is_relative_to(Path(home).resolve()):
                    prefix = Path(home)
                elif store_root is not None:
                    from .acquisition import managed_r
                    selected = managed_r(store_root, selected)
                    prefix = conda_prefix(selected)
            if prefix is None:
                # Self-contained user tool installations (bin + lib + share).
                parent = Path(selected).resolve().parent
                candidate = parent.parent if parent.name.lower() in ('bin', 'scripts') else parent
                if candidate not in (Path('/'), Path('/usr'), Path('/usr/local'), Path('/bin')):
                    if not (candidate / 'pyvenv.cfg').exists() and ((candidate / 'lib').is_dir() or (candidate / 'share').is_dir()):
                        prefix = candidate
            binding = bind(selected, prefix=prefix)
            if name in tools and tools[name] != binding:
                raise ContractError('Conflicting portable tool bindings: ' + name,
                                    code='portable_tool_conflict')
            tools[name] = binding
        if resources.get('r'):
            from operon.r_runtime import RRuntime
            runtime = RRuntime(r_root)
            record = runtime.ensure(resources['r'], repair=False)
            home = run_process([record['executable'], '--vanilla', '-e', 'cat(R.home())'],
                               env=runtime._env(record['library'], record['executable']), timeout=45).strip()
            executable = record['executable']
            if not conda_prefix(executable) and not Path(executable).resolve().is_relative_to(Path(home).resolve()):
                from .acquisition import managed_r
                executable = managed_r(store_root, executable)
            exe = bind(executable, prefix=Path(home))
            library = bind(record['library'], prefix=Path(record['library']))
            r[runtime.key(resources['r'])] = {**record, 'executable': exe, 'library': library}
    # Directory timestamps alone miss in-place Conda package upgrades. Metadata
    # files are cheap to inspect, not an expanded dependency-file scan.
    for value in roots.values():
        root = Path(value['source'])
        metadata = sorted((root / 'conda-meta').glob('*.json')) if value['kind'] == 'conda' else []
        value['stamp'] = [(p.name, p.stat().st_size, p.stat().st_mtime_ns) for p in metadata]
        value['directory_stamp'] = root.stat().st_mtime_ns
    return {'roots': roots, 'python': python, 'python_packages': python_packages,
            'external': children, 'tools': tools, 'r': r}


def capture(discovered, directory, store_root, *, cancel=None):
    """Seal each selected prefix once; conda-pack never repairs the source."""
    from .acquisition import pack_conda
    from .canvas import archive_tree
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    result = {key: value for key, value in discovered.items() if key != 'roots'}
    result['roots'] = {}
    for key, value in discovered['roots'].items():
        if cancel and cancel(): raise InterruptedError('Closure preparation cancelled')
        archive = directory / (key + '.tar')
        if value['kind'] == 'conda':
            pack_conda(value['source'], archive, store_root)
        else:
            archive_tree(value['source'], archive, cancel=cancel)
        # The archive is already produced by a trusted local packer. Extraction
        # still applies traversal/special-member and expanded-size bounds.
        import tarfile
        with tarfile.open(archive) as stream:
            maximum = sum(item.size for item in stream)
        result['roots'][key] = {'archive': archive.name, 'sha256': file_digest(archive),
                                'max_unpacked_bytes': maximum, 'kind': value['kind']}
    atomic_json(directory / 'manifest.json', result)
    return result


def materialize(payload, cache, *, python, cancel=None):
    """Return path bindings without changing immutable payloads or host config."""
    from .builders import extract_locked
    payload, cache = Path(payload), Path(cache)
    manifest = payload / 'closures/manifest.json'
    if not io_path(manifest).is_file():
        return {'python': None, 'python_packages': [], 'external': {}, 'tools': {}, 'r': {}, 'paths': [], 'prefixes': []}
    value = json.loads(io_path(manifest).read_text(encoding='utf-8'))
    deployed = {}
    for key, item in value['roots'].items():
        # Final absolute location participates in the receipt: moving a cache
        # triggers fresh unpack from original bytes, not a second conda-unpack.
        folder = cache / sha256_hex({'sha256': item['sha256'], 'cache': str(cache.resolve())})[:32]
        receipt = folder.with_suffix('.ready.json')
        identity = {'archive': item['sha256'], 'prefix': str(folder.resolve())}
        with FileLock(folder.with_suffix('.lock'), timeout=1800):
            if not (io_path(receipt).is_file() and json.loads(io_path(receipt).read_text()) == identity
                    and io_path(folder).is_dir()):
                archive = confined(payload / 'closures', item['archive'])
                if file_digest(archive) != item['sha256']:
                    raise ContractError('Packed tool/runtime differs from its receipt', code='environment_corrupt')
                # Only this content-addressed, lock-owned partial directory.
                if io_path(folder).exists(): shutil.rmtree(io_path(folder))
                io_path(folder).mkdir(parents=True)
                extract_locked(archive, folder, format='tar', maximum=item['max_unpacked_bytes'], cancel=cancel)
                if item['kind'] == 'conda':
                    unpack = next((folder / p for p in ('bin/conda-unpack', 'Scripts/conda-unpack-script.py')
                                   if io_path(folder / p).is_file()), None)
                    if unpack is None:
                        raise ContractError('Packed Conda prefix has no relocation script', code='environment_unverified')
                    run_process([str(python), '-I', str(io_path(unpack))], timeout=600)
                atomic_json(receipt, identity)
        deployed[key] = folder
    def resolve(ref):
        return str(confined(deployed[ref['closure']], ref['path'])) if ref['path'] != '.' else str(deployed[ref['closure']])
    records = {key: {**record, 'executable': resolve(record['executable']), 'library': resolve(record['library'])}
               for key, record in value['r'].items()}
    return {'python': resolve(value['python']) if value['python'] else None,
            'python_packages': [resolve(ref) for ref in value.get('python_packages', [])],
            'external': {key: resolve(ref) for key, ref in value['external'].items()},
            'tools': {key: resolve(ref) for key, ref in value['tools'].items()}, 'r': records,
            'prefixes': [str(root) for root in deployed.values()],
            'paths': [str(root / p) for root in deployed.values() for p in ('bin', 'Scripts', 'Library/bin', 'lib')
                      if io_path(root / p).is_dir()]}


def execution_environment(bindings, environment):
    """Only package-owned locations; no original machine search paths."""
    result = dict(environment)
    result['PATH'] = os.pathsep.join(bindings['paths'] + [result.get('PATH', '')])
    result['OPERON_PACKED_TOOLS'] = json.dumps(bindings['tools'])
    result['OPERON_PACKED_R'] = json.dumps(bindings['r'])
    result['OPERON_PACKED_PREFIXES'] = json.dumps(bindings['prefixes'])
    result['OPERON_PACKED_PYTHON_PATHS'] = json.dumps(bindings.get('python_packages', []))
    for name, path in bindings['external'].items():
        result['OPERON_ENV_' + name.upper()] = path
    return result
