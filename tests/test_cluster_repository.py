"""K08 tests require an actual, disposable PostgreSQL 17 database.

Set OPERON_TEST_POSTGRES_DSN to opt in. Every run owns a random schema; no
SQLite substitute is accepted. Missing infrastructure is an unmet gate.
"""
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import uuid

import pytest

from operon.contracts.run_plan import CodeRef, InvocationSpec, PlacementPolicy, ResourceRequestSpec, RunPlan, TargetSpec, UnitSpec
from operon.cluster.postgres import DatabaseConfig, Leadership, Postgres
from operon.cluster.receipts import AdmissionLimits, ClusterError, LeadershipLost, Observation
from operon.cluster.repository import ClusterRepository
from operon.engine.contracts import BusyError, CommitOutcomeUnknown, IdempotencyConflictError, StaleRevisionError


def plan():
    return RunPlan(plan_id='pending', workflow_revision='a' * 64, parameters_digest='b' * 64,
        compiler_version='test', units=(UnitSpec(unit_id='unit', node_ids=('node',),
            invocation=InvocationSpec(kind='command', argv=('true',), code_ref=CodeRef(kind='file', ref='true')),
            resource_request=ResourceRequestSpec(),
            placement=PlacementPolicy(executor='ssh', target=TargetSpec(os='linux', arch='x86_64'))),)).with_identity()


@pytest.fixture
def database():
    dsn = os.environ.get('OPERON_TEST_POSTGRES_DSN')
    if not dsn:
        pytest.skip('K08 real PostgreSQL 17 gate NOT RUN: OPERON_TEST_POSTGRES_DSN is not set')
    psycopg = pytest.importorskip('psycopg', reason='K08 pinned psycopg extra unavailable')
    pytest.importorskip('psycopg_pool', reason='K08 pinned psycopg_pool extra unavailable')
    from psycopg import sql
    schema = 'operon_test_' + uuid.uuid4().hex
    with psycopg.connect(dsn, autocommit=True) as admin:
        assert admin.info.server_version // 10000 == 17
        admin.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    database = Postgres(DatabaseConfig(dsn, schema=schema))
    try:
        database.migrate()
        yield database
    finally:
        database.close()
        with psycopg.connect(dsn, autocommit=True) as admin:
            admin.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))


@pytest.fixture
def leader(database):
    value = Leadership(database, cluster_id='test-cluster', owner_id='controller-test')
    value.acquire()
    value.reconciled()
    try:
        yield value
    finally:
        value.close()


def test_same_key_concurrent_admission_is_one_transaction(database):
    repository = ClusterRepository(database)
    frozen = plan()
    with ThreadPoolExecutor(max_workers=6) as executor:
        receipts = list(executor.map(lambda _: repository.submit(principal='alice', request_id='one', plan=frozen), range(6)))
    assert all(receipt == receipts[0] for receipt in receipts)
    with database.connection() as connection:
        assert connection.execute('SELECT count(*) AS n FROM runs').fetchone()['n'] == 1
        assert connection.execute('SELECT count(*) AS n FROM outbox').fetchone()['n'] == 1
        usage = connection.execute('SELECT * FROM quota_usage').fetchone()
        assert usage['runs'] == usage['units'] == usage['retained_requests'] == 1


def test_replay_precedes_quota_and_conflict_is_explicit(database):
    repository = ClusterRepository(database, limits=AdmissionLimits(runs=1))
    frozen = plan()
    receipt = repository.submit(principal='alice', request_id='one', plan=frozen)
    assert repository.submit(principal='alice', request_id='one', plan=frozen) == receipt
    with pytest.raises(BusyError):
        repository.submit(principal='alice', request_id='two', plan=frozen)
    changed = frozen.model_copy(update={'parameters_digest': 'c' * 64}).with_identity()
    with pytest.raises(IdempotencyConflictError):
        repository.submit(principal='alice', request_id='one', plan=changed)
    assert repository.request('alice', 'two') is None


def test_real_rollback_leaves_no_admission(database):
    def transaction(connection):
        connection.execute("INSERT INTO requests(principal,request_id,digest,receipt) VALUES ('a','b','c','{}')")
        raise RuntimeError('Injected before commit')
    with pytest.raises(RuntimeError):
        database.transaction(transaction)
    assert ClusterRepository(database).request('a', 'b') is None


def test_lost_commit_reply_requires_lookup_of_real_committed_receipt(database, monkeypatch):
    """Fault injection drops the reply AFTER PostgreSQL actually commits."""
    original = database.connection
    class LostReply:
        def __init__(self, connection): self.connection = connection
        def execute(self, *args, **kwargs): return self.connection.execute(*args, **kwargs)
        @contextmanager
        def transaction(self):
            with self.connection.transaction():
                yield
            raise database.psycopg.OperationalError('Injected lost COMMIT reply')
    @contextmanager
    def connection(lane='ordinary'):
        with original(lane) as raw:
            yield LostReply(raw)
    monkeypatch.setattr(database, 'connection', connection)
    repository = ClusterRepository(database)
    with pytest.raises(CommitOutcomeUnknown):
        repository.submit(principal='alice', request_id='lost', plan=plan())
    monkeypatch.setattr(database, 'connection', original)
    receipt = repository.request('alice', 'lost')
    assert receipt is not None
    assert repository.submit(principal='alice', request_id='lost', plan=plan()) == receipt


def test_migration_checksum_and_newer_binary_guard(database, tmp_path):
    source = Path(__file__).parents[1] / 'operon' / 'cluster' / 'migrations'
    for migration in source.glob('*.sql'):
        (tmp_path / migration.name).write_bytes(migration.read_bytes() + b'\n-- changed\n')
    with pytest.raises(ClusterError, match='checksum'):
        database.migrate(tmp_path)
    assert database.migrate() == ('0001_cluster.sql',)


def test_leadership_is_dedicated_exclusive_and_epoch_is_durable(database, leader):
    contender = Leadership(database, cluster_id='test-cluster', owner_id='controller-two')
    with pytest.raises(LeadershipLost):
        contender.acquire()
    first = leader.epoch
    leader.close()
    try:
        assert contender.acquire() == first + 1
        with pytest.raises(LeadershipLost): contender.assert_current()
        contender.reconciled()
        contender.assert_current()
    finally:
        contender.close()


def test_lost_submit_receipt_is_pinned_to_same_host_and_key(database, leader):
    repository = ClusterRepository(database)
    receipt = repository.submit(principal='alice', request_id='one', plan=plan())
    repository.register_node(node_id='host1', capacity_domain='physical1', executor='ssh', inventory={})
    repository.heartbeat('host1', observed_pool_epoch=7)
    command = repository.prepare_dispatch(run_id=receipt['run_id'], unit_id='unit', node_id='host1',
        executor='ssh', controller_id='cluster', epoch=leader.epoch, expected_revision=1,
        payload={'workspace': '/test', 'graph': {}})
    dispatch = repository.claim_dispatch(command, epoch=leader.epoch)
    assert dispatch.request_key and repository.claim_dispatch(command, epoch=leader.epoch) is None
    repository.recovery_barrier(epoch=leader.epoch)
    recovered, = repository.dispatches()
    assert (recovered.node_id, recovered.request_key) == ('host1', dispatch.request_key)
    assert recovered.phase == 'submission_unknown'
    repository.observe(recovered, Observation('recovery_required', 'host_offline'), epoch=leader.epoch)
    with pytest.raises(StaleRevisionError):
        repository.prepare_dispatch(run_id=receipt['run_id'], unit_id='unit', node_id='host1', executor='ssh',
            controller_id='cluster', epoch=leader.epoch, expected_revision=3, payload={})


def test_cancel_unstarted_run_releases_quota_but_preserves_request(database):
    repository = ClusterRepository(database, limits=AdmissionLimits(runs=1))
    receipt = repository.submit(principal='alice', request_id='one', plan=plan())
    assert repository.cancel('alice', receipt['run_id'])['state'] == 'cancelled'
    assert repository.request('alice', 'one') == receipt
    repository.submit(principal='alice', request_id='two', plan=plan())


def test_database_lifecycle_capacity_is_reserved(database):
    from contextlib import ExitStack
    with ExitStack() as stack:
        for _ in range(6): stack.enter_context(database.connection('ordinary'))
        with pytest.raises(BusyError):
            with database.connection('ordinary'): pass
        with database.connection('lifecycle') as connection:
            assert connection.execute('SELECT 1 AS n').fetchone()['n'] == 1


def test_committed_cancel_intent_prevents_pending_external_dispatch(database, leader):
    repository = ClusterRepository(database)
    receipt = repository.submit(principal='alice', request_id='cancel-pending', plan=plan())
    repository.register_node(node_id='host1', capacity_domain='physical1', executor='ssh', inventory={})
    repository.heartbeat('host1', observed_pool_epoch=7)
    command = repository.prepare_dispatch(run_id=receipt['run_id'], unit_id='unit', node_id='host1',
        executor='ssh', controller_id='cluster', epoch=leader.epoch, expected_revision=1,
        payload={'workspace': '/test', 'graph': {}})
    assert repository.cancel('alice', receipt['run_id'])['state'] == 'cancel_requested'
    assert repository.claim_dispatch(command, epoch=leader.epoch) is None
    cancellation, = repository.cancellations()
    assert cancellation.phase == 'pending' and cancellation.external_handle is None


def test_producer_receipt_query_is_same_principal_run_and_committed_only(database, leader):
    """Actual PostgreSQL query/state gate; executor receipt is a synthetic fixture."""
    from test_cluster_consumer import template
    repository = ClusterRepository(database)
    source = template().source_plan
    run = repository.submit(principal='alice', request_id='producer-query', plan=source)['run_id']
    repository.register_node(node_id='node', capacity_domain='physical1', executor='ssh', inventory={})
    repository.heartbeat('node', observed_pool_epoch=2)
    command = repository.prepare_dispatch(run_id=run, unit_id='parent', node_id='node', executor='ssh',
        controller_id='controller', epoch=leader.epoch, expected_revision=1, payload={'workspace': '/test'})
    dispatch = repository.claim_dispatch(command, epoch=leader.epoch)
    assert repository.producer_receipts('alice', run, ['parent']) == []
    evidence = {'artifact_committed': True, 'artifact': {'artifact_id': 'fixture', 'digest': 'd' * 64}}
    import json
    repository.observe(dispatch, Observation('succeeded', 'fixture-complete', 'host-run', 4,
        json.dumps(evidence), stop_confirmed=True), epoch=leader.epoch)
    row, = repository.producer_receipts('alice', run, ['parent'])
    assert row['request_key'] == dispatch.request_key and row['external_handle'] == 'host-run'
    assert row['plan_id'] == source.plan_id and row['spec'] == source.units[0].model_dump(mode='json')
    assert row['unit_state'] == row['state'] == 'succeeded'
    assert repository.producer_receipts('bob', run, ['parent']) == []
    assert repository.producer_receipts('alice', 'different-run', ['parent']) == []
    assert repository.producer_receipts('alice', run, ['unit']) == []
    with pytest.raises(ValueError):
        repository.producer_receipts('alice', run, [str(i) for i in range(129)])
