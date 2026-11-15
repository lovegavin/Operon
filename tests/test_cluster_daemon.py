"""Configured lifecycle fixtures; no SSH, PostgreSQL or Slurm acceptance claim."""
from contextlib import contextmanager
import hashlib
import json
import threading
from types import SimpleNamespace

import pytest

from operon.cluster import daemon
from operon.cluster.daemon import ControllerSettings, ConfiguredPlanner, TransportLeases
from operon.contracts.base import sha256_hex
from test_cluster_invocation import source_plan, binding


def configuration():
    return {'principal': 'alice', 'cluster_id': 'cluster', 'controller_id': 'controller',
        'nodes': [{'node_id': 'node', 'capacity_domain': 'host:fixture', 'executor': 'ssh',
            'host_identity': 'pool-fixture', 'target': {'os': 'linux', 'arch': 'x86_64'},
            'ssh': {'host': 'fixture.invalid', 'username': 'alice',
                'host_key': {'type': 'ssh-ed25519', 'base64': 'fixture'},
                'app_dir': '/opt/operon', 'workspace': '/work/alice'}}]}


def test_configuration_rejects_inline_secret_and_alias_capacity():
    raw = configuration()
    raw['nodes'][0]['ssh']['password'] = 'not-permitted'
    with pytest.raises(ValueError):
        ControllerSettings.model_validate(raw)
    raw = configuration()
    raw['nodes'].append({**raw['nodes'][0], 'node_id': 'alias'})
    with pytest.raises(ValueError, match='capacity domains'):
        ControllerSettings.model_validate(raw)


def test_secret_environment_provider_is_explicit_and_required(monkeypatch):
    raw = configuration()
    raw['nodes'][0]['ssh'].update(auth='password', password_environment='OPERON_TEST_CLUSTER_SECRET')
    settings = ControllerSettings.model_validate(raw).nodes[0].ssh
    monkeypatch.delenv('OPERON_TEST_CLUSTER_SECRET', raising=False)
    with pytest.raises(Exception) as failure:
        TransportLeases._secrets(settings)
    assert failure.value.code == 'secret_unavailable'
    monkeypatch.setenv('OPERON_TEST_CLUSTER_SECRET', 'fixture-secret')
    assert TransportLeases._secrets(settings) == {'password': 'fixture-secret'}


def test_prepared_payload_hash_and_frozen_unit_must_match(tmp_path):
    raw = configuration()
    payload = tmp_path / 'payload.json'
    source = source_plan()
    encoded = json.dumps({'workspace': '/work/alice', 'source_plan': source.model_dump(mode='json'),
                          'source_unit_id': 'unit', 'binding': binding()}).encode()
    payload.write_bytes(encoded)
    spec = source.units[0].model_dump(mode='json')
    raw['prepared'] = [{'run_id': 'run', 'unit_id': 'unit', 'node_id': 'node',
        'spec_digest': sha256_hex(spec), 'payload_file': 'payload.json',
        'payload_sha256': hashlib.sha256(encoded).hexdigest(), 'binding_id': 'binding'}]
    settings = ControllerSettings.model_validate(raw)
    planner = ConfiguredPlanner(settings, directory=tmp_path)
    assert not planner.planner.prepared
    planner.validate(SimpleNamespace(unit_spec=lambda *_: spec, status=lambda *_: {'plan_id': source.plan_id}))
    assert ('run', 'unit', 'node') in planner.planner.prepared
    with pytest.raises(Exception) as failure:
        planner.validate(SimpleNamespace(unit_spec=lambda *_: {'different': True}, status=lambda *_: {'plan_id': source.plan_id}))
    assert failure.value.code == 'artifact_mismatch'
    payload.write_bytes(encoded + b' ')
    with pytest.raises(ValueError, match='checksum'):
        ConfiguredPlanner(settings, directory=tmp_path)


def test_template_is_ready_before_admission_and_selected_by_source_plan_id(tmp_path):
    from datetime import datetime, timezone
    source = source_plan()
    raw = configuration()
    raw['nodes'][0]['environments'] = ['runtime']
    encoded = json.dumps({'workspace': '/work/alice', 'source_plan': source.model_dump(mode='json'),
                          'source_unit_id': 'unit', 'binding': binding()}).encode()
    (tmp_path / 'template.json').write_bytes(encoded)
    raw['prepared'] = [{'plan_id': source.plan_id, 'unit_id': 'unit', 'node_id': 'node',
        'spec_digest': sha256_hex(source.units[0]), 'payload_file': 'template.json',
        'payload_sha256': hashlib.sha256(encoded).hexdigest(), 'binding_id': 'binding'}]
    planner = ConfiguredPlanner(ControllerSettings.model_validate(raw), directory=tmp_path)
    planner.validate(object())  # No run or DB lookup exists at template provisioning time.
    assert planner.planner.prepared == {}
    stamp = datetime.now(timezone.utc)
    ready = [{'run_id': 'newly-admitted', 'unit_id': 'unit', 'plan_id': source.plan_id,
              'principal': 'alice', 'created_at': stamp, 'revision': 1, 'spec': source.units[0].model_dump(mode='json')}]
    nodes = [{'node_id': 'node', 'executor': 'ssh', 'health': 'healthy', 'heartbeat_at': stamp,
              'inventory': {'os': 'linux', 'arch': 'x86_64', 'environments': ['runtime']}}]
    decision, = planner(ready, nodes)
    assert decision['run_id'] == 'newly-admitted'
    assert decision['payload']['plan']['units'][0]['placement']['executor'] == 'local'
    assert decision['payload']['source_plan_id'] == source.plan_id
    assert 'graph' not in decision['payload']
    ready[0]['plan_id'] = 'different-plan'
    assert list(planner(ready, nodes)) == []


def test_dependent_template_waits_for_current_run_producer_identities(tmp_path):
    from test_cluster_consumer import template
    source = template().source_plan
    raw = configuration()
    encoded = json.dumps({'workspace': '/work/alice', 'source_plan': source.model_dump(mode='json'),
                          'source_unit_id': 'unit', 'binding': binding()}).encode()
    (tmp_path / 'consumer.json').write_bytes(encoded)
    raw['prepared'] = [{'plan_id': source.plan_id, 'unit_id': 'unit', 'node_id': 'node',
        'spec_digest': sha256_hex(source.units[1]), 'payload_file': 'consumer.json',
        'payload_sha256': hashlib.sha256(encoded).hexdigest(), 'binding_id': 'binding'}]
    planner = ConfiguredPlanner(ControllerSettings.model_validate(raw), directory=tmp_path)
    planner.validate(object())
    value = json.loads(planner.templates[(source.plan_id, 'unit', 'node')].payload_json)
    assert value['format'] == 'operon.cluster-consumer-template'
    assert value['source_plan']['plan_id'] == source.plan_id
    assert value['binding']['inputs'] == {} and 'producers' not in value
    assert value['target_host_identity'] == 'pool-fixture'
    assert planner.consumer_nodes == {'node'}


@pytest.mark.parametrize('capable', [True, False])
def test_explicit_serve_acquires_leadership_probes_and_cleans_up(tmp_path, monkeypatch, capable):
    log = []
    settings = ControllerSettings.model_validate(configuration())

    class Repository:
        def __init__(self, database): pass
        def register_node(self, **kwargs): log.append('register')
        def heartbeat(self, node_id, **kwargs): log.append(kwargs.get('health', 'healthy'))

    class Leadership:
        epoch = 1
        owner_id = 'owner'
        def __init__(self, *args, **kwargs): pass
        def acquire(self): log.append('leadership')
        def assert_current(self, **kwargs): pass

    class Transports:
        def __init__(self, nodes): pass
        @contextmanager
        def lease(self, node_id, lane):
            def call(method, params):
                assert method == 'cluster.lookup'
                assert params['controller_epoch'] == 1
                log.append('lookup-only')
                return {'host_identity': 'pool-fixture', 'capacity_domain': 'host:fixture',
                        'target': {'os': 'linux', 'arch': 'x86_64'}, 'host_pool_epoch': 9}
            yield SimpleNamespace(supports=lambda _: capable, call=call)
        def close(self): log.append('transport-close')

    class Controller:
        def __init__(self, repository, leadership, **kwargs): self.leadership = leadership
        def start(self, *, prepare):
            self.leadership.acquire()
            prepare()
            log.append('scheduler-start')
        def request_stop(self): log.append('stop-intent')
        def stop(self): log.append('controller-close')

    monkeypatch.setattr(daemon, 'ClusterRepository', Repository)
    monkeypatch.setattr(daemon, 'Leadership', Leadership)
    monkeypatch.setattr(daemon, 'TransportLeases', Transports)
    monkeypatch.setattr(daemon, 'ClusterController', Controller)
    stop = threading.Event()
    stop.set()
    if capable:
        assert daemon.serve(settings, object(), directory=tmp_path, stop_event=stop)['state'] == 'stopped'
        assert log.index('leadership') < log.index('lookup-only') < log.index('scheduler-start')
    else:
        with pytest.raises(Exception) as failure:
            daemon.serve(settings, object(), directory=tmp_path, stop_event=stop)
        assert failure.value.code == 'capability_unavailable'
        assert 'scheduler-start' not in log
        assert 'offline' in log
    assert log[-3:] == ['stop-intent', 'transport-close', 'controller-close']
