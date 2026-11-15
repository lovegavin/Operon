"""Public storage reference aliases."""
from .run_plan import ArtifactRef, StorageBinding, StorageRef
from typing import Literal
from pydantic import Field, field_validator
from urllib.parse import quote


class StorageInputRef(StorageRef):
    """Versioned saved source selection; it grants no filesystem permission."""
    format: Literal['operon.storage-input'] = 'operon.storage-input'
    schema_version: Literal[1] = 1
    version: str = Field(min_length=1, max_length=256)

    @field_validator('schema_version', mode='before')
    @classmethod
    def integer_version(cls, value):
        if type(value) is not int:
            raise ValueError('Storage input schema version must be an integer')
        return value

    @field_validator('relative_path')
    @classmethod
    def portable_path(cls, value):
        from pathlib import PurePosixPath
        if ':' in value or value != PurePosixPath(value.replace('\\', '/')).as_posix() or value == '.':
            raise ValueError('A storage input needs a normalized relative file path')
        return value


def storage_input_path(value):
    """Display/plan URI, never an absolute execution path or read grant."""
    return 'storage://' + quote(value.storage_id, safe='') + '/' + quote(value.relative_path, safe='/')

__all__ = ['ArtifactRef', 'StorageBinding', 'StorageRef', 'StorageInputRef', 'storage_input_path']
