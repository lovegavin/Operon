"""Deterministic, bounded estimates; host pools still decide admission."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from itertools import islice
import math
import time


@dataclass(frozen=True)
class NodeCandidate:
    node_id: str
    executor: str
    os: str
    arch: str
    python_abi: str | None = None
    health: str = 'healthy'
    capabilities: tuple[str, ...] = ()
    environments: tuple[str, ...] = ()
    devices: tuple[str, ...] = ()
    reachable_storage: tuple[str, ...] = ()
    route_affinities: tuple[str, ...] = ()
    queue_seconds: float | None = None
    compute_seconds: float | None = None
    transfer_bytes_per_second: float | None = None
    missing_bytes: int | None = None


@dataclass(frozen=True)
class UnitCandidate:
    run_id: str
    unit_id: str
    principal: str
    created_at: float
    executor: str
    os: str
    arch: str
    python_abi: str | None = None
    required_capabilities: tuple[str, ...] = ()
    required_environments: tuple[str, ...] = ()
    devices: tuple[str, ...] = ()
    required_storage: tuple[str, ...] = ()
    route_affinity: str | None = None
    explicit_node: str | None = None


@dataclass(frozen=True)
class PlacementDefaults:
    queue_seconds: float = 60.0
    compute_seconds: float = 3600.0
    transfer_bytes_per_second: float = 1024 * 1024
    missing_bytes: int = 1024 * 1024 * 1024
    max_units: int = 256
    max_candidates: int = 4
    cpu_budget_seconds: float = 0.05

    def __post_init__(self):
        if any(not math.isfinite(value) or value <= 0 for value in self.__dict__.values()):
            raise ValueError('Placement bounds and defaults must be finite and positive')
        if self.max_units > 256 or self.max_candidates > 4 or self.cpu_budget_seconds > .05:
            raise ValueError('Placement cannot exceed the initial contract bounds')


@dataclass(frozen=True)
class RankedNode:
    node_id: str
    finish_seconds: float
    missing_bytes: int
    unknown_costs: tuple[str, ...]


@dataclass(frozen=True)
class PlacementDecision:
    run_id: str
    unit_id: str
    candidates: tuple[RankedNode, ...]
    ineligible: tuple[tuple[str, tuple[str, ...]], ...]
    budget_exhausted: bool = False


def ineligible_reasons(unit: UnitCandidate, node: NodeCandidate):
    reasons = []
    if node.health != 'healthy': reasons.append('node_health')
    if (unit.os, unit.arch) != (node.os, node.arch): reasons.append('target_abi')
    if unit.python_abi and unit.python_abi != node.python_abi: reasons.append('python_abi')
    if unit.executor != node.executor: reasons.append('executor')
    if unit.explicit_node and unit.explicit_node != node.node_id: reasons.append('explicit_node')
    for required, available, label in (
        (unit.required_capabilities, node.capabilities, 'capabilities'),
        (unit.required_environments, node.environments, 'environment_unavailable'),
        (unit.devices, node.devices, 'devices'),
        (unit.required_storage, node.reachable_storage, 'storage_unreachable')):
        if not set(required) <= set(available): reasons.append(label)
    if unit.route_affinity and unit.route_affinity not in node.route_affinities:
        reasons.append('route_affinity')
    return tuple(reasons)


def rank_node(node, defaults):
    unknown = []
    def value(name):
        result = getattr(node, name)
        if result is None or not math.isfinite(result) or result < 0 or (name == 'transfer_bytes_per_second' and result == 0):
            unknown.append(name)
            return getattr(defaults, name)
        return result
    queue, compute = value('queue_seconds'), value('compute_seconds')
    missing, throughput = value('missing_bytes'), value('transfer_bytes_per_second')
    return RankedNode(node.node_id, queue + compute + missing / throughput, int(missing), tuple(unknown))


def plan_placements(units, nodes, *, defaults=PlacementDefaults(), clock=time.thread_time):
    """Caller supplies a bounded ready page; returns at most four host attempts/unit."""
    start = clock()
    # Fair rounds preserve age within each principal, with a stable total order.
    groups = {}
    for unit in islice(units, defaults.max_units):
        groups.setdefault(unit.principal, []).append(unit)
    ordered = []
    for principal in sorted(groups):
        group = sorted(groups[principal], key=lambda u: (u.created_at, u.run_id, u.unit_id))
        ordered.extend((index, unit) for index, unit in enumerate(group))
    ordered.sort(key=lambda pair: (pair[0], pair[1].created_at, pair[1].principal,
                                   pair[1].run_id, pair[1].unit_id))
    nodes = tuple(sorted(nodes, key=lambda node: node.node_id))
    decisions = []
    for _, unit in ordered:
        if clock() - start >= defaults.cpu_budget_seconds:
            break
        ranked, rejected, exhausted = [], [], False
        for node in nodes:
            if clock() - start >= defaults.cpu_budget_seconds:
                exhausted = True
                break
            reasons = ineligible_reasons(unit, node)
            if reasons:
                rejected.append((node.node_id, reasons))
            else:
                ranked.append(rank_node(node, defaults))
        ranked.sort(key=lambda item: (item.finish_seconds, item.missing_bytes, item.node_id))
        decisions.append(PlacementDecision(unit.run_id, unit.unit_id,
            tuple(ranked[:defaults.max_candidates]), tuple(rejected), exhausted))
        if exhausted:
            break
    return tuple(decisions)


def heartbeat_health(age_seconds, *, suspect_seconds=30, offline_seconds=90):
    """Observation only: never a proof that a process or allocation stopped."""
    if not 0 < suspect_seconds < offline_seconds:
        raise ValueError('Heartbeat thresholds must be ordered and positive')
    if age_seconds >= offline_seconds: return 'offline'
    if age_seconds >= suspect_seconds: return 'suspect'
    return 'healthy'


@dataclass(frozen=True)
class PreparedBinding:
    """Materialization is already complete; this immutable value contains no I/O."""
    payload_json: str
    binding_id: str | None = None


class PlacementPlanner:
    """Repository-row adapter for the bounded greedy planner.

    ``prepared`` maps (run, unit, node) to verified, pre-staged payloads.
    Missing materialization is explicit ineligibility; the scheduler never
    installs an environment or transfers files while planning.
    """

    def __init__(self, *, controller_id, prepared, prepared_templates=None, defaults=PlacementDefaults()):
        self.controller_id, self.prepared, self.defaults = controller_id, prepared, defaults
        self.prepared_templates = prepared_templates or {}
        self.last_decisions = ()

    def __call__(self, ready, node_rows):
        now = datetime.now(timezone.utc)
        nodes = []
        for row in node_rows:
            inventory = row['inventory']
            health = row['health']
            if health == 'healthy':
                age = (now - row['heartbeat_at']).total_seconds() if row['heartbeat_at'] else float('inf')
                health = heartbeat_health(age)
            nodes.append(NodeCandidate(node_id=row['node_id'], executor=row['executor'],
                os=inventory['os'], arch=inventory['arch'], python_abi=inventory.get('python_abi'), health=health,
                capabilities=tuple(inventory.get('capabilities', ())), environments=tuple(inventory.get('environments', ())),
                devices=tuple(inventory.get('devices', ())), reachable_storage=tuple(inventory.get('reachable_storage', ())),
                route_affinities=tuple(inventory.get('route_affinities', ())),
                queue_seconds=inventory.get('queue_seconds'), compute_seconds=inventory.get('compute_seconds'),
                transfer_bytes_per_second=inventory.get('transfer_bytes_per_second'), missing_bytes=inventory.get('missing_bytes')))
        units, rows = [], {}
        for row in ready[:self.defaults.max_units]:
            spec = row['spec']
            policy = spec['placement']
            target = policy['target']
            environment = spec['invocation'].get('environment_ref')
            candidate = UnitCandidate(run_id=row['run_id'], unit_id=row['unit_id'], principal=row['principal'],
                created_at=row['created_at'].timestamp(), executor=policy['executor'], os=target['os'], arch=target['arch'],
                python_abi=target.get('python_abi'), required_capabilities=tuple(target.get('capabilities', ())),
                required_environments=(environment,) if environment else (), devices=tuple(spec['resource_request'].get('devices', ())),
                required_storage=tuple(policy.get('storage_affinity', ())), explicit_node=policy.get('node_id'))
            units.append(candidate)
            rows[(row['run_id'], row['unit_id'])] = row
        decisions = plan_placements(units, nodes, defaults=self.defaults)
        self.last_decisions = decisions
        for decision in decisions:
            row = rows[(decision.run_id, decision.unit_id)]
            # No external call here. Only a committed, prepared candidate can be dispatched.
            for candidate in decision.candidates:
                binding = self.prepared.get((decision.run_id, decision.unit_id, candidate.node_id))
                if binding is None:
                    binding = self.prepared_templates.get((row.get('plan_id'), decision.unit_id, candidate.node_id))
                if binding is None:
                    continue
                yield {'run_id': decision.run_id, 'unit_id': decision.unit_id, 'node_id': candidate.node_id,
                       'executor': row['spec']['placement']['executor'], 'controller_id': self.controller_id,
                       'expected_revision': row['revision'], 'payload': json.loads(binding.payload_json),
                       'binding_id': binding.binding_id}
                break
