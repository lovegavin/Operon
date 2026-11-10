"""DAG helpers: topology validation, independent chain splitting and estimates.

Splitting is opt-in.  A chain stops at a branch (one producer with several
consumers), at a merge (several producers feeding one node), and at a target
change.  This avoids duplicating interpreter/input overhead for ordinary linear
pipelines while allowing genuinely independent branches to overlap.
"""
from __future__ import annotations

from dataclasses import dataclass

from .contracts import UnitPlan


class DagError(ValueError):
    pass


def topology(nodes: list[str], edges: list[tuple[str, str]]) -> tuple[dict, dict, list[str]]:
    incoming = {node: [] for node in nodes}
    outgoing = {node: [] for node in nodes}
    for source, target in edges:
        if source not in incoming or target not in incoming:
            raise DagError(f'Edge references a missing node: {source} -> {target}')
        incoming[target].append(source)
        outgoing[source].append(target)
    ready = sorted(node for node in nodes if not incoming[node])
    order, degree = [], {node: len(incoming[node]) for node in nodes}
    while ready:
        node = ready.pop(0)
        order.append(node)
        for child in outgoing[node]:
            degree[child] -= 1
            if degree[child] == 0:
                ready.append(child)
                ready.sort()
    if len(order) != len(nodes):
        raise DagError('Workflow contains a cycle')
    return incoming, outgoing, order


def split_chains(nodes: list[str], edges: list[tuple[str, str]], assigned: dict[str, str], *,
                 sources: set[str] | None = None) -> list[dict]:
    """Split independent chains that share one execution target.

    ``assigned`` maps every schedulable node to its target key.  Source nodes
    are staging inputs and are not units.  Unit ids are stable for a given plan
    (``branch_1`` ... in topological order).
    """
    sources = set(sources or ())
    schedulable = [node for node in nodes if node not in sources]
    incoming, outgoing, order = topology(schedulable, [(a, b) for a, b in edges
                                                       if a not in sources and b not in sources])
    index = {node: position for position, node in enumerate(order)}
    owner: dict[str, int] = {}
    chains: list[list[str]] = []
    for node in order:
        if node in owner:
            continue
        chain = [node]
        owner[node] = len(chains)
        current = node
        while True:
            children = [child for child in outgoing[current] if child not in sources]
            if len(children) != 1:
                break
            child = children[0]
            if child in owner:
                break
            if len(incoming[child]) != 1:
                break
            if assigned.get(child) != assigned.get(current):
                break
            chain.append(child)
            owner[child] = len(chains)
            current = child
        chains.append(chain)
    # Sort units by their first node so planning is deterministic.
    order_index = sorted(range(len(chains)), key=lambda i: index[chains[i][0]])
    remap = {old: new for new, old in enumerate(order_index)}
    units = []
    for new in range(len(chains)):
        chain = chains[order_index[new]]
        dependencies = set()
        for node in chain:
            for parent in incoming[node]:
                if owner[parent] != owner_index(chain, owner):
                    dependencies.add(remap[owner[parent]])
        units.append({'id': f'stage_{new + 1}', 'node_ids': chain,
                      'depends_on': [f'stage_{number + 1}' for number in
                                     sorted(remap[item] for item in dependencies)],
                      'target_key': assigned[chain[0]]})
    return units


def owner_index(chain, owner):
    return owner[chain[0]]


def parallel_estimate(chains: list[dict], *, process_overhead_bytes: int = 0,
                      sequential_bytes: int = 0) -> dict:
    """Compare serial versus split overhead before choosing parallelism."""
    if not chains:
        return {'units': 0, 'split': False, 'extra_overhead_bytes': 0}
    return {'units': len(chains), 'split': len(chains) > 1,
            'extra_overhead_bytes': process_overhead_bytes * max(0, len(chains) - 1),
            'sequential_equivalent_bytes': sequential_bytes,
            'worth_splitting': len(chains) > 1 and
            process_overhead_bytes * max(0, len(chains) - 1) < max(1, sequential_bytes)}


def units_from_engine_plan(plan: dict) -> list[UnitPlan]:
    """Adapt the existing execution plan without changing its unit identities."""
    units = []
    for item in plan.get('units', []):
        units.append(UnitPlan(unit_id=item['id'], node_ids=tuple(item.get('node_ids', ())),
                              depends_on=tuple(item.get('depends_on', ())),
                              target=dict(item.get('target') or {'kind': 'local'})))
    return units


def ready_nodes(units: list[dict], completed: set[str]) -> list[str]:
    return [unit['id'] for unit in units
            if unit['id'] not in completed and set(unit.get('depends_on', ())) <= completed]


@dataclass(frozen=True)
class BranchDecision:
    unit_id: str
    run: bool
    reason: str


def decide_branches(estimate: dict, *, max_parallel: int, enabled: bool) -> list[BranchDecision]:
    """The planner records why a branch was or was not split."""
    if not enabled:
        return [BranchDecision('all', False, 'split-disabled')]
    if estimate.get('units', 0) <= 1:
        return [BranchDecision('all', False, 'single-chain')]
    if not estimate.get('worth_splitting'):
        return [BranchDecision('all', False, 'duplicated-process-overhead-exceeds-benefit')]
    if max_parallel < 2:
        return [BranchDecision('all', False, 'max-parallel-tasks-is-one')]
    return [BranchDecision('all', True, 'independent-branches-within-close')]
