"""Receipts for the verified source-to-wheel namespace transformation.

Source-authored routes use a bundled code identity; installed providers use a
private namespace and an exact wheel identity. Only a library whose wheels were
reproduced from its included sources may establish this bridge. Standalone wheel
installs and unknown code never acquire a source compatibility fallback.
"""
from copy import deepcopy


def receipt(manifest, root, document, bundle_sha):
    from operon_sdk.declarations import DeclarationCompiler

    compiler = DeclarationCompiler(root)
    wheels = {p['name']: document['files'][p['file']] for p in document['packages']}
    providers = []
    for package in manifest['packages']:
        if package['name'] not in wheels:
            continue
        sources = {}
        for descriptor in package['descriptors']:
            actual = compiler.capture(descriptor['entry_point'])
            if actual != descriptor['code_sha']:
                raise ValueError(f"Library source code identity mismatch: {descriptor['id']}")
            sources[descriptor['id']] = actual
        providers.append({'package': package['name'], 'version': package['version'],
                          'wheel_sha256': wheels[package['name']], 'sources': sources})
    compiler.verify()
    return {'schema_version': 1, 'bundle_sha256': bundle_sha, 'providers': providers}


def replacements(graph, state):
    from operon.pins import graphs, identity

    proof = state.get('library_source_pins') or {}
    if proof.get('schema_version') != 1:
        return {}
    if proof.get('bundle_sha256') != (state.get('library_release') or {}).get('sha256'):
        return {}
    providers = {p['package']: p for p in proof['providers']}
    available = {d['id']: d for d in state['descriptors']}
    result = {}
    for part in graphs(graph):
        for key, before in part.plugin_lock.items():
            descriptor = available.get(key)
            provider = providers.get(before.get('package'))
            if not descriptor or not provider or before.get('execution_sha'):
                continue
            after = descriptor['implementation']
            # Bundled source identities ignore declaration-only index SHA
            # changes. The entire source-code tree, package and version must
            # still match the source whose wheel we rebuilt byte-for-byte.
            if (descriptor.get('origin') == 'wheel'
                    and before.get('code_sha') == provider['sources'].get(key)
                    and before.get('code_sha')
                    and before.get('version') == provider['version'] == after.get('version')
                    and before['package'] == descriptor['distribution'] == after.get('package')
                    and after.get('sha256') == provider['wheel_sha256']
                    and before['code_sha'] != after.get('code_sha')):
                result[key, identity(before)] = deepcopy(after)
    return result
