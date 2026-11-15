"""Bounded environment grouping driven by a real resolver, never import guessing."""
from __future__ import annotations

from dataclasses import dataclass
import time

from operon.contracts.base import sha256_hex


@dataclass(frozen=True)
class ResolutionGroup:
    members: tuple[str, ...]
    requirement: dict
    resolution: dict
    reason: str


def resolve_groups(requirements, resolver, *, max_merges=16, seconds=30):
    """resolver(requirements, timeout=...) must return the actual locked closure.

    Called on every initial group; unresolved requirements are errors. A failed
    optional merge keeps already resolved groups separate. This avoids exhaustive
    graph coloring and never declares compatibility from module import names.
    """
    deadline = time.monotonic() + seconds
    groups, identical = [], {}
    for name, requirement in sorted(requirements.items()):
        key = sha256_hex(requirement)
        if key in identical:
            i = identical[key]
            prior = groups[i]
            groups[i] = ResolutionGroup((*prior.members, name), prior.requirement, prior.resolution, prior.reason)
            continue
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('Initial dependency resolution exceeded its budget')
        resolved = resolver([requirement], timeout=remaining)
        identical[key] = len(groups)
        groups.append(ResolutionGroup((name,), requirement, resolved, 'resolved independently'))
    attempts = 0
    i = 0
    while i < len(groups):
        j = i + 1
        while j < len(groups) and attempts < max_merges and time.monotonic() < deadline:
            a, b = groups[i], groups[j]
            # Runtime includes language and ABI. Capability/tool policy is exact.
            keys = ('target', 'runtime', 'required_capabilities')
            if any(a.requirement.get(k) != b.requirement.get(k) for k in keys):
                j += 1
                continue
            attempts += 1
            members = tuple(sorted((*a.members, *b.members)))
            try:
                merged = resolver([requirements[m] for m in members], timeout=deadline - time.monotonic())
            except (ValueError, TimeoutError):
                j += 1
                continue
            groups[i] = ResolutionGroup(members, a.requirement, merged, 'resolver verified merged closure')
            groups.pop(j)
        i += 1
    return groups
