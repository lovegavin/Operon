"""Canonical data and strict wire-contract primitives.

This module deliberately has no dependency on the web layer, the scientific
operator packages or an execution backend.  It is safe to import while planning,
in a worker, or from a foreign-language adapter that consumes the canonical
bytes.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any, Iterable, Mapping, get_origin

from pydantic import BaseModel, ConfigDict, model_validator


class FrozenJSONDict(dict):
    """JSON mapping with immutable public access and mutable explicit copies."""

    def _deny(self, *args, **kwargs):
        raise TypeError('Contract values are immutable; create a validated copy')

    __setitem__ = __delitem__ = clear = pop = popitem = setdefault = update = __ior__ = _deny

    def __deepcopy__(self, memo):
        return {key: deepcopy(value, memo) for key, value in self.items()}


def _freeze(value):
    if isinstance(value, dict):
        return FrozenJSONDict({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


CANONICAL_JSON = 'operon-canonical-json-v1'
CANONICAL_DOMAIN = 'operon:canonical-json:v1'


class ContractError(ValueError):
    """A stable, machine-readable contract failure."""

    code = 'invalid_contract'
    status = 422

    def __init__(self, message: str, *, code: str | None = None, details: Mapping[str, Any] | None = None,
                 next_actions: Iterable[Mapping[str, Any]] | None = None):
        super().__init__(message)
        if code:
            self.code = code
        self.details = dict(details or {})
        self.next_actions = tuple(dict(item) for item in (next_actions or ()))

    def to_json(self) -> dict:
        value = {'code': self.code, 'message': str(self),
                 'details': deepcopy(self.details), 'next_actions': list(self.next_actions)}
        return value


class ContractModel(BaseModel):
    """Strict, frozen public record.

    Container fields accept their JSON list spelling without scalar coercion.
    Nested JSON mappings and sequences are frozen; model_dump(mode='json') is
    the explicit mutable wire representation. This is an API invariant, not an
    in-process security boundary against Python introspection.
    """

    model_config = ConfigDict(extra='forbid', strict=True, frozen=True,
                              validate_assignment=True, revalidate_instances='always')

    @model_validator(mode='before')
    @classmethod
    def _json_sequences(cls, value):
        if isinstance(value, Mapping):
            value = dict(value)
            assert_json_value(value)
            for name, field in cls.model_fields.items():
                if get_origin(field.annotation) is tuple and isinstance(value.get(name), list):
                    value[name] = tuple(value[name])
        return value

    @model_validator(mode='after')
    def _immutable_containers(self):
        for name in type(self).model_fields:
            object.__setattr__(self, name, _freeze(getattr(self, name)))
        return self

    def model_copy(self, *, update=None, deep=False):
        value = self.model_dump(mode='json')
        value.update(update or {})
        return type(self).model_validate(value)


def _plain(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode='json')
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise ContractError('JSON object keys must be strings', code='non_canonical_value')
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def canonical_json(value: Any) -> str:
    """The single canonical JSON spelling used by every identity hash.

    Keys are sorted, there is no insignificant whitespace, non-ASCII text is
    retained, and NaN/Infinity are rejected.  The function is stable across
    the Python versions covered by the frozen vectors. Other languages consume
    these bytes instead of implementing their own float serialization.
    """
    try:
        return json.dumps(_plain(value), sort_keys=True, separators=(',', ':'),
                          ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ContractError(f'Value is not canonical-JSON encodable: {exc}',
                            code='non_canonical_value') from exc


def canonical_bytes(value: Any) -> bytes:
    return canonical_json(value).encode('utf-8')


def sha256_hex(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def domain_digest(domain: str, value: Any) -> str:
    """Domain-separated SHA-256 of canonical bytes.

    Domains are literal ASCII namespaces such as ``operon:run-plan:v1``; adding
    a new record type must not silently reuse another record's hash.
    """
    if not isinstance(domain, str) or not domain or any(character not in
            'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789:._-/'
            for character in domain):
        raise ContractError('A canonical hash domain must be a printable ASCII name',
                            code='invalid_hash_domain')
    return hashlib.sha256(domain.encode('ascii') + b'\0' + canonical_bytes(value)).hexdigest()


def assert_json_value(value: Any) -> None:
    """Reject NaN/Infinity and non-JSON Python values at a public boundary."""
    canonical_json(value)
