"""Restart reconciliation for durable attempts, leases and artifact commits.

Recovery is deliberately conservative: a live identity is adopted only with a
verified receipt, a missing receipt for a never-launched attempt is failed and
released, and unknown ownership remains quarantined with its lease charged.
"""
from __future__ import annotations

from dataclasses import dataclass

from .artifacts import ArtifactCommitter
from .contracts import AttemptState, RunState
from .events import EventStream
from .state import now_iso
from .supervisor import ProcessSupervisor, SupervisorError
from .telemetry import METRICS


@dataclass(frozen=True)
class RecoveryReport:
    adopted: int = 0
    failed: int = 0
    quarantined: int = 0
    leases_released: int = 0
    artifacts: dict | None = None
    settled: int = 0

    def to_json(self) -> dict:
        return {'adopted': self.adopted, 'failed': self.failed, 'quarantined': self.quarantined,
                'leases_released': self.leases_released, 'artifacts': self.artifacts or {},
                'settled': self.settled, 'at': now_iso()}


def recover(runtime, *, supervisor: ProcessSupervisor | None = None,
            artifact_committer: ArtifactCommitter | None = None) -> RecoveryReport:
    """Reconcile one engine root after a coordinator/service restart."""
    store = runtime.store
    if store is None:
        return RecoveryReport()
    supervisor = supervisor or ProcessSupervisor(runtime.workspace_root / 'supervisor')
    adopted = failed = quarantined = released = settled = 0
    now = now_iso()
    # 1. Artifact crash points: resolve rename/receipt/database asymmetries.
    artifact_report = {}
    if artifact_committer is not None:
        try:
            artifact_report = artifact_committer.reconcile()
        except Exception as exc:  # noqa: BLE001 - report, never hide
            artifact_report = {'error': f'{type(exc).__name__}: {exc}'}
    # 2. Attempts and their leases.
    states = [AttemptState.ADMITTED.value, AttemptState.STARTING.value, AttemptState.RUNNING.value,
              AttemptState.COMMITTING.value, AttemptState.RECOVERY_REQUIRED.value]
    for attempt in store.attempts_for_pool(runtime.spec.pool_id, states=states):
        unit = store.unit(attempt['unit_id'])
        run = store.run(unit['run_id'])
        if run['cancel_requested']:
            # Cancellation is completed by the supervisor/coordinator; keep the
            # lease charged until the owned tree is confirmed stopped.
            continue
        receipt = supervisor.read_receipt(attempt['id'])
        state = AttemptState(attempt['state'])
        if receipt is not None and receipt.fence == int(attempt['fence']) and \
                receipt.identity is not None:
            from .supervisor import identity_alive
            if identity_alive(receipt.identity):
                if state in (AttemptState.ADMITTED, AttemptState.STARTING, AttemptState.RECOVERY_REQUIRED):
                    store.transition_attempt(attempt['id'], AttemptState.RUNNING,
                                             expected_revision=attempt['revision'],
                                             process=receipt.identity.to_json(),
                                             receipt={'adopted': 'supervisor'})
                adopted += 1
                continue
            # Proved dead: release only after the identity check, never merely
            # because a timeout elapsed.
            if state not in (AttemptState.SUCCEEDED, AttemptState.FAILED, AttemptState.CANCELLED):
                store.transition_attempt(attempt['id'], AttemptState.FAILED,
                                         expected_revision=attempt['revision'],
                                         error='Worker exited while the coordinator was absent; '
                                               'its scientific result is unknown',
                                         error_code='recovery_unknown')
            lease = store.lease(attempt['id'])
            if lease and lease['state'] != 'released':
                store.release_lease(lease['id'], reason='recovery: proven process death',
                                    released_process_bytes=lease['committed'].process_reservation_bytes)
                released += 1
            failed += 1
            continue
        if state in (AttemptState.ADMITTED, AttemptState.STARTING) and receipt is None:
            # The launch outbox never produced a process: safe to fail/release.
            store.transition_attempt(attempt['id'], AttemptState.FAILED,
                                     expected_revision=attempt['revision'],
                                     error='The attempt was never launched',
                                     error_code='launch_failed')
            lease = store.lease(attempt['id'])
            if lease and lease['state'] != 'released':
                store.release_lease(lease['id'], reason='recovery: never launched',
                                    released_process_bytes=lease['committed'].process_reservation_bytes)
                released += 1
            failed += 1
            continue
        # A running/committing attempt with no verifiable receipt is unknown
        # ownership: quarantine it and keep its lease charged.
        if state != AttemptState.RECOVERY_REQUIRED:
            store.transition_attempt(attempt['id'], AttemptState.RECOVERY_REQUIRED,
                                     expected_revision=attempt['revision'],
                                     error='Process ownership after restart is uncertain',
                                     error_code='recovery_required')
        quarantined += 1
    # 3. Release leases whose attempts are already terminal (crash between
    #    attempt terminal transition and lease release).
    for lease in store.lease_details(runtime.spec.pool_id):
        if not lease.get('attempt_state'):
            continue
        if lease['attempt_state'] in ('succeeded', 'failed', 'cancelled'):
            store.release_lease(lease['id'], reason='recovery: terminal attempt',
                                released_process_bytes=lease['committed'].process_reservation_bytes)
            released += 1
    # 4. Recompute readiness and settle runs.
    for run in store.list_runs(states=[RunState.QUEUED.value, RunState.RUNNING.value,
                                        RunState.SUBMITTED.value], limit=1000):
        store.set_unit_state_for_dependencies(run['id'])
        units = store.units(run['id'])
        if units and all(unit['state'] in ('succeeded', 'failed', 'cancelled') for unit in units):
            if all(unit['state'] == 'succeeded' for unit in units):
                continue
            if run['cancel_requested']:
                store.mark_cancel_stopped(run['id'], actor='recovery')
            else:
                store.transition_run(run['id'], RunState.FAILED, actor='recovery',
                                     reason='unit terminal after recovery',
                                     error='One or more execution units failed before recovery')
            settled += 1
    for pool in store.list_runs(states=[RunState.RECOVERY_REQUIRED.value], limit=100):
        METRICS.increment('recovery.quarantined_runs')
    store.append_event('recovery_completed', principal=runtime.principal,
                       payload={'adopted': adopted, 'failed': failed, 'quarantined': quarantined,
                                'leases_released': released, 'artifacts': artifact_report})
    return RecoveryReport(adopted=adopted, failed=failed, quarantined=quarantined,
                          leases_released=released, artifacts=artifact_report, settled=settled)
