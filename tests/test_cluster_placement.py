from dataclasses import replace
import threading

import pytest

from operon.cluster.placement import (NodeCandidate, UnitCandidate, PlacementDefaults,
    heartbeat_health, ineligible_reasons, plan_placements)
from operon.cluster.service import BoundedExecutor
from operon.engine.contracts import BusyError


def unit(**kwargs):
    return UnitCandidate(run_id='run', unit_id='unit', principal='alice', created_at=1,
                         executor='ssh', os='linux', arch='x86_64', **kwargs)


def node(name='host', **kwargs):
    return NodeCandidate(node_id=name, executor='ssh', os='linux', arch='x86_64', **kwargs)


def test_explicit_eligibility_filters_and_conservative_unknowns():
    candidate = unit(required_capabilities=('native',), required_environments=('generation',),
                     required_storage=('storage',), devices=('gpu0',), route_affinity='route')
    reasons = ineligible_reasons(candidate, node())
    assert reasons == ('capabilities', 'environment_unavailable', 'devices', 'storage_unreachable', 'route_affinity')
    decision, = plan_placements([unit()], [node('z'), node('a')])
    assert [choice.node_id for choice in decision.candidates] == ['a', 'z']
    assert set(decision.candidates[0].unknown_costs) == {
        'queue_seconds', 'compute_seconds', 'missing_bytes', 'transfer_bytes_per_second'}


def test_placement_fairness_and_bounds():
    units = [replace(unit(), unit_id=str(index)) for index in range(300)]
    units[1] = replace(units[1], principal='bob', created_at=2)
    decisions = plan_placements(units, [node(str(i)) for i in range(10)], clock=lambda: 0)
    assert len(decisions) == 256
    assert decisions[0].unit_id == '0' and decisions[1].unit_id == '1'
    assert all(len(item.candidates) == 4 for item in decisions)


def test_budget_stops_planning_without_network_or_truncating_units():
    times = iter((0, .001, .002, .051))
    decisions = plan_placements([unit()], [node('a'), node('b')], clock=lambda: next(times))
    assert decisions[0].budget_exhausted
    assert len(decisions[0].candidates) == 1
    assert heartbeat_health(91) == 'offline'  # Only observation; no terminal attempt state.


def test_executor_applies_backpressure_before_queueing_and_reserves_lifecycle():
    executor = BoundedExecutor({'ordinary': 1, 'lifecycle': 1}, name='test-cluster')
    release, entered = threading.Event(), threading.Event()
    def hold():
        entered.set()
        release.wait(5)
    try:
        first = executor.submit('ordinary', hold)
        assert entered.wait(2)
        with pytest.raises(BusyError): executor.submit('ordinary', lambda: None)
        assert executor.submit('lifecycle', lambda: 'cancel').result(timeout=2) == 'cancel'
        release.set()
        first.result(timeout=2)
    finally:
        release.set()
        executor.close()


def test_configuration_rejects_unbounded_or_invalid_limits():
    with pytest.raises(ValueError): PlacementDefaults(max_candidates=5)
    with pytest.raises(ValueError): PlacementDefaults(cpu_budget_seconds=.1)
    with pytest.raises(ValueError): PlacementDefaults(queue_seconds=float('nan'))
