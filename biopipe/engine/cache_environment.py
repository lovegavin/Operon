"""Probe the selected scientific interpreter without importing scientific code.

This file also runs as a standalone child script in another Python environment.
Unknown isolated/native-tool environments are deliberately not cache eligible.
"""
import hashlib
import json
from pathlib import Path
import sys


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def inspect(requirements):
    from importlib import metadata
    from packaging.requirements import Requirement
    from packaging.utils import canonicalize_name
    distributions = {}
    for d in metadata.distributions():
        if d.metadata.get('Name'):
            distributions.setdefault(canonicalize_name(d.metadata['Name']), d)
    pending = [Requirement(r) for r in requirements]
    seen, contents = set(), {}
    while pending:
        requirement = pending.pop()
        if requirement.marker is not None and not requirement.marker.evaluate():
            continue
        if requirement.extras:
            raise ValueError('Optional dependency groups require explicit cache environment support')
        name = canonicalize_name(requirement.name)
        dist = distributions[name]
        if not requirement.specifier.contains(dist.version, prereleases=True):
            raise ValueError(f'Installed dependency does not satisfy {requirement}')
        if name in seen:
            continue
        seen.add(name)
        if not dist.files:
            raise ValueError(f'Unverifiable package files: {name}')
        files = []
        for item in dist.files:
            path = Path(dist.locate_file(item))
            if path.suffix in ('.pyc', '.pyo') or '__pycache__' in path.parts:
                continue
            if not path.is_file():
                raise ValueError(f'Incomplete installed package: {name}')
            files.append((str(item), file_hash(path)))
        contents[name] = {'version': dist.version, 'files': sorted(files)}
        for raw in dist.requires or []:
            req = Requirement(raw)
            if req.marker is None or req.marker.evaluate():
                pending.append(req)
    value = {'python': str(Path(sys.executable).resolve()), 'binary': file_hash(sys.executable),
             'version': sys.version, 'prefix': sys.prefix, 'base_prefix': sys.base_prefix,
             'installed': sorted((n, d.version) for n, d in distributions.items()), 'dependencies': contents}
    return {'verified': True, 'executable': value['python'],
            'digest': hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()}


def fingerprint(service, stage):
    import os
    import subprocess
    import tempfile
    try:
        if service.pool_remote:
            service._ensure_pool_session()
            return service.pool_client.request('environment.fingerprint', {
                'workspace': str(service.root), 'principal': service.pool_principal,
                'graph': stage.model_dump(mode='json')})
        state = service.plugins.snapshot(stage)
        selected = set(stage.plugin_lock)
        requirements = {'numpy'}
        for descriptor in state['descriptors']:
            if descriptor['id'] not in selected:
                continue
            resource = descriptor.get('resources') or {}
            if (descriptor.get('execution', {}).get('mode') == 'isolated'
                    or resource.get('environment') or resource.get('external_tools')
                    or resource.get('tools') or resource.get('r') is not None):
                return {'verified': False, 'error': 'isolated-or-external-environment-unverified'}
            requirements.update(descriptor.get('dependencies') or [])
        python = service.plugins.python_for(state)
        with tempfile.TemporaryDirectory(prefix='cache-probe-', dir=service.directory) as temporary:
            output = Path(temporary) / 'result.json'
            from biopipe.targets import paths_for
            paths = paths_for(state) if state.get('runtime_protocol') == 1 else []
            request = Path(temporary) / 'request.json'
            request.write_text(json.dumps({'requirements': sorted(requirements), 'paths': paths}), encoding='utf-8')
            with (Path(temporary) / 'console.log').open('wb') as console:
                result = subprocess.run([str(python), '-P', str(Path(__file__).resolve()),
                                         str(request), str(output)],
                                        cwd=service.root, stdin=subprocess.DEVNULL, stdout=console,
                                        stderr=console, timeout=120,
                                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            if result.returncode or not output.is_file():
                return {'verified': False, 'error': 'execution-environment-probe-failed'}
            return json.loads(output.read_text(encoding='utf-8'))
    except Exception as exc:
        return {'verified': False, 'error': f'{type(exc).__name__}: {exc}'}


if __name__ == '__main__':
    request = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    sys.path[:0] = request['paths']
    Path(sys.argv[2]).write_text(json.dumps(inspect(request['requirements'])), encoding='utf-8')
