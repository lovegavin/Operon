"""One persistent scheduling thread, bounded I/O and fail-closed leadership.

The planner hook resolves immutable environment/storage bindings outside SQL.
It returns prepared placement arguments, never grants physical resources.
"""
from __future__ import annotations

import json
import threading
import time

from operon.engine.contracts import BusyError
from .receipts import LeadershipLost, Observation
from .service import BoundedExecutor
from .invocation import ConsumerTemplate, consumer_intent


class ClusterController:
    def __init__(self, repository, leadership, *, executors, planner, database_work=None, tick_seconds=1):
        if not 0 < tick_seconds <= 10:
            raise ValueError('Scheduler tick must be within (0,10] seconds')
        self.repository, self.leadership = repository, leadership
        self.executors, self.planner = dict(executors), planner
        self.tick_seconds = tick_seconds
        self.database_work = database_work or BoundedExecutor({'ordinary': 6, 'scheduler': 1, 'lifecycle': 1}, name='cluster-db')
        self._owns_database_work = database_work is None
        self.io = BoundedExecutor({'control': 6, 'poll': 1, 'lifecycle': 1}, name='cluster-ssh')
        self._stop, self._wake = threading.Event(), threading.Event()
        self._thread = None
        self._pending = {}  # At most eight Futures, retained until receipt is durable.
        self._next_poll = {}
        self.last_error = None
        self.preparation_errors = {}
        self._recovery = True

    def _db(self, function, *args, **kwargs):
        return self.database_work.submit('scheduler', function, *args, **kwargs).result()

    def start(self, *, prepare=None):
        if self._thread is not None:
            raise RuntimeError('Controller already started')
        self.leadership.acquire()
        if prepare is not None:
            prepare()
        self.leadership.assert_current(dispatch=False)
        self._db(self.repository.recovery_barrier, epoch=self.leadership.epoch)
        self._thread = threading.Thread(target=self._run, name='cluster-scheduler', daemon=True)
        self._thread.start()

    def wake(self):
        self._wake.set()

    def _launch(self, dispatch, operation):
        if dispatch.command_id in self._pending or len(self._pending) >= 8:
            return False
        executor = self.executors[dispatch.executor]
        def execute():
            self.leadership.assert_current(dispatch=operation == 'launch')
            return getattr(executor, operation)(dispatch)
        lane = {'launch': 'control', 'reconcile': 'poll', 'cancel': 'lifecycle'}[operation]
        try:
            future = self.io.submit(lane, execute)
        except BusyError:
            return False
        self._pending[dispatch.command_id] = (future, dispatch, operation)
        future.add_done_callback(lambda _: self.wake())
        return True

    def _collect(self):
        for command_id, (future, dispatch, operation) in tuple(self._pending.items()):
            if not future.done():
                continue
            try:
                observation = future.result()
            except LeadershipLost:
                raise
            except Exception as exc:
                observation = Observation('recovery_required', operation + '_unknown', dispatch.external_handle,
                    dispatch.host_fence, json.dumps({'error': type(exc).__name__}))
            # Keep the Future until commit succeeds; a failed DB write cannot lose evidence.
            self._db(self.repository.observe, dispatch, observation, epoch=self.leadership.epoch)
            if operation == 'cancel':
                self._db(self.repository.finish_cancel, dispatch.attempt_id)
            if observation.state in ('succeeded', 'failed', 'cancelled') or observation.admission_rejected:
                self._next_poll.pop(command_id, None)
            else:
                self._next_poll[command_id] = time.monotonic() + getattr(self.executors[dispatch.executor], 'poll_interval', 10.0)
            del self._pending[command_id]

    def _prepared_arguments(self, arguments, ready):
        """Read producer identities after bounded ranking, before durable send.

        No filesystem scan or RPC runs here. Host resolution happens on the
        existing bounded I/O lane after the dispatch key has been committed.
        """
        if arguments['payload'].get('format') != 'operon.cluster-consumer-template':
            return arguments
        template = ConsumerTemplate.model_validate(arguments['payload'])
        row = next(value for value in ready if value['run_id'] == arguments['run_id']
                   and value['unit_id'] == arguments['unit_id'])
        if row['plan_id'] != template.source_plan.plan_id or arguments['node_id'] != template.target_node_id:
            raise ValueError('Consumer template differs from the admitted plan or selected host')
        unit = next(unit for unit in template.source_plan.units if unit.unit_id == template.source_unit_id)
        parents = {value[len('artifact:'):].split('/', 1)[0] for value in unit.input_bindings.values()
                   if value.startswith('artifact:')}
        producers = self._db(self.repository.producer_receipts, row['principal'], row['run_id'], parents)
        intent = consumer_intent(template, producers, principal=row['principal'], cluster_run_id=row['run_id'],
            controller_id=arguments['controller_id'], controller_epoch=self.leadership.epoch)
        return {**arguments, 'payload': intent.model_dump(mode='json')}

    def step(self):
        self.leadership.assert_current(dispatch=False)
        self._collect()
        if self._recovery:
            recover = self._db(self.repository.dispatches, needs_reconcile_epoch=self.leadership.epoch, limit=256)
            for dispatch in recover:
                if len(self._pending) >= 8:
                    break
                self._launch(dispatch, 'reconcile')
            if recover or self._pending:
                return
            self.leadership.reconciled()
            self._recovery = False
        for dispatch in self._db(self.repository.cancellations):
            if dispatch.command_id in self._pending:
                continue
            if dispatch.external_handle is None:
                # A not-yet-sent command is cancelled locally, never sent merely
                # to obtain a remote handle for cancellation.
                if dispatch.phase == 'pending':
                    self._db(self.repository.observe, dispatch,
                             Observation('cancelled', 'cancelled_before_dispatch', stop_confirmed=True),
                             epoch=self.leadership.epoch)
                    self._db(self.repository.finish_cancel, dispatch.attempt_id)
                else:
                    self._launch(dispatch, 'reconcile')
            else:
                self._launch(dispatch, 'cancel')
        # Cancellation gets the lifecycle lane before ordinary periodic polling.
        for dispatch in self._db(self.repository.dispatches, limit=256):
            if len(self._pending) >= 8:
                break
            if time.monotonic() >= self._next_poll.get(dispatch.command_id, 0):
                self._launch(dispatch, 'reconcile')
        if len(self._pending) >= 6:
            return
        # Pure bounded placement hook. Payload staging must already be complete.
        ready = self._db(self.repository.ready)
        nodes = self._db(self.repository.nodes)
        available = 6 - len(self._pending)
        self.preparation_errors = {}
        for index, arguments in enumerate(self.planner(ready, nodes)):
            if index >= available:
                break
            self.leadership.assert_current()
            try:
                arguments = self._prepared_arguments(arguments, ready)
            except ValueError as exc:
                # A proven unsupported edge must not starve already admitted
                # unrelated work. Keep a bounded per-pass diagnostic and leave
                # this unit unclaimed; no external command was sent.
                self.preparation_errors[(arguments['run_id'], arguments['unit_id'])] = {
                    'code': getattr(exc, 'code', 'invalid_consumer_preparation'), 'message': str(exc)[:1000]}
                continue
            self._db(self.repository.prepare_dispatch, **arguments, epoch=self.leadership.epoch)
        for pending in self._db(self.repository.dispatches, pending=True):
            if len(self._pending) >= 6:
                break
            self.leadership.assert_current()
            dispatch = self._db(self.repository.claim_dispatch, pending.command_id, epoch=self.leadership.epoch)
            if dispatch:
                # If the I/O lane becomes full after claiming, leave it uncertain
                # for reconciliation. Never silently change it back to pending.
                self._launch(dispatch, 'launch')

    def _run(self):
        while not self._stop.is_set():
            try:
                self.step()
                self.last_error = None
            except LeadershipLost as exc:
                self.last_error = exc
                self._stop.set()
                break
            except Exception as exc:
                self.last_error = exc
            self._wake.wait(self.tick_seconds)
            self._wake.clear()

    def request_stop(self):
        self._stop.set()
        self._wake.set()

    def stop(self):
        self.request_stop()
        if self._thread is not None:
            self._thread.join(timeout=10)
        self.leadership.close()
        self.io.close(wait=True)
        if self._owns_database_work:
            self.database_work.close()
