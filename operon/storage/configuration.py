"""Opt-in storage roots; credentials and compute profiles are never migrated."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator

from operon.contracts.base import ContractModel
from .browsing import BrowseLimits
from .mounts import LocalStorage, MountMap, SFTPStorage
from .references import StorageError
from .ssh import SFTPConnection


# The current loopback bridge authenticates the owner of one local profile.
# Agent names are presentation and never become authorization identities.
PROFILE_OWNER = 'profile-owner'


class HostKey(ContractModel):
    type: str = Field(min_length=1, max_length=100)
    base64: str = Field(min_length=1, max_length=16384)


class SSHProfile(ContractModel):
    host: str = Field(min_length=1, max_length=253, pattern=r'^[A-Za-z0-9.:\[\]-]+$')
    port: int = Field(default=22, ge=1, le=65535)
    username: str = Field(min_length=1, max_length=128)
    auth: Literal['key', 'agent', 'password'] = 'agent'
    key_path: str = Field(default='', max_length=2048)
    host_key: HostKey | None = None
    credential_id: str | None = Field(default=None, min_length=1, max_length=160)

    @field_validator('username', 'key_path')
    @classmethod
    def no_control(cls, value):
        if any(ord(character) < 32 for character in value):
            raise ValueError('SSH configuration must not contain control characters')
        return value


class LocalMountConfig(ContractModel):
    kind: Literal['local']
    storage_id: str = Field(min_length=1, max_length=160)
    root: str = Field(min_length=1, max_length=32768)
    principals: tuple[str, ...] = Field(min_length=1, max_length=128)


class SFTPMountConfig(ContractModel):
    kind: Literal['sftp']
    storage_id: str = Field(min_length=1, max_length=160)
    root: str = Field(min_length=1, max_length=2048)
    principals: tuple[str, ...] = Field(min_length=1, max_length=128)
    ssh: SSHProfile
    jump: SSHProfile | None = None
    execution_profile_id: str | None = Field(default=None, min_length=1, max_length=120)


class StorageConfiguration(ContractModel):
    format: Literal['operon.storage-mounts'] = 'operon.storage-mounts'
    schema_version: Literal[1] = 1
    mounts: tuple[Annotated[LocalMountConfig | SFTPMountConfig, Field(discriminator='kind')], ...] = Field(default=(), max_length=128)
    limits: BrowseLimits = Field(default_factory=BrowseLimits)

    @field_validator('schema_version', mode='before')
    @classmethod
    def integer_version(cls, value):
        if type(value) is not int:
            raise ValueError('Storage schema version must be an integer')
        return value


def configured_mounts(path, *, credentials=None):
    """A missing opt-in file yields an empty map, never an implicit workspace."""
    path = Path(path)
    if not path.exists():
        return MountMap(), BrowseLimits()
    with path.open('rb') as stream:
        raw = stream.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise StorageError('Storage configuration exceeds 1 MiB', code='storage_configuration_invalid')

    def unique(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate storage configuration key')
            result[key] = value
        return result

    config = StorageConfiguration.model_validate(json.loads(raw.decode('utf-8-sig'), object_pairs_hook=unique))
    mounts, seen = MountMap(), set()

    def secret(profile):
        if profile.credential_id is None:
            if profile.auth == 'password':
                raise StorageError('Password storage requires an explicit credential provider reference',
                                   code='storage_credentials_required')
            return {}
        if credentials is None:
            raise StorageError('Storage credential provider is unavailable', code='storage_credentials_required')
        return credentials(profile.credential_id)

    for mount in config.mounts:
        if mount.storage_id in seen:
            raise StorageError('Duplicate storage ID', code='storage_configuration_invalid')
        seen.add(mount.storage_id)
        if mount.kind == 'local':
            if not Path(mount.root).is_absolute():
                raise StorageError('Local storage roots must be explicitly absolute', code='storage_configuration_invalid')
            backend = LocalStorage(mount.root)
        else:
            def connect(mount=mount):
                return SFTPConnection(mount.ssh.model_dump(mode='json', exclude={'credential_id'}), secret(mount.ssh),
                                      jump_profile=mount.jump.model_dump(mode='json', exclude={'credential_id'}) if mount.jump else None,
                                      jump_credentials=secret(mount.jump) if mount.jump else None)
            backend = SFTPStorage(mount.root, connect)
        mounts.register(mount.storage_id, backend, principals=mount.principals,
            execution_profile_id=mount.execution_profile_id if mount.kind == 'sftp' else None,
            endpoint=(mount.ssh.host, mount.ssh.port, mount.ssh.username) if mount.kind == 'sftp' else None)
    return mounts, config.limits
