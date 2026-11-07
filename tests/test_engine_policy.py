"""Pure fair policy: weights, ageing, protected reservation and determinism."""
import random

import pytest

from biopipe.engine.contracts import ResourceRequest
from biopipe.engine.policy import FairnessPolicy, Demand, Usage, select_ready, water_fill


def demand(key, principal='alice', project='p', ram=10, cpu=1, age=0.0, submitted=None):
    return Demand(key=key, principal=principal, project=project,
                  requirement=ResourceRequest(managed_budget_bytes=ram, process_reservation_bytes=ram,
                                              cpu_threads=cpu),
                  age_seconds=age, submitted_at=age if submitted is None else submitted,
                  run_id='run-' + key, unit_id='unit-' + key)


def test_opening_ten_connections_does_not_create_ten_shares():
    demands = [demand(f'a{i}', principal='alice', ram=10) for i in range(10)]
    demands.append(demand('b', principal='bob', ram=10))
    selection = select_ready(demands, capacity=100, free=Usage(ram=100, cpu=10),
                             usage={'alice': Usage(ram=70, cpu=1), 'bob': Usage()},
                             policy=FairnessPolicy(max_principal_share=0.75))
    assert 'b' in selection.keys
    assert sum(item.ram for item in selection.chosen if item.principal == 'alice') <= 10
    assert any(item['reason'] == 'principal_quota' for item in selection.deferred)


def test_aged_feasible_large_job_protects_capacity_and_blocks_competitors():
    demands = [demand('large', ram=30, age=45), demand('small1', ram=5, age=1),
               demand('small2', ram=5, age=2)]
    selection = select_ready(demands, capacity=100, free=Usage(ram=10, cpu=4), usage={},
                             policy=FairnessPolicy(protect_after_seconds=30,
                                                   large_job_fraction=0.2))
    assert selection.reservation and selection.reservation['run_id'] == 'run-large'
    assert 'large' not in selection.keys
    assert selection.keys == ()
    assert {item['reason'] for item in selection.deferred} >= {'protected_reservation'}
    # Once enough capacity accumulates, the protected job is selected first.
    ready = select_ready(demands, capacity=100, free=Usage(ram=35, cpu=4), usage={},
                         policy=FairnessPolicy(protect_after_seconds=30,
                                               large_job_fraction=0.2))
    assert ready.keys[0] == 'large'


def test_infeasible_job_is_rejected_without_head_blocking_the_queue():
    demands = [demand('huge', ram=500), demand('small', ram=5)]
    selection = select_ready(demands, capacity=100, free=Usage(ram=100, cpu=4), usage={})
    assert selection.keys == ('small',)
    assert selection.infeasible and selection.infeasible[0]['key'] == 'huge'


def test_decisions_are_deterministic_under_a_recorded_event_sequence():
    demands = [demand(f'x{i}', principal='alice' if i % 2 else 'bob', ram=5,
                      age=float(i)) for i in range(20)]
    first = select_ready(demands, capacity=64, free=Usage(ram=64, cpu=8), usage={})
    shuffled = list(demands)
    random.Random(7).shuffle(shuffled)
    second = select_ready(shuffled, capacity=64, free=Usage(ram=64, cpu=8), usage={})
    assert first.keys == second.keys


def test_candidate_scan_is_bounded():
    demands = [demand(f'x{i}', ram=1, age=float(i)) for i in range(500)]
    selection = select_ready(demands, capacity=1000, free=Usage(ram=1000, cpu=8),
                             usage={}, policy=FairnessPolicy(max_candidates=3))
    assert len(selection.chosen) <= 3


def test_older_equal_share_candidate_is_admitted_first():
    demands = [demand('old', principal='alice', age=50), demand('new', principal='bob', age=0)]
    selection = select_ready(demands, capacity=100, free=Usage(ram=10, cpu=2), usage={})
    assert selection.keys == ('old',)


def test_water_fill_respects_weights_and_caps():
    result = water_fill([
        {'key': 'a', 'minimum': 10, 'preferred': 40, 'weight': 3},
        {'key': 'b', 'minimum': 10, 'preferred': 40, 'weight': 1},
    ], 70)
    assert result['a'] + result['b'] == 70
    assert result['a'] > result['b']
    assert result['a'] <= 40 and result['b'] <= 40
