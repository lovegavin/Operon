"""Durable event cursors, compact snapshots and bounded subscriptions.

Delivery is pull-based.  A slow or vanished subscriber cannot accumulate an
unbounded server-side queue: the durable journal keeps the cursor and every
read is limited by event count and encoded bytes.  A client whose cursor has
been pruned receives an explicit ``cursor_expired`` result and requests a
snapshot instead.
"""
from __future__ import annotations

import time

from .contracts import CursorExpiredError
from .telemetry import METRICS

DEFAULT_LIMIT = 200
DEFAULT_BYTES = 256 * 1024


def compact_run(run: dict, units: list[dict] | None = None) -> dict:
    value = {
        'id': run['id'], 'status': run['status'], 'revision': int(run['revision']),
        'principal': run['principal'], 'project': run['project'], 'workspace_id': run['workspace_id'],
        'plan_key': run['plan_key'], 'cancel_requested': bool(run.get('cancel_requested')),
        'cancel_state': run.get('cancel_state'), 'created_at': run['created_at'],
        'updated_at': run['updated_at'], 'finished_at': run.get('finished_at'), 'error': run.get('error'),
    }
    if units is not None:
        value['units'] = [{'id': unit['local_id'], 'state': unit['state'],
                           'attempts': int(unit['attempts']), 'depends_on': list(unit['depends_on'])}
                          for unit in units]
    return value


class Page:
    __slots__ = ('events', 'cursor', 'floor', 'has_more', 'bytes', 'snapshot_required')

    def __init__(self, value: dict, *, snapshot_required=False):
        self.events = value.get('events', [])
        self.cursor = int(value.get('cursor', 0))
        self.floor = int(value.get('floor', 0))
        self.has_more = bool(value.get('has_more'))
        self.bytes = int(value.get('bytes', 0))
        self.snapshot_required = snapshot_required

    def to_json(self) -> dict:
        return {'events': self.events, 'cursor': self.cursor, 'floor': self.floor,
                'has_more': self.has_more, 'bytes': self.bytes,
                **({'snapshot_required': True} if self.snapshot_required else {})}


class EventStream:
    """Cursor-based view of the durable event journal."""

    def __init__(self, store, *, limit=DEFAULT_LIMIT, max_bytes=DEFAULT_BYTES):
        self.store = store
        self.limit = max(1, int(limit))
        self.max_bytes = max(4096, int(max_bytes))

    def page(self, cursor=0, *, run_id=None, principal=None, workspace_id=None, kinds=None,
             limit=None, max_bytes=None) -> Page:
        start = time.perf_counter()
        try:
            value = self.store.events_after(
                int(cursor), limit=limit or self.limit, run_id=run_id, principal=principal,
                workspace_id=workspace_id, kinds=kinds, max_bytes=max_bytes or self.max_bytes)
            page = Page(value)
        except CursorExpiredError as exc:
            page = Page({'events': [], 'cursor': int(cursor), 'floor': exc.details.get('floor', 0),
                         'has_more': False, 'bytes': 0}, snapshot_required=True)
        METRICS.observe('events.page_ms', (time.perf_counter() - start) * 1000)
        METRICS.increment('events.pages')
        METRICS.increment('events.delivered', len(page.events))
        return page

    def wait(self, cursor=0, *, timeout=1.0, **filters) -> Page:
        """Long-poll for durable events without a server-side queue."""
        deadline = time.monotonic() + max(0.0, float(timeout))
        while True:
            page = self.page(cursor, **filters)
            if page.events or page.snapshot_required:
                return page
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return page
            self.store.wait_events(int(cursor), min(remaining, 0.5))

    def snapshot(self, *, principal=None, workspace_id=None, limit=200) -> dict:
        """Compact authoritative snapshot used when a cursor has expired."""
        runs = self.store.list_runs(principal=principal, workspace_id=workspace_id, limit=limit)
        values = []
        for run in runs:
            values.append(compact_run(run, self.store.units(run['id'])))
        first, last = self.store.event_bounds()
        return {'schema_version': 1, 'runs': values, 'event_bounds': [first, last],
                'floor': self.store._event_floor(), 'snapshot_at': time.time()}

    def prune(self, keep=20000) -> dict:
        return self.store.prune_events(keep=keep)


class Subscription:
    """A bounded, resumable subscription over one filter set.

    ``batch`` never materializes more than ``max_events`` events.  There is no
    unbounded internal queue, so a stalled consumer only stops advancing its
    cursor; the producer never pays for it.
    """

    def __init__(self, stream: EventStream, *, cursor=0, max_events=128, **filters):
        self.stream = stream
        self.cursor = int(cursor)
        self.max_events = max(1, int(max_events))
        self.filters = filters
        self.closed = False
        self.dropped = 0

    def batch(self, timeout=1.0) -> Page:
        if self.closed:
            return Page({'events': [], 'cursor': self.cursor, 'has_more': False})
        page = self.stream.wait(self.cursor, timeout=timeout, limit=min(self.max_events, self.stream.limit),
                                **self.filters)
        if page.events:
            self.cursor = page.cursor
        if page.snapshot_required:
            self.closed = True
        return page

    def close(self):
        self.closed = True
