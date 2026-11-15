"""Small immutable records crossing the cluster/executor boundary."""
from __future__ import annotations

from dataclasses import dataclass
import json

from operon.engine.contracts import EngineError


class ClusterError(EngineError):
    code = 'cluster_unavailable'
    status = 503


class LeadershipLost(ClusterError):
    code = 'controller_leadership_lost'


@dataclass(frozen=True)
class Dispatch:
    command_id: str
    attempt_id: str
    run_id: str
    unit_id: str
    node_id: str
    executor: str
    request_key: str
    principal: str
    controller_id: str
    controller_epoch: int
    payload_json: str
    external_handle: str | None = None
    host_fence: int | None = None
    phase: str = 'pending'

    @property
    def payload(self) -> dict:
        # Copies, never a mutable mapping inside a frozen record.
        return json.loads(self.payload_json)


@dataclass(frozen=True)
class Observation:
    state: str
    phase: str
    external_handle: str | None = None
    host_fence: int | None = None
    evidence_json: str = '{}'
    # A rejection proves no host acceptance occurred; it is not a task retry.
    admission_rejected: bool = False
    stop_confirmed: bool = False

    @property
    def evidence(self) -> dict:
        return json.loads(self.evidence_json)


@dataclass(frozen=True)
class AdmissionLimits:
    runs: int = 128
    units: int = 32768
    plan_bytes: int = 64 * 1024 * 1024
    preparations: int = 16
    retained_requests: int = 100000

    def __post_init__(self):
        if any(type(v) is not int or v <= 0 for v in self.__dict__.values()):
            raise ValueError('Admission limits must be positive integers')
