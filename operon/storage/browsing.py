"""Strict browse requests and bounded immutable results."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import Field, field_validator, model_validator

from operon.contracts.base import ContractModel
from .references import StorageEntry, relative_path as normalize_relative_path


class BrowseRequest(ContractModel):
    storage_id: str = Field(min_length=1, max_length=160)
    relative_path: str = Field(default='.', max_length=2048)
    cursor: str | None = Field(default=None, min_length=1, max_length=256)
    page_size: int | None = Field(default=None, ge=1, le=1000)
    hidden: bool = False
    order: Literal['filesystem'] = 'filesystem'

    _path = field_validator('relative_path')(normalize_relative_path)


class PreviewRequest(ContractModel):
    storage_id: str = Field(min_length=1, max_length=160)
    relative_path: str = Field(min_length=1, max_length=2048)
    byte_limit: int | None = Field(default=None, ge=1, le=1024 * 1024)
    row_limit: int | None = Field(default=None, ge=1, le=10000)

    _path = field_validator('relative_path')(normalize_relative_path)


class BrowseLimits(ContractModel):
    default_page_size: int = Field(default=200, ge=1, le=1000)
    max_page_size: int = Field(default=1000, ge=1, le=1000)
    max_scan_entries: int = Field(default=1000, ge=1, le=10000)
    page_work_seconds: int = Field(default=2, ge=1)
    cursor_idle_seconds: int = Field(default=30, ge=1)
    max_handles: int = Field(default=64, ge=1)
    handles_per_principal: int = Field(default=2, ge=1)
    io_slots: int = Field(default=8, ge=1)
    io_slots_per_principal: int = Field(default=2, ge=1)
    lifecycle_slots: int = Field(default=2, ge=1)
    default_preview_bytes: int = Field(default=64 * 1024, ge=1, le=1024 * 1024)
    max_preview_bytes: int = Field(default=1024 * 1024, ge=1, le=1024 * 1024)
    default_preview_rows: int = Field(default=100, ge=1, le=10000)
    max_preview_rows: int = Field(default=10000, ge=1, le=10000)

    @model_validator(mode='after')
    def _defaults_fit(self):
        for default, maximum in ((self.default_page_size, self.max_page_size),
                                 (self.default_preview_bytes, self.max_preview_bytes),
                                 (self.default_preview_rows, self.max_preview_rows)):
            if default > maximum:
                raise ValueError('Default storage limits must not exceed their maxima')
        return self


@dataclass(frozen=True)
class BrowsePage:
    entries: tuple[StorageEntry, ...]
    next_cursor: str | None
    listing_revision: str
    complete: bool
    order: Literal['filesystem'] = 'filesystem'
    scanned: int = 0


@dataclass(frozen=True)
class Preview:
    entry: StorageEntry
    text: str
    bytes_read: int
    rows: int
    truncated: bool
    encoding: Literal['utf-8'] = 'utf-8'
    decoding_errors: bool = False
