"""Schema reuse must never cache parameter values or accept a changed contract."""
from copy import deepcopy

import pytest

from operon_sdk import protocol


@pytest.fixture(autouse=True)
def clear_schema_cache():
    protocol._validate_schema_text.cache_clear()
    yield
    protocol._validate_schema_text.cache_clear()


def test_repeated_schema_checks_reuse_content_but_every_value_is_validated(monkeypatch):
    calls = []
    original = protocol._validate_schema_uncached
    def checked(schema):
        calls.append(deepcopy(schema))
        return original(schema)
    monkeypatch.setattr(protocol, '_validate_schema_uncached', checked)
    schema = {'type': 'object', 'properties': {'n': {'type': 'integer', 'default': 2}}}
    assert protocol.validate_parameters(schema, {}) == {'n': 2}
    assert protocol.validate_parameters(deepcopy(schema), {'n': 3}) == {'n': 3}
    with pytest.raises(ValueError):
        protocol.validate_parameters(schema, {'n': 'invalid'})
    assert len(calls) == 1
    schema['properties']['n']['default'] = 4
    assert protocol.validate_parameters(schema, {}) == {'n': 4}
    assert len(calls) == 2


def test_cached_defaults_are_copied_and_remote_references_still_rejected():
    schema = {'type': 'object', 'properties': {'x': {'type': 'array', 'default': [1]}}}
    first = protocol.validate_parameters(schema, {})
    first['x'].append(2)
    assert protocol.validate_parameters(schema, {}) == {'x': [1]}
    schema['properties']['x']['$ref'] = 'https://example.invalid/schema.json'
    for _ in range(2):
        with pytest.raises(ValueError, match='Only local'):
            protocol.validate_parameters(schema, {})
    assert protocol._validate_schema_text.cache_info().currsize == 1


def test_cache_is_bounded_and_oversized_schema_is_checked_without_retention(monkeypatch):
    # The existing public validator checks this large document on every call;
    # the cache is an optimization, never a reason to skip validation.
    calls = []
    original = protocol._validate_schema_uncached
    def checked(schema):
        calls.append(True)
        return original(schema)
    monkeypatch.setattr(protocol, '_validate_schema_uncached', checked)
    large = {'type': 'object', 'description': 'x' * 65536}
    protocol.validate_schema(large)
    protocol.validate_schema(large)
    assert len(calls) == 2
    assert protocol._validate_schema_text.cache_info().currsize == 0
    for i in range(140):
        protocol.validate_schema({'type': 'object', 'title': str(i)})
    assert protocol._validate_schema_text.cache_info().currsize == 128
