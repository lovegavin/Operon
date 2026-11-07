"""Pure scheduling policy: deterministic, explainable and replayable.

Nothing in this module touches a database, process or socket.  Given the same
durable event sequence and pool snapshot, the functions return the same
decision.  The coordinator persists the inputs that led to a decision so a
support report can explain a queue instead of guessing.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from .contracts import InfeasibleResourcesError, ResourceRequest


@dataclass(frozen=True)
class FairnessPolicy:
    """Weights and bounds of the initial fair policy.

    ``principal_weight`` is intentionally not derived from the number of client
    connections.  Ten windows under one principal remain one share.  Project
    quotas inherit the authenticated principal's aggregate quota: creating a
    new project name cannot manufacture capacity or scheduling weight.
    """

    principal_weight: float = 1.0
    max_principal_share: float = 0.75
    protect_after_seconds: float = 30.0
    large_job_fraction: float = 0.35
    max_candidates: int = 64
    scan_limit: int = 256

    def __post_init__(self):
        if self.principal_weight <= 0 or not math.isfinite(self.principal_weight):
            raise ValueError('principal_weight must be positive')
        if not 0 < self.max_principal_share <= 1:
            raise ValueError('max_principal_share must be in (0, 1]')
        if self.protect_after_seconds < 0:
            raise ValueError('protect_after_seconds must be non-negative')
        if not 0 <= self.large_job_fraction <= 1:
            raise ValueError('large_job_fraction must be in [0, 1]')
        if self.max_candidates < 1 or self.scan_limit < self.max_candidates:
            raise ValueError('invalid candidate bounds')


@dataclass(frozen=True)
class Demand:
    """One ready unit offered to the policy."""

    key: str
    principal: str
    project: str
    requirement: ResourceRequest
    age_seconds: float = 0.0
    weight: float = 1.0
    submitted_at: float = 0.0
    run_id: str | None = None
    unit_id: str | None = None
    retry: int = 0

    @property
    def ram(self) -> int:
        return self.requirement.ram_bytes

    @property
    def cpu(self) -> int:
        return self.requirement.cpu_threads


@dataclass(frozen=True)
class Usage:
    ram: int = 0
    cpu: int = 0
    scratch: int = 0


@dataclass(frozen=True)
class Selection:
    chosen: tuple[Demand, ...]
    deferred: tuple[dict, ...] = ()
    infeasible: tuple[dict, ...] = ()
    reservation: dict | None = None
    explanation: str = ''

    @property
    def keys(self) -> tuple[str, ...]:
        return tuple(item.key for item in self.chosen)


def _usage_key(usage: Usage, weight: float, capacity: int) -> float:
    if capacity <= 0:
        return float('inf')
    return usage.ram / (weight * capacity)


def water_fill(allocations: list[dict], available: int) -> dict[str, int]:
    """Weighted water filling between minimum and preferred grants.

    ``allocations`` items require ``key``, ``minimum``, ``preferred`` and may
    carry ``weight``.  Every minimum must fit or the result is infeasible.
    Surplus is shared by weight without exceeding a preferred bound.  Bytes are
    integers; remainder distribution is deterministic by input order.
    """
    if isinstance(available, bool) or not isinstance(available, int) or available < 0:
        raise ValueError('available must be a non-negative integer')
    prepared = []
    for index, item in enumerate(allocations):
        minimum = int(item.get('minimum', 0))
        preferred = int(item.get('preferred', minimum))
        weight = float(item.get('weight', 1.0))
        if minimum < 0 or preferred < minimum or weight <= 0 or not math.isfinite(weight):
            raise ValueError('invalid allocation bounds')
        prepared.append({'key': item['key'], 'minimum': minimum, 'preferred': preferred,
                         'weight': weight, 'index': index, 'value': minimum})
    required = sum(value['minimum'] for value in prepared)
    if required > available:
        raise InfeasibleResourcesError(
            'The minimum grants exceed the available capacity',
            details={'required_bytes': required, 'available_bytes': available,
                     'shortfall_bytes': required - available})
    remaining = available - required
    while remaining > 0:
        active = [item for item in prepared if item['value'] < item['preferred']]
        if not active:
            break
        total_weight = sum(item['weight'] for item in active)
        progressed = False
        shares = []
        for item in active:
            share = int(math.floor(remaining * item['weight'] / total_weight))
            share = min(share, item['preferred'] - item['value'])
            shares.append((item, share))
        for item, share in shares:
            if share:
                item['value'] += share
                remaining -= share
                progressed = True
        if remaining <= 0:
            break
        if not progressed:
            # Every active item reached its preferred bound in the previous
            # pass; give the remaining bytes to the first item that can use
            # them, preserving deterministic input order.
            for item in active:
                capacity = item['preferred'] - item['value']
                take = min(capacity, remaining)
                if take:
                    item['value'] += take
                    remaining -= take
                if remaining <= 0:
                    break
    return {item['key']: item['value'] for item in prepared}


def select_ready(demands: list[Demand], *, capacity: int, free: Usage, usage: dict[str, Usage],
                 policy: FairnessPolicy | None = None, limit: int | None = None,
                 cpu_capacity: int | None = None) -> Selection:
    """Choose a bounded set of ready units without exponential search.

    ``capacity`` is the schedulable RAM ceiling; ``free`` is the currently
    uncommitted amount.  ``usage`` is committed RAM/CPU per principal, used for
    weighted fairness, never as a measurement of actual use.
    """
    policy = policy or FairnessPolicy()
    if capacity < 0 or free.ram < 0 or free.cpu < 0:
        raise ValueError('invalid pool accounting')
    bound = min(policy.max_candidates, int(limit or policy.max_candidates))
    ordered = sorted(demands, key=lambda item: (item.submitted_at or 0, item.key))[:policy.scan_limit]
    infeasible, feasible = [], []
    for item in ordered:
        if item.ram > capacity or (cpu_capacity is not None and item.cpu > cpu_capacity):
            infeasible.append({'key': item.key, 'run_id': item.run_id,
                               'reason': 'infeasible_resources',
                               'message': 'The minimum grant exceeds the frozen pool ceiling'})
            continue
        feasible.append(item)

    def effective(item: Demand) -> float:
        current = usage.get(item.principal, Usage())
        return _usage_key(current, max(1e-9, item.weight * policy.principal_weight), capacity)

    feasible.sort(key=lambda item: (effective(item), -item.age_seconds, item.submitted_at, item.key))

    candidates = [item for item in feasible if item.ram >= policy.large_job_fraction * capacity]
    reservation = None
    if candidates:
        protected = max(candidates, key=lambda item: (item.age_seconds, -item.submitted_at, item.key))
        if protected.age_seconds >= policy.protect_after_seconds and protected.ram > free.ram:
            reservation = {'run_id': protected.run_id, 'unit_id': protected.unit_id,
                           'key': protected.key, 'principal': protected.principal,
                           'required_bytes': protected.ram, 'free_bytes': free.ram,
                           'reason': 'protect_aged_large_job'}

    chosen, deferred = [], []
    simulated = Usage(ram=free.ram, cpu=free.cpu, scratch=free.scratch)
    simulated_usage = {key: Usage(ram=value.ram, cpu=value.cpu, scratch=value.scratch)
                       for key, value in usage.items()}
    other_principals_waiting = len({item.principal for item in feasible}) > 1
    for item in feasible:
        if len(chosen) >= bound:
            deferred.append({'key': item.key, 'run_id': item.run_id, 'reason': 'bounded_candidate_scan'})
            continue
        if reservation and item.key != reservation['key']:
            if simulated.ram - item.ram < reservation['required_bytes']:
                deferred.append({'key': item.key, 'run_id': item.run_id,
                                 'reason': 'protected_reservation',
                                 'message': 'Capacity is accumulating for an aged feasible job'})
                continue
        if item.ram > simulated.ram or item.cpu > simulated.cpu:
            deferred.append({'key': item.key, 'run_id': item.run_id,
                             'reason': 'waiting_for_resources'})
            continue
        principal = simulated_usage.get(item.principal, Usage())
        if (item.principal in simulated_usage and other_principals_waiting and
                principal.ram + item.ram > policy.max_principal_share * capacity):
            deferred.append({'key': item.key, 'run_id': item.run_id,
                             'reason': 'principal_quota',
                             'message': "One principal cannot exceed its aggregate share while others wait"})
            continue
        chosen.append(item)
        simulated = Usage(ram=simulated.ram - item.ram, cpu=simulated.cpu - item.cpu,
                          scratch=max(0, simulated.scratch - item.requirement.scratch_reserved_bytes))
        simulated_usage[item.principal] = Usage(
            ram=principal.ram + item.ram, cpu=principal.cpu + item.cpu,
            scratch=principal.scratch + item.requirement.scratch_reserved_bytes)
    explanation = 'selected %d of %d ready units; %d deferred; %d infeasible%s' % (
        len(chosen), len(ordered), len(deferred), len(infeasible),
        '; reserving for ' + str(reservation['key']) if reservation else '')
    return Selection(chosen=tuple(chosen), deferred=tuple(deferred), infeasible=tuple(infeasible),
                     reservation=reservation, explanation=explanation)


def aggregate(assignments: list[dict]) -> dict[str, Usage]:
    result: dict[str, Usage] = {}
    for item in assignments:
        principal = item['principal']
        current = result.get(principal, Usage())
        result[principal] = Usage(ram=current.ram + int(item.get('ram', 0)),
                                  cpu=current.cpu + int(item.get('cpu', 0)),
                                  scratch=current.scratch + int(item.get('scratch', 0)))
    return result


def normalize_weights(principals: dict[str, float]) -> dict[str, float]:
    total = sum(max(0.0, value) for value in principals.values())
    if total <= 0:
        return {key: 1.0 for key in principals}
    return {key: max(0.0, value) / total for key, value in principals.items()}
