"""Workspace-scoped desktop plan receipts, never execution authority."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from fastapi import Request
from pydantic import Field, model_validator

from .bytecode import io_path
from .contracts.base import ContractError, ContractModel
from .contracts.plan_operations import PlanSubmitRequest
from .contracts.plan_export import PlanExportRequest
from .engine.fs import FileLock, atomic_json


class PlanUiRecord(ContractModel):
    title: str = Field(min_length=1, max_length=200)
    created_at: str = Field(min_length=1, max_length=60)
    submission: PlanSubmitRequest
    run_id: str | None = Field(default=None, max_length=200, pattern=r'^[A-Za-z0-9_.:-]+$')
    status: Literal['pending', 'unknown', 'accepted', 'rejected'] = 'pending'


class PlanUiExport(ContractModel):
    request: PlanExportRequest
    export_id: str | None = Field(default=None, max_length=200)


class PlanUiState(ContractModel):
    version: Literal[1] = 1
    revision: int = Field(default=0, ge=0)
    records: tuple[PlanUiRecord, ...] = Field(default=(), max_length=20)
    exports: tuple[PlanUiExport, ...] = Field(default=(), max_length=20)

    @model_validator(mode='after')
    def unique_keys(self):
        for items in ([item.submission.request_id for item in self.records],
                      [item.request.request_id for item in self.exports]):
            if len(items) != len(set(items)):
                raise ValueError('Duplicate plan UI request IDs')
        return self


class PlanUiStore:
    max_bytes = 4 * 1024 * 1024

    def __init__(self, directory, workspace):
        key = hashlib.sha256(str(Path(workspace).resolve()).encode()).hexdigest()
        self.path = Path(directory) / 'plan-ui' / (key + '.json')
        self.lock = FileLock(self.path.with_suffix('.lock'))

    def _read(self):
        path = io_path(self.path)
        if not path.exists():
            return PlanUiState()
        if path.stat().st_size > self.max_bytes:
            raise ContractError('Plan history exceeds the desktop receipt limit', code='plan_ui_capacity')
        return PlanUiState.model_validate(json.loads(path.read_text(encoding='utf-8')))

    def read(self):
        with self.lock:
            return self._read()

    def write(self, value):
        value = PlanUiState.model_validate(value)
        with self.lock:
            previous = self._read()
            if previous.revision != value.revision:
                error = ContractError('Plan history changed in another client; reload before editing',
                                      code='plan_ui_conflict', details={'revision': previous.revision})
                error.status = 409
                raise error
            current = {item.submission.request_id: item for item in value.records}
            for old in previous.records:
                new = current.get(old.submission.request_id)
                if new is None and old.status in ('pending', 'unknown'):
                    raise ContractError('Unresolved submissions must be retained', code='plan_ui_unresolved')
                if new and old.submission != new.submission:
                    raise ContractError('A request ID cannot change its frozen submission', code='idempotency_conflict')
            exports = {item.request.request_id: item for item in value.exports}
            for old in previous.exports:
                new = exports.get(old.request.request_id)
                if new is None or new.request != old.request:
                    raise ContractError('Export receipts must retain their original request', code='idempotency_conflict')
            result = value.model_copy(update={'revision': value.revision + 1})
            data = result.model_dump(mode='json')
            if len(json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')) > self.max_bytes:
                raise ContractError('Plan history is full; no request was submitted', code='plan_ui_capacity')
            atomic_json(self.path, data)
            return result


def mount_plan_ui_state(app, application, bridge):
    store = PlanUiStore(application.service.directory, application.service.root)

    @app.get('/api/v1/plan-ui-state')
    def read_state(request: Request):
        bridge.actor(request, 'context')
        return store.read()

    @app.post('/api/v1/plan-ui-state')
    def write_state(request: Request, payload: PlanUiState):
        bridge.actor(request, 'edit')
        return store.write(payload)
