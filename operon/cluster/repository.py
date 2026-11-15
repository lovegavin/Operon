"""Explicit SQL repository; transactions never contain executor operations."""
from __future__ import annotations

import hashlib
import json
import uuid

from operon.contracts.base import canonical_json
from operon.contracts.run_plan import RunPlan
from operon.engine.contracts import BusyError, IdempotencyConflictError, StaleRevisionError
from operon.execution.unit_executor import unit_dependencies
from .receipts import AdmissionLimits, ClusterError, Dispatch, LeadershipLost, Observation


def _json(value):
    return canonical_json(value)


def _id(prefix):
    return prefix + uuid.uuid4().hex


class ClusterRepository:
    def __init__(self, database, *, limits=AdmissionLimits()):
        self.db, self.limits = database, limits

    @staticmethod
    def _event(connection, principal, run_id, kind, payload):
        connection.execute('INSERT INTO events(principal,run_id,kind,payload) VALUES (%s,%s,%s,%s::jsonb)',
                           (principal, run_id, kind, _json(payload)))

    @staticmethod
    def _epoch(connection, epoch):
        row = connection.execute('SELECT epoch FROM controller_owner WHERE singleton=true FOR SHARE').fetchone()
        if row is None or row['epoch'] != epoch:
            raise LeadershipLost('Controller epoch is stale')

    def request(self, principal, request_id):
        with self.db.connection('lifecycle') as connection:
            row = connection.execute('SELECT receipt FROM requests WHERE principal=%s AND request_id=%s',
                                     (principal, request_id)).fetchone()
            return None if row is None else row['receipt']

    def unit_spec(self, principal, run_id, unit_id):
        """Read immutable deployment input before the bounded scheduler starts."""
        with self.db.connection() as connection:
            row = connection.execute('SELECT u.spec FROM units u JOIN runs r USING(run_id) '
                'WHERE r.principal=%s AND u.run_id=%s AND u.unit_id=%s', (principal, run_id, unit_id)).fetchone()
            if row is None:
                raise ClusterError('Prepared unit not found for this principal', code='not_found', status=404)
            return row['spec']

    def submit(self, *, principal: str, request_id: str, plan: RunPlan, preparations=0):
        if not principal or not request_id or len(principal) > 128 or len(request_id) > 512:
            raise ValueError('A bounded authenticated principal and request ID are required')
        if type(preparations) is not int or preparations < 0:
            raise ValueError('Preparations must be a non-negative integer')
        if plan.plan_id != plan.compute_id():
            raise ValueError('RunPlan identity does not match its frozen contents')
        plan_json = plan.canonical_json()
        digest = hashlib.sha256(plan_json.encode()).hexdigest()
        size, count = len(plan_json.encode('utf-8')), len(plan.units)
        dependencies = unit_dependencies(plan)
        run_id = _id('crun-')
        receipt = {'run_id': run_id, 'plan_id': plan.plan_id, 'request_id': request_id,
                   'state': 'queued', 'revision': '1'}

        def submit(connection):
            # Serialize a key before looking it up; matching replay precedes ALL quotas.
            connection.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',
                               (_json([principal, request_id]),))
            existing = connection.execute('SELECT digest,receipt FROM requests WHERE principal=%s AND request_id=%s',
                                          (principal, request_id)).fetchone()
            if existing:
                if existing['digest'] != digest:
                    raise IdempotencyConflictError('Request ID belongs to a different frozen plan')
                return existing['receipt']
            connection.execute("INSERT INTO quota_usage(principal,scope) VALUES (%s,'admission') ON CONFLICT DO NOTHING",
                               (principal,))
            usage = connection.execute("SELECT * FROM quota_usage WHERE principal=%s AND scope='admission' FOR UPDATE",
                                       (principal,)).fetchone()
            additions = {'runs': 1, 'units': count, 'plan_bytes': size,
                         'preparations': preparations, 'retained_requests': 1}
            for name, amount in additions.items():
                if usage[name] + amount > getattr(self.limits, name):
                    raise BusyError('Cluster admission quota reached', code='queue_full',
                                    details={'scope': name, 'limit': getattr(self.limits, name)})
            connection.execute('INSERT INTO requests(principal,request_id,digest,receipt) VALUES (%s,%s,%s,%s::jsonb)',
                               (principal, request_id, digest, _json(receipt)))
            connection.execute('INSERT INTO runs(run_id,principal,request_id,plan_id,plan,plan_bytes,unit_count,preparations) '
                               'VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s,%s)',
                               (run_id, principal, request_id, plan.plan_id, plan_json, size, count, preparations))
            for unit in plan.units:
                deps = sorted(dependencies[unit.unit_id])
                connection.execute('INSERT INTO units(run_id,unit_id,spec,depends_on,state) VALUES (%s,%s,%s::jsonb,%s::jsonb,%s)',
                                   (run_id, unit.unit_id, _json(unit), _json(deps), 'blocked' if deps else 'ready'))
            connection.execute("UPDATE quota_usage SET runs=runs+1,units=units+%s,plan_bytes=plan_bytes+%s,"
                               "preparations=preparations+%s,retained_requests=retained_requests+1 "
                               "WHERE principal=%s AND scope='admission'", (count, size, preparations, principal))
            connection.execute("INSERT INTO outbox(command_id,run_id,kind,payload) VALUES (%s,%s,'schedule',%s::jsonb)",
                               (_id('cmd-'), run_id, _json({'run_id': run_id})))
            self._event(connection, principal, run_id, 'run_submitted', receipt)
            return receipt
        return self.db.transaction(submit)

    def register_node(self, *, node_id, capacity_domain, executor, inventory):
        if executor not in ('ssh', 'slurm') or not node_id or not capacity_domain:
            raise ValueError('Node ID, unique capacity domain and executor are required')
        def register(connection):
            connection.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', ('capacity:' + capacity_domain,))
            overlap = connection.execute('SELECT node_id FROM nodes WHERE capacity_domain=%s AND node_id<>%s',
                                         (capacity_domain, node_id)).fetchone()
            if overlap:
                raise ClusterError('Capacity domain is already registered through another alias', code='capacity_domain_conflict')
            existing = connection.execute('SELECT capacity_domain,executor FROM nodes WHERE node_id=%s FOR UPDATE',
                                          (node_id,)).fetchone()
            if existing and (existing['capacity_domain'] != capacity_domain or existing['executor'] != executor):
                raise ClusterError('A registered node cannot change capacity identity', code='capacity_domain_conflict')
            return connection.execute(
                'INSERT INTO nodes(node_id,capacity_domain,executor,inventory) VALUES (%s,%s,%s,%s::jsonb) '
                'ON CONFLICT(node_id) DO UPDATE SET inventory=EXCLUDED.inventory,revision=nodes.revision+1 RETURNING revision',
                (node_id, capacity_domain, executor, _json(inventory))).fetchone()['revision']
        return self.db.transaction(register)

    def bind_environment(self, *, binding_id, requirement_digest, node_id, generation_id, content_digest, verification):
        if verification.get('verified') is not True:
            raise ValueError('Environment binding requires verified immutable generation evidence')
        def bind(connection):
            existing = connection.execute('SELECT * FROM environment_bindings WHERE binding_id=%s FOR UPDATE', (binding_id,)).fetchone()
            values = (requirement_digest, node_id, generation_id, content_digest)
            if existing:
                if tuple(existing[key] for key in ('requirement_digest', 'node_id', 'generation_id', 'content_digest')) != values:
                    raise IdempotencyConflictError('Environment binding ID is immutable')
                return binding_id
            connection.execute('INSERT INTO environment_bindings(binding_id,requirement_digest,node_id,generation_id,content_digest,verification) '
                               'VALUES (%s,%s,%s,%s,%s,%s::jsonb)', (binding_id, *values, _json(verification)))
            return binding_id
        return self.db.transaction(bind)

    def register_storage(self, *, storage_id, revision, topology):
        if type(revision) is not int or revision < 1:
            raise ValueError('Storage revision must be a positive integer')
        def register(connection):
            row = connection.execute('SELECT revision,topology FROM storage_endpoints WHERE storage_id=%s FOR UPDATE', (storage_id,)).fetchone()
            if row and (revision < row['revision'] or (revision == row['revision'] and row['topology'] != topology)):
                raise StaleRevisionError('Storage topology revision is stale or conflicts')
            connection.execute('INSERT INTO storage_endpoints(storage_id,revision,topology) VALUES (%s,%s,%s::jsonb) '
                'ON CONFLICT(storage_id) DO UPDATE SET revision=EXCLUDED.revision,topology=EXCLUDED.topology',
                (storage_id, revision, _json(topology)))
        self.db.transaction(register)

    def register_mount(self, *, node_id, storage_id, root, validation):
        if not root or validation.get('verified') is not True:
            raise ValueError('Mount must have a validated root mapping')
        self.db.transaction(lambda connection: connection.execute(
            'INSERT INTO node_mounts(node_id,storage_id,root,validation) VALUES (%s,%s,%s,%s::jsonb) '
            'ON CONFLICT(node_id,storage_id) DO UPDATE SET root=EXCLUDED.root,validation=EXCLUDED.validation',
            (node_id, storage_id, root, _json(validation))))

    def heartbeat(self, node_id, *, observed_pool_epoch, health='healthy'):
        if health not in ('healthy', 'suspect', 'offline', 'disabled'):
            raise ValueError('Invalid node health')
        return self.db.transaction(lambda connection: connection.execute(
            'UPDATE nodes SET observed_pool_epoch=%s,health=%s,heartbeat_at=now(),revision=revision+1 WHERE node_id=%s',
            (observed_pool_epoch, health, node_id)).rowcount)

    def nodes(self):
        with self.db.connection('scheduler') as connection:
            return list(connection.execute('SELECT * FROM nodes ORDER BY node_id'))

    def ready(self, limit=256):
        if type(limit) is not int or not 1 <= limit <= 256:
            raise ValueError('Ready page limit must be 1..256')
        with self.db.connection('scheduler') as connection:
            return list(connection.execute(
                "SELECT * FROM (SELECT u.*,r.principal,r.plan_id, row_number() OVER (PARTITION BY r.principal "
                "ORDER BY u.created_at,u.run_id,u.unit_id) AS principal_rank FROM units u JOIN runs r USING(run_id) "
                "WHERE u.state='ready' AND r.state IN ('queued','running')) candidates "
                'ORDER BY principal_rank,created_at,principal,run_id,unit_id LIMIT %s', (limit,)))

    def prepare_dispatch(self, *, run_id, unit_id, node_id, executor, controller_id, epoch,
                         expected_revision, payload, binding_id=None):
        attempt_id, command_id, key = _id('cattempt-'), _id('cmd-'), _id('operon-')
        def prepare(connection):
            self._epoch(connection, epoch)
            run = connection.execute('SELECT state FROM runs WHERE run_id=%s FOR UPDATE', (run_id,)).fetchone()
            if not run or run['state'] not in ('queued', 'running'):
                raise StaleRevisionError('Run is no longer eligible for placement')
            unit = connection.execute('SELECT * FROM units WHERE run_id=%s AND unit_id=%s FOR UPDATE',
                                      (run_id, unit_id)).fetchone()
            if not unit or unit['state'] != 'ready' or unit['revision'] != expected_revision:
                raise StaleRevisionError('Unit is no longer eligible for placement')
            node = connection.execute('SELECT executor,health FROM nodes WHERE node_id=%s', (node_id,)).fetchone()
            if not node or node['executor'] != executor or node['health'] != 'healthy':
                raise ClusterError('Node is not eligible for dispatch', code='node_unavailable')
            if binding_id:
                binding = connection.execute('SELECT node_id FROM environment_bindings WHERE binding_id=%s', (binding_id,)).fetchone()
                if not binding or binding['node_id'] != node_id:
                    raise ClusterError('Environment binding does not belong to target node', code='environment_generation_unavailable')
            # Submission token is generated and committed BEFORE any external sbatch/RPC.
            connection.execute(
                'INSERT INTO placements(attempt_id,run_id,unit_id,node_id,executor,command_id,request_key,'
                'controller_id,controller_epoch,payload,binding_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)',
                (attempt_id, run_id, unit_id, node_id, executor, command_id, key,
                 controller_id, epoch, _json(payload), binding_id))
            connection.execute("INSERT INTO outbox(command_id,attempt_id,run_id,kind,payload) VALUES (%s,%s,%s,'submit',%s::jsonb)",
                               (command_id, attempt_id, run_id, _json({'request_key': key, 'node_id': node_id})))
            connection.execute("UPDATE units SET state='admitted',revision=revision+1 WHERE run_id=%s AND unit_id=%s",
                               (run_id, unit_id))
            return command_id
        return self.db.transaction(prepare, lane='scheduler')

    def producer_receipts(self, principal, run_id, unit_ids):
        """Bounded, read-only identities for same-run host-side verification.

        The connection is returned before preparation or RPC. This does not
        authorize a path or certify bytes; the host resolves the named evidence.
        """
        unit_ids = tuple(sorted(set(unit_ids)))
        if not unit_ids or len(unit_ids) > 128 or any(not isinstance(value, str) or len(value) > 200 for value in unit_ids):
            raise ValueError('Producer receipt page requires 1..128 bounded unit IDs')
        with self.db.connection('scheduler') as connection:
            rows = list(connection.execute(
                'SELECT p.*,r.principal,r.plan_id,u.spec,u.state AS unit_state FROM placements p '
                'JOIN runs r USING(run_id) JOIN units u ON u.run_id=p.run_id AND u.unit_id=p.unit_id '
                "WHERE r.principal=%s AND p.run_id=%s AND p.unit_id=ANY(%s) AND p.state='succeeded' "
                "AND u.state='succeeded' AND p.active=false ORDER BY p.unit_id,p.created_at,p.command_id LIMIT 129",
                (principal, run_id, list(unit_ids))))
        if len(rows) > 128:
            raise ClusterError('Producer receipt page is ambiguous or exceeds its bound', code='producer_not_committed')
        return rows

    @staticmethod
    def _dispatch(row):
        return Dispatch(command_id=row['command_id'], attempt_id=row['attempt_id'], run_id=row['run_id'],
                        unit_id=row['unit_id'], node_id=row['node_id'], executor=row['executor'],
                        request_key=row['request_key'], principal=row['principal'], controller_id=row['controller_id'],
                        controller_epoch=row['controller_epoch'], payload_json=_json(row['payload']),
                        external_handle=row['external_handle'], host_fence=row['host_fence'], phase=row['phase'])

    def claim_dispatch(self, command_id, *, epoch):
        def claim(connection):
            self._epoch(connection, epoch)
            row = connection.execute('SELECT p.*,r.principal,o.state AS delivery FROM placements p '
                'JOIN runs r USING(run_id) JOIN outbox o ON o.command_id=p.command_id '
                'WHERE p.command_id=%s FOR UPDATE OF o,p', (command_id,)).fetchone()
            if row is None or row['delivery'] != 'pending' or not row['active']:
                return None
            if connection.execute("SELECT 1 FROM outbox WHERE attempt_id=%s AND kind='cancel'", (row['attempt_id'],)).fetchone():
                return None  # Cancellation intent already won; never dispatch it.
            connection.execute("UPDATE outbox SET state='dispatching',updated_at=now() WHERE command_id=%s", (command_id,))
            connection.execute("UPDATE placements SET phase='dispatching',state='starting',revision=revision+1 WHERE command_id=%s",
                               (command_id,))
            row['phase'] = 'dispatching'
            return self._dispatch(row)
        return self.db.transaction(claim, lane='scheduler')

    def dispatches(self, *, pending=False, limit=256, needs_reconcile_epoch=None):
        if type(limit) is not int or not 1 <= limit <= 256:
            raise ValueError('Dispatch page limit must be 1..256')
        with self.db.connection('scheduler') as connection:
            rows = connection.execute('SELECT p.*,r.principal FROM placements p JOIN runs r USING(run_id) '
                'JOIN outbox o ON o.command_id=p.command_id WHERE p.active=true AND '
                + ("o.state='pending' " if pending else "o.state<>'pending' ")
                + ('AND p.observed_epoch<>%s ' if needs_reconcile_epoch is not None else '')
                + 'ORDER BY o.updated_at,p.command_id LIMIT %s',
                ((needs_reconcile_epoch, limit) if needs_reconcile_epoch is not None else (limit,)))
            return tuple(self._dispatch(row) for row in rows)

    def recovery_barrier(self, *, epoch):
        """Crash between claim/send/reply stays uncertain, never returns to pending."""
        def recover(connection):
            self._epoch(connection, epoch)
            connection.execute("UPDATE outbox SET state='unknown',updated_at=now() WHERE state='dispatching'")
            connection.execute("UPDATE placements SET state='recovery_required',phase='submission_unknown',revision=revision+1 "
                               "WHERE active=true AND phase='dispatching'")
            connection.execute("UPDATE outbox SET state='delivered',updated_at=now() WHERE kind='schedule' AND state='pending'")
        self.db.transaction(recover, lane='scheduler')

    def observe(self, dispatch: Dispatch, observation: Observation, *, epoch):
        valid_states = {'admitted', 'starting', 'running', 'committing', 'succeeded', 'failed', 'cancelled', 'recovery_required'}
        if observation.state not in valid_states:
            raise ValueError('Unknown executor state')
        terminal = observation.state in ('succeeded', 'failed', 'cancelled')
        if terminal and not observation.stop_confirmed:
            raise ValueError('Terminal state requires verified stop evidence')
        if observation.state == 'succeeded' and not observation.evidence.get('artifact_committed'):
            raise ValueError('Success requires committed and verified output artifacts')
        def observe(connection):
            self._epoch(connection, epoch)
            run = connection.execute('SELECT * FROM runs WHERE run_id=%s FOR UPDATE', (dispatch.run_id,)).fetchone()
            row = connection.execute('SELECT * FROM placements WHERE command_id=%s FOR UPDATE', (dispatch.command_id,)).fetchone()
            if not row or row['node_id'] != dispatch.node_id or row['request_key'] != dispatch.request_key:
                raise ClusterError('Receipt does not match the placement', code='receipt_identity_mismatch')
            if not row['active']:
                return
            if row['external_handle'] and observation.external_handle and row['external_handle'] != observation.external_handle:
                raise ClusterError('External handle changed', code='receipt_identity_mismatch')
            if row['host_fence'] is not None and observation.host_fence is not None and row['host_fence'] != observation.host_fence:
                raise ClusterError('Host fence changed', code='receipt_identity_mismatch')
            rejected = observation.admission_rejected
            if rejected and (row['external_handle'] or observation.external_handle or not observation.stop_confirmed):
                raise ValueError('Admission rejection requires proof of non-acceptance')
            connection.execute('UPDATE placements SET state=%s,phase=%s,external_handle=COALESCE(%s,external_handle),'
                               'host_fence=COALESCE(%s,host_fence),evidence=%s::jsonb,active=%s,observed_epoch=%s,revision=revision+1 WHERE command_id=%s',
                               (observation.state, observation.phase, observation.external_handle, observation.host_fence,
                                observation.evidence_json, not (terminal or rejected), epoch, dispatch.command_id))
            connection.execute('UPDATE outbox SET state=%s,evidence=%s::jsonb,updated_at=now() WHERE command_id=%s',
                               ('unknown' if observation.state == 'recovery_required' else 'delivered',
                                observation.evidence_json, dispatch.command_id))
            connection.execute('UPDATE units SET state=%s,revision=revision+1 WHERE run_id=%s AND unit_id=%s',
                               ('ready' if rejected else observation.state, dispatch.run_id, dispatch.unit_id))
            if observation.state == 'succeeded':
                connection.execute("UPDATE units u SET state='ready',revision=revision+1 WHERE run_id=%s AND state='blocked' "
                    "AND NOT EXISTS (SELECT 1 FROM jsonb_array_elements_text(u.depends_on) d(unit_id) JOIN units parent "
                    "ON parent.run_id=u.run_id AND parent.unit_id=d.unit_id WHERE parent.state<>'succeeded')", (dispatch.run_id,))
            if terminal and observation.state in ('failed', 'cancelled'):
                # Never kill siblings implicitly. Unstarted descendants cannot run.
                connection.execute("UPDATE units SET state='cancelled',revision=revision+1 WHERE run_id=%s AND state IN ('blocked','ready')",
                                   (dispatch.run_id,))
            states = [item['state'] for item in connection.execute('SELECT state FROM units WHERE run_id=%s', (dispatch.run_id,))]
            if all(state in ('succeeded', 'failed', 'cancelled') for state in states):
                run_state = 'failed' if 'failed' in states else ('cancelled' if 'cancelled' in states else 'complete')
                if not run['quota_released']:
                    connection.execute("UPDATE quota_usage SET runs=runs-1,units=units-%s,plan_bytes=plan_bytes-%s,"
                        "preparations=preparations-%s WHERE principal=%s AND scope='admission'",
                        (run['unit_count'], run['plan_bytes'], run['preparations'], run['principal']))
                connection.execute('UPDATE runs SET state=%s,quota_released=true,revision=revision+1 WHERE run_id=%s',
                                   (run_state, dispatch.run_id))
            else:
                connection.execute('UPDATE runs SET state=%s,revision=revision+1 WHERE run_id=%s',
                    ('recovery_required' if 'recovery_required' in states else 'running', dispatch.run_id))
            self._event(connection, dispatch.principal, dispatch.run_id, 'attempt_observed',
                        {'attempt_id': dispatch.attempt_id, 'state': observation.state, 'phase': observation.phase})
        self.db.transaction(observe, lane='scheduler')

    def status(self, principal, run_id):
        with self.db.connection('lifecycle') as connection:
            run = connection.execute('SELECT run_id,plan_id,state,revision,unit_count FROM runs WHERE run_id=%s AND principal=%s',
                                     (run_id, principal)).fetchone()
            if run is None:
                raise ClusterError('Run not found for this principal', code='not_found', status=404)
            return {**run, 'revision': str(run['revision'])}

    def cancel(self, principal, run_id):
        """Durable cancellation intent; never perform network I/O under the lock."""
        def cancel(connection):
            run = connection.execute('SELECT * FROM runs WHERE run_id=%s AND principal=%s FOR UPDATE',
                                     (run_id, principal)).fetchone()
            if run is None:
                raise ClusterError('Run not found for this principal', code='not_found', status=404)
            if run['state'] in ('complete', 'failed', 'cancelled'):
                return {'run_id': run_id, 'state': run['state']}
            # Lock active placements to serialize with receipt recording.
            placements = list(connection.execute('SELECT * FROM placements WHERE run_id=%s AND active=true FOR UPDATE', (run_id,)))
            for row in placements:
                connection.execute("INSERT INTO outbox(command_id,attempt_id,run_id,kind,payload) VALUES (%s,%s,%s,'cancel','{}') "
                                   'ON CONFLICT(command_id) DO NOTHING',
                                   ('cancel-' + row['attempt_id'], row['attempt_id'], run_id))
            connection.execute("UPDATE units SET state='cancelled',revision=revision+1 WHERE run_id=%s AND state IN ('ready','blocked')", (run_id,))
            if not placements:
                if not run['quota_released']:
                    connection.execute("UPDATE quota_usage SET runs=runs-1,units=units-%s,plan_bytes=plan_bytes-%s,"
                        "preparations=preparations-%s WHERE principal=%s AND scope='admission'",
                        (run['unit_count'], run['plan_bytes'], run['preparations'], principal))
                connection.execute("UPDATE runs SET state='cancelled',quota_released=true,revision=revision+1 WHERE run_id=%s", (run_id,))
            self._event(connection, principal, run_id, 'cancel_requested', {})
            return {'run_id': run_id, 'state': 'cancel_requested' if placements else 'cancelled'}
        return self.db.transaction(cancel, lane='lifecycle')

    def cancellations(self, limit=8):
        with self.db.connection('scheduler') as connection:
            rows = connection.execute('SELECT p.*,r.principal FROM placements p JOIN runs r USING(run_id) '
                "JOIN outbox c ON c.attempt_id=p.attempt_id AND c.kind='cancel' "
                "WHERE p.active=true AND c.state<>'delivered' ORDER BY c.updated_at LIMIT %s", (limit,))
            return tuple(self._dispatch(row) for row in rows)

    def finish_cancel(self, attempt_id):
        self.db.transaction(lambda connection: connection.execute(
            "UPDATE outbox SET state='delivered',updated_at=now() WHERE attempt_id=%s AND kind='cancel' "
            'AND NOT EXISTS(SELECT 1 FROM placements p WHERE p.attempt_id=%s AND p.active=true)',
            (attempt_id, attempt_id)), lane='scheduler')

    def events(self, principal, *, after='0', limit=200):
        if not isinstance(after, str) or not after.isdecimal() or not 1 <= limit <= 1000:
            raise ValueError('Expected a decimal cursor and page limit 1..1000')
        with self.db.connection('lifecycle') as connection:
            rows = list(connection.execute('SELECT cursor,run_id,kind,payload FROM events WHERE principal=%s AND cursor>%s '
                                           'ORDER BY cursor LIMIT %s', (principal, int(after), limit)))
            return [{**row, 'cursor': str(row['cursor'])} for row in rows]

    def update_cost(self, key, seconds, *, alpha=0.25):
        import math
        if not math.isfinite(seconds) or seconds < 0 or not 0 < alpha <= 1:
            raise ValueError('Cost samples must be finite and nonnegative')
        self.db.transaction(lambda connection: connection.execute(
            'INSERT INTO cost_estimates(cost_key,seconds,sample_count,confidence) VALUES (%s,%s,1,0.1) '
            'ON CONFLICT(cost_key) DO UPDATE SET seconds=cost_estimates.seconds*(1-%s)+EXCLUDED.seconds*%s,'
            'sample_count=cost_estimates.sample_count+1,confidence=LEAST(1.0,(cost_estimates.sample_count+1)/10.0),updated_at=now()',
            (key, seconds, alpha, alpha)), lane='scheduler')
