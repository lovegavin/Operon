"""Freeze a selected private Python once; reuse package-level receipts thereafter.

This is explicit run/export preparation, never startup or registry discovery.
Scientific installations are never modified. System/Conda interpreters acquire
a private bootstrap and preserve scientific closures separately.
"""
from pathlib import Path
import json
import os
import tarfile
import uuid

from operon.contracts.base import ContractError, sha256_hex
from operon.contracts.run_plan import EnvironmentRequirement, TargetSpec
from operon.engine.fs import FileLock, atomic_json
from operon.plugins import run_process
from operon.bytecode import io_path
from . import EnvironmentStore
from .builders import LockedArchive, LockedArchiveBuilder
from .verification import file_digest, confined


PROBE = '''import json,sys,sysconfig,platform,importlib.metadata as m
print(json.dumps(dict(executable=sys.executable,prefix=sys.prefix,base_prefix=sys.base_prefix,
 version=list(sys.version_info[:3]),os=platform.system().lower(),arch=platform.machine().lower(),
 purelib=sysconfig.get_path('purelib'),distributions=sorted((d.metadata.get('Name',''),d.version) for d in m.distributions()))))
'''


def archive_tree(root, output, *, exclude=(), cancel=None):
    """One initial seal. No outside symlinks, special files, or changing files."""
    root = io_path(Path(root).resolve(strict=True))
    total = 0
    with tarfile.open(io_path(output), 'x', format=tarfile.PAX_FORMAT) as archive:
        for parent, dirs, files in os.walk(root, followlinks=False):
            dirs[:] = sorted(name for name in dirs if name not in ('__pycache__', '.git', *exclude))
            for name in sorted(dirs + files):
                if cancel and cancel():
                    raise InterruptedError('Runtime preparation cancelled')
                path = Path(parent) / name
                if getattr(path.lstat(), 'st_file_attributes', 0) & 0x400:
                    raise ContractError('Runtime contains an external alias', code='environment_preparation_required')
                if path.is_symlink():
                    if not path.resolve().is_relative_to(root.resolve()):
                        raise ContractError('Runtime alias escapes its prefix', code='environment_preparation_required')
                    info = archive.gettarinfo(str(path), path.relative_to(root).as_posix())
                    info.linkname = os.path.relpath(path.resolve(), path.parent)
                    archive.addfile(info)
                    continue
                if path.is_dir() or name.endswith(('.pyc', '.pyo')):
                    continue
                if not path.is_file():
                    raise ContractError('Runtime contains a special file', code='environment_preparation_required')
                before = path.stat()
                info = archive.gettarinfo(str(path), path.relative_to(root).as_posix())
                info.uid = info.gid = info.mtime = 0
                info.uname = info.gname = ''
                with path.open('rb') as stream:
                    archive.addfile(info, stream)
                after = path.stat()
                if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    raise ContractError('Runtime changed during preparation', code='environment_changed')
                total += before.st_size
    return total


def prepare_python(store_root, python, state, descriptors, *, cancel=None, r_root=None):
    """Capture dependency targets separately, retaining conflict-specific paths."""
    store_root = Path(store_root)
    store = EnvironmentStore(store_root)
    info = json.loads(run_process([python, '-I', '-c', PROBE], timeout=45))
    home = Path(info['base_prefix']).resolve(strict=True)
    prefix = Path(info['prefix']).resolve(strict=True)
    original_info = info
    from .closures import conda_prefix, discover, capture
    if str(home) in ('/', '/usr', '/usr/local') or conda_prefix(prefix):
        from .acquisition import standalone_python
        info = standalone_python(store_root, info)
        home = Path(info['base_prefix']).resolve(strict=True)
    executable = ('python.exe' if info['os'] == 'windows' else 'bin/python3')
    if not (home / executable).is_file():
        raise ContractError('Selected runtime has no relocatable Python entry', code='environment_preparation_required')
    base = Path(state.get('_runtime_root') or '.')
    shared = list(state.get('shared_paths', ()))
    isolated = sorted({path for d in descriptors for path in (d.get('execution') or {}).get('paths', ())})
    # Include target directory metadata, not an O(number of dependency files) walk.
    target_roots = [confined(base, path) for path in dict.fromkeys(shared + isolated)]
    external = {}
    names = sorted({d.get('resources', {}).get('environment') for d in descriptors
                    if d.get('resources', {}).get('environment')})
    if names:
        from operon.environments import resolve
        for name in names:
            selected = resolve(name)
            if selected is None:
                raise ContractError('Prepare the declared environment: ' + name,
                    code='environment_preparation_required', next_actions=({'action': 'prepare_environment'},))
            details = json.loads(run_process([str(selected), '-I', '-c', PROBE], timeout=45))
            directory = Path(details['base_prefix']).resolve()
            external[name] = details
    discovered = discover(original_info, descriptors, external, store_root=store_root, r_root=r_root)
    def stamp(path):
        value = Path(path).stat()
        return [str(path), value.st_size, value.st_mtime_ns]
    implementation = {name: file_digest(Path(__file__).with_name(name))
                      for name in ('canvas.py', 'closures.py', 'acquisition.py')}
    key = sha256_hex({'format': 2, 'preparer': implementation, 'python': info, 'selected': original_info, 'binary': stamp(home / executable),
        'generation': state.get('generation'), 'targets': [stamp(path) for path in target_roots],
        'external': external, 'closures': discovered})
    cache = store_root / 'canvas'; cache.mkdir(exist_ok=True)
    receipt = cache / (key + '.json')
    with FileLock(cache / (key + '.lock'), timeout=1800):
        if io_path(receipt).is_file():
            value = json.loads(io_path(receipt).read_text(encoding='utf-8'))
            binding = store.binding(value['generation_id'])
            if binding.requirement_digest != sha256_hex(value['requirement']):
                raise ContractError('Canvas environment receipt differs', code='environment_corrupt')
            return value
        staging = cache / ('prepare-' + uuid.uuid4().hex); io_path(staging).mkdir()
        archives = []
        def add(path, destination, exclude=()):
            archive = staging / (str(len(archives)) + '.tar')
            size = archive_tree(path, archive, exclude=exclude, cancel=cancel)
            archives.append(LockedArchive(archive, file_digest(archive), destination, size, 'tar'))
        # A venv contributes packages, never its interpreter launcher or pyvenv.cfg.
        add(home, 'runtime', exclude=('site-packages', 'dist-packages'))
        packages = Path(original_info['purelib'])
        if discovered['python']:
            # Bootstrap management dependencies must themselves be relocatable;
            # scientific Conda packages stay in their patched scientific prefix.
            packages = staging / 'management-packages'
            core = ('numpy', 'pydantic', 'psutil', 'PyYAML', 'jsonschema', 'packaging')
            from packaging.utils import canonicalize_name
            versions = {canonicalize_name(name): version for name, version in original_info['distributions']}
            requirements = [name + '==' + versions[canonicalize_name(name)] for name in core]
            run_process([str(home / executable), '-I', '-m', 'pip', 'install', '--disable-pip-version-check',
                         '--no-compile', '--only-binary=:all:', '--target', str(packages), *requirements], timeout=1200)
        if packages.is_dir():
            add(packages, 'packages')
        paths = {}
        for index, path in enumerate(target_roots):
            destination = 'targets/' + str(index)
            add(path, destination)
            paths[str(path)] = destination
        external_interpreters = {}
        external_probes = []
        for index, (name, details) in enumerate(external.items()):
            if name in discovered['external']:
                continue
            prefix = 'external/' + str(index)
            home = Path(details['base_prefix'])
            if str(home) in ('/', '/usr', '/usr/local'):
                from .acquisition import standalone_python
                home = Path(standalone_python(store_root, details)['base_prefix'])
            add(home, prefix, exclude=('site-packages', 'dist-packages'))
            package_path = 'Lib/site-packages' if details['os'] == 'windows' else 'lib/python' + '.'.join(map(str, details['version'][:2])) + '/site-packages'
            add(Path(details['purelib']), prefix + '/' + package_path)
            external_executable = prefix + ('/python.exe' if details['os'] == 'windows' else '/bin/python3')
            external_interpreters[name] = external_executable
            modules = sorted({module for d in descriptors if d.get('resources', {}).get('environment') == name
                              for module in d.get('dependency_imports', [])})
            external_probes.append((external_executable, '-I', '-B', '-c', 'import importlib; '
                '[importlib.import_module(n) for n in ' + repr(modules) + ']'))
        shared_targets = [paths[str(confined(base, path))] for path in shared]
        relative_python = 'runtime/' + executable
        # The actual relocated runtime must resolve required imports and engine
        # dependencies within this payload; a developer PYTHONPATH cannot help.
        imports = sorted({'psutil', 'pydantic', 'yaml', 'jsonschema', 'numpy', 'packaging'} |
            {name for d in descriptors if (d.get('execution') or {}).get('mode') != 'isolated' and not d.get('resources', {}).get('environment')
             for name in d.get('dependency_imports', []) if isinstance(name, str)})
        check = ('import sys,pathlib,importlib,os,json; root=pathlib.Path.cwd(); '
                 'sys.path[:0]=[str(root/p) for p in ' + repr(shared_targets) + '] + '
                 'json.loads(os.environ.get("OPERON_PACKED_PYTHON_PATHS","[]")) + [str(root/"packages")]; '
                 'mods=[importlib.import_module(n) for n in ' + repr(imports) + ']; '
                 'roots=[root,*map(pathlib.Path,json.loads(os.environ.get("OPERON_PACKED_PREFIXES","[]")))]; '
                 'assert all(not getattr(m,"__file__",None) or any(pathlib.Path(m.__file__).resolve().is_relative_to(r.resolve()) for r in roots) for m in mods)')
        probes = [(relative_python, '-I', '-B', '-c', check), *external_probes]
        for d in descriptors:
            if (d.get('execution') or {}).get('mode') == 'isolated':
                selected = [paths[str(confined(base, path))] for path in d['execution'].get('paths', [])]
                probes.append((relative_python, '-I', '-B', '-c',
                    'import sys,pathlib,importlib; r=pathlib.Path.cwd(); sys.path[:0]=[str(r/p) for p in ' +
                    repr(selected + ['packages']) + ']; [importlib.import_module(n) for n in ' + repr(d.get('dependency_imports', [])) + ']'))
        if discovered['roots']:
            captured = staging / 'closures'
            capture(discovered, captured, store_root, cancel=cancel)
            add(captured, 'closures')
        builder = CanvasArchiveBuilder(archives, probes, timeout=180,
                                       relative_python=relative_python, imports=imports)
        target = TargetSpec(os=info['os'], arch={'amd64': 'x86_64', 'arm64': 'aarch64'}.get(info['arch'], info['arch']))
        requirement = EnvironmentRequirement(target=target, runtime='cpython-' + '.'.join(map(str, info['version'][:2])),
            dependency_lock={'artifact_hashes': [a.sha256 for a in archives], 'installed': original_info['distributions']},
            recipe_digest=sha256_hex(builder.recipe()))
        binding = store.prepare(requirement, builder, cancel=cancel)
        value = {'generation_id': binding.generation_id, 'executable': relative_python,
            'requirement': requirement.model_dump(mode='json'), 'shared_targets': shared_targets,
            'target_paths': paths, 'source_identity': key, 'external_interpreters': external_interpreters}
        atomic_json(receipt, value)
        # All blobs now belong to the immutable store. Only remove our source TARs.
        for item in archives:
            io_path(item.source).unlink()
        # Retain raw closure sources until successful immutable publication.
        if (staging / 'closures').exists():
            import shutil
            shutil.rmtree(io_path(staging / 'closures'))
        if (staging / 'management-packages').exists():
            import shutil
            shutil.rmtree(io_path(staging / 'management-packages'))
        io_path(staging).rmdir()
        return value


class CanvasArchiveBuilder(LockedArchiveBuilder):
    """Probe actual Conda/tool deployments, both before and after relocation."""
    def __init__(self, *args, relative_python, imports, **kwargs):
        super().__init__(*args, **kwargs)
        self.relative_python, self.imports = relative_python, imports

    def recipe(self):
        return {**super().recipe(), 'canvas_closures': 1,
                'relative_python': self.relative_python, 'imports': self.imports}

    def verify(self, root, *, cancel=None):
        from .closures import materialize, execution_environment
        from .builders import temporary_directory, probe
        import shutil
        results = []
        with temporary_directory('operon-closure-check-') as directory:
            for index, payload in enumerate((Path(root), Path(directory) / 'moved payload')):
                if index: shutil.copytree(io_path(root), io_path(payload), symlinks=True)
                selected = materialize(payload, Path(directory) / ('cache-' + str(index)),
                                       python=payload / self.relative_python, cancel=cancel)
                env = execution_environment(selected, {})
                # Test the selected scientific interpreter when a Conda closure
                # owns it; bootstrap imports are checked independently as well.
                for command in self.probes:
                    override = selected['python'] if command[0] == self.relative_python else None
                    results.append(probe(payload, command, timeout=self.timeout, cancel=cancel,
                                         environment=env, executable_override=override))
                if selected['python']:
                    results.append(probe(payload, (self.relative_python, '-I', '-c',
                        'import sys,importlib; sys.path.insert(0,' + repr(str(payload / 'packages')) + '); '
                        '[importlib.import_module(n) for n in ["pydantic","numpy","yaml","psutil","jsonschema","packaging"]]'),
                        timeout=self.timeout, cancel=cancel, environment=env))
                for record in selected['r'].values():
                    from operon.r_runtime import RRuntime
                    RRuntime()._probe(record['executable'], record['library'], record['spec'])
                for name, executable in selected['tools'].items():
                    # --version is not universal. Known usage-only probes must
                    # prove tool identity, not accept arbitrary loader failures.
                    from operon.processes import owned_process
                    import subprocess
                    log = Path(directory) / ('tool-' + sha256_hex(name)[:12] + '.log')
                    arguments = [] if name == 'bwa' else ['--version']
                    with log.open('wb') as output, owned_process([executable, *arguments], env={**os.environ, **env},
                                       stdout=output, stderr=subprocess.STDOUT) as child:
                        result = child.wait(timeout=30)
                    with log.open('rb') as stream:
                        detail = stream.read(8192).decode('utf-8', errors='replace')
                    if result and not (name == 'bwa' and result == 1 and 'Version:' in detail and 'Usage:' in detail):
                        raise ContractError(f'Packed tool {name} failed its launch probe: {detail}', code='environment_unverified')
        return {'status': 'passed', 'relocation': 'passed', 'probes': results}
