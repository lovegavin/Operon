"""Manifest-only library comparison and explicitly selected provider transfer.

Providers are the installation unit. Never remove remote-only declarations or
enable a disabled provider as a side effect of supplementing a library.
"""
from copy import deepcopy
from pathlib import Path
import shutil

from biopipe.packages import provider_identity
from .handshake import digest


def inventory(state):
    packages = []
    for package in state['packages']:
        entries = [{key: d.get(key) for key in ('id', 'kind', 'title', 'code_sha', 'declaration_sha')}
                   for d in state['descriptors'] if d['distribution'] == package['name']]
        packages.append({**{key: package.get(key) for key in ('name', 'version', 'origin', 'sha256')},
                         'enabled': package.get('enabled', True),
                         'entries': sorted(entries, key=lambda d: (d['kind'], d['id']))})
    value = {'packages': sorted(packages, key=lambda p: p['name'])}
    return {**value, 'revision': digest(value)}


def compare(local, remote, *, supported=True):
    remote_packages = {provider_identity(p['name']): p for p in remote['packages']}
    present = {(e['kind'], e['id']): p for p in remote['packages'] for e in p['entries']}
    groups = []
    for package in local['packages']:
        if not package['enabled']:
            continue
        owner = provider_identity(package['name'])
        previous = remote_packages.get(owner)
        missing = [e for e in package['entries'] if (e['kind'], e['id']) not in present]
        disabled = [e for e in package['entries'] if (e['kind'], e['id']) in present
                    and not present[e['kind'], e['id']]['enabled']]
        if not missing and not disabled:
            continue
        reason = None
        keys = {(e['kind'], e['id']) for e in package['entries']}
        if not supported:
            reason = 'server_upgrade_required'
        elif previous and not previous['enabled']:
            reason = 'remote_package_disabled'
        elif any((e['kind'], e['id']) not in keys for e in (previous or {}).get('entries', [])):
            reason = 'remote_only_entries'
        elif any(provider_identity(present[key]['name']) != owner for key in keys if key in present):
            reason = 'different_provider'
        groups.append({'name': package['name'], 'version': package['version'],
                       'remote_version': previous['version'] if previous else None,
                       'missing': missing, 'disabled': disabled,
                       'replaces': len(previous['entries']) if previous else 0,
                       'selectable': bool(missing) and reason is None, 'reason': reason})
    return {'local_revision': local['revision'], 'remote_revision': remote['revision'],
            'supported': supported, 'packages': groups,
            'missing_count': sum(len(p['missing']) for p in groups)}


def export_provider(manager, state, name, directory):
    """Export registered bytes only; source edits require an explicit refresh."""
    from biopipe.bytecode import filesystem_path
    from biopipe.library_bundle import sha256
    package = next(p for p in state['packages'] if p['name'] == name)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    if package['origin'] == 'wheel':
        source = Path(filesystem_path(manager.directory / package['wheel']))
        if sha256(source) != package['sha256']:
            raise ValueError(f'Registered package changed: {name}; refresh the local library first')
        wheel = directory / source.name
        shutil.copyfile(source, wheel)
    elif package['origin'] == 'bundled':
        from biopipe.library_location import source_root
        from biopipe.source_library import provider_wheel
        from biopipe_sdk.declarations import verify_code, verify_declaration
        root = source_root()
        descriptors = [deepcopy(d) for d in state['descriptors'] if d['distribution'] == name]
        # Factory entries share one code-tree identity. Verify its bytes once,
        # not a full source traversal for every operator in a large provider.
        verified = set()
        for descriptor in descriptors:
            verify_declaration(descriptor)
            if descriptor['code_sha'] not in verified:
                verify_code(descriptor, root)
                verified.add(descriptor['code_sha'])
        from biopipe_sdk.protocol import Descriptor
        descriptors = [{k: v for k, v in d.items() if k in Descriptor.model_fields} for d in descriptors]
        wheel = provider_wheel({**package, 'descriptors': descriptors}, root, directory)
    else:
        raise ValueError(f'Unsupported provider source: {name}')
    # Cross-platform native packages need a separately built server wheel.
    from packaging.utils import parse_wheel_filename
    if any(tag.platform != 'any' for tag in parse_wheel_filename(wheel.name)[3]):
        raise ValueError(f'{name} contains platform-specific code; install a server-compatible wheel on the server')
    return wheel


def install_selected(manager, transfers, payload):
    """One generation transaction with optimistic concurrency and safe ownership."""
    from biopipe.install_targets import wheel_entries
    from biopipe.library_bundle import sha256
    from packaging.utils import parse_wheel_filename
    from tempfile import TemporaryDirectory
    files = payload.get('files')
    if not isinstance(files, list) or not files:
        raise ValueError('Select at least one provider package')
    # Resolve only verified transfer objects, never arbitrary remote paths.
    with TemporaryDirectory(prefix='remote-library-', dir=manager.directory) as temporary:
        wheels, incoming, names = [], [], set()
        for item in files:
            filename = item['filename']
            if Path(filename).name != filename or '/' in filename or '\\' in filename:
                raise ValueError('Invalid wheel filename')
            name, version, _, tags = parse_wheel_filename(filename)
            if any(tag.platform != 'any' for tag in tags):
                raise ValueError('Remote library transfer requires portable provider wheels')
            owner = provider_identity(name)
            if owner in names:
                raise ValueError('Duplicate provider package')
            names.add(owner)
            source = transfers.reference(item['reference'])
            wheel = Path(temporary) / filename
            shutil.copyfile(source, wheel)
            if sha256(wheel) != item['reference']['sha256']:
                raise ValueError('Transferred package checksum mismatch')
            import json
            import zipfile
            with zipfile.ZipFile(wheel) as archive:
                manifests = [n for n in archive.namelist() if n.endswith('.dist-info/biopipe.json')]
                if len(manifests) != 1:
                    raise ValueError('A provider requires exactly one declaration manifest')
                manifest = json.loads(archive.read(manifests[0]))
                if manifest['name'] != name or manifest['version'] != str(version):
                    raise ValueError('Wheel filename and provider identity disagree')
            entries = [record['expected'] for record in wheel_entries(wheel)]
            incoming.append({'name': name, 'version': str(version), 'enabled': True, 'entries': entries})
            wheels.append(wheel)
        manager.state()
        with manager.lock:
            state = manager.state()
            current = inventory(state)
            if current['revision'] != payload.get('remote_revision'):
                raise ValueError('Server library changed; check the library again before installing')
            candidate = {'revision': '', 'packages': incoming}
            decision = compare(candidate, current)
            allowed = {provider_identity(p['name']) for p in decision['packages'] if p['selectable']}
            if names != allowed:
                raise ValueError('Selection is stale, disabled, or would replace remote-only operators; check the library again')
            # The package installer validates protocol, code/schema and ID
            # uniqueness, prepares immutable code, then publishes atomically.
            manager._install_many(wheels, state)
    return {'installed': sorted(names)}
