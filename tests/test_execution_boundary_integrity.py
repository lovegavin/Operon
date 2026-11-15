"""Metadata corruption/overlap guards; no runtime platform acceptance claims."""
import json
from types import SimpleNamespace

import pytest

from operon.contracts import ContractError
from operon.contracts.base import sha256_hex
from operon.contracts.run_plan import EnvironmentRequirement, TargetSpec
from operon.environment_store.service import EnvironmentStore
from operon.environment_store.verification import inventory
from operon.execution.codecs import file_reference, validate_reference
from operon.execution.adapters.command import CommandInvocationAdapter, resolve_argv


def generation(tmp_path):
    """Construct an exact synthetic manifest for metadata verification only."""
    store = EnvironmentStore(tmp_path / 'store')
    requirement = EnvironmentRequirement(target=TargetSpec(os='synthetic', arch='synthetic'),
                                         runtime='fixture-v1')
    files = {}
    identity = {'requirement_digest': sha256_hex(requirement), 'content_digest': sha256_hex(files),
                'builder': {'fixture': True}, 'target': requirement.target.model_dump(mode='json')}
    key = sha256_hex(identity)
    root = store.root / 'generations' / key
    (root / 'payload').mkdir(parents=True)
    manifest = {'format': 'operon.environment-generation', 'schema_version': 1,
                'generation_id': key, 'identity': identity, 'files': files,
                'requirement_digest': sha256_hex(requirement),
                'requirement': requirement.model_dump(mode='json'), 'content_digest': sha256_hex(files)}
    receipt = {'status': 'passed', 'relocation': 'passed', 'content_digest': sha256_hex(files)}
    (root / 'manifest.json').write_text(json.dumps(manifest))
    (root / 'verification.json').write_text(json.dumps(receipt))
    return store, key, root, manifest


@pytest.mark.parametrize('field', ['requirement', 'requirement_digest', 'content_digest', 'schema_version'])
def test_generation_binding_rejects_unbound_manifest_fields(tmp_path, field):
    store, key, root, manifest = generation(tmp_path)
    assert store.binding(key).generation_id == key
    if field == 'requirement':
        manifest['requirement']['runtime'] = 'a-different-runtime'
        manifest['requirement_digest'] = sha256_hex(manifest['requirement'])
    elif field == 'requirement_digest':
        manifest['requirement_digest'] = 'f' * 64
    elif field == 'schema_version':
        manifest['schema_version'] = True
    else:
        # Matching files/receipt alone must not bypass the immutable identity.
        (root / 'payload' / 'added.txt').write_text('changed')
        manifest['files'] = inventory(root / 'payload')
        manifest['content_digest'] = sha256_hex(manifest['files'])
        (root / 'verification.json').write_text(json.dumps({
            'status': 'passed', 'relocation': 'passed', 'content_digest': manifest['content_digest']}))
    (root / 'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ContractError) as caught:
        store.binding(key)
    assert caught.value.code == 'environment_corrupt'


def test_generation_binding_requires_relocation_verification(tmp_path):
    store, key, root, manifest = generation(tmp_path)
    (root / 'verification.json').write_text(json.dumps({
        'status': 'passed', 'content_digest': manifest['content_digest']}))
    with pytest.raises(ContractError) as caught:
        store.binding(key)
    assert caught.value.code == 'environment_corrupt'


def test_form_reference_detects_attachment_changes_before_native_registration(tmp_path):
    packet = tmp_path / 'value.bpform'
    attachment = tmp_path / 'data.npy'
    # No scientific reader runs here: validate_reference is the pre-consumer gate.
    packet.write_text('{"version":1,"value":{"file":"data.npy"}}')
    attachment.write_bytes(b'original numeric payload')
    reference = file_reference(packet, representation='form', metadata={'inventory': inventory(tmp_path)})
    assert validate_reference(reference) == packet
    attachment.write_bytes(b'corrupt! numeric payload')
    with pytest.raises(ContractError) as caught:
        validate_reference(reference)
    assert caught.value.code == 'artifact_mismatch'


def test_form_reference_requires_attachment_inventory(tmp_path):
    packet = tmp_path / 'value.bpform'
    packet.write_text('{}')
    reference = file_reference(packet, representation='form')
    with pytest.raises(ContractError) as caught:
        validate_reference(reference)
    assert caught.value.code == 'artifact_mismatch'


@pytest.mark.parametrize('paths', [('same.txt', 'same.txt'), ('data', 'data/child.txt'),
                                   ('data/child.txt', 'data'), ('folder/../bad', 'other')])
def test_command_output_overlap_is_rejected_before_execution(tmp_path, paths):
    # The store is only an adapter contract fixture. No process is launched.
    binding = SimpleNamespace(model_dump=lambda **options: {})
    store = SimpleNamespace(root=tmp_path / 'store', binding=lambda key: binding)
    adapter = CommandInvocationAdapter(store, 'fixture', package_root=tmp_path)
    context = SimpleNamespace(attempt_root=tmp_path / 'attempt', payload={
        'outputs': {'one': {'path': paths[0]}, 'two': {'path': paths[1]}}})
    with pytest.raises((ContractError, ValueError)):
        adapter.prepare(SimpleNamespace(), context)
    assert not (context.attempt_root / 'invocation.json').exists()


def test_typed_argv_keys_have_machine_readable_failures():
    for token in ({'input': []}, {'input': 1}, {'unknown': 'name'}):
        with pytest.raises(ContractError) as caught:
            resolve_argv([token], inputs={}, outputs={}, parameters={}, resources={})
        assert caught.value.code == 'invalid_argument'
