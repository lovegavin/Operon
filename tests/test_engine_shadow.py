"""Shadow mode computes pool decisions without taking admission authority."""
import json

from src.web.operator_catalog import catalog_from_descriptors
from src.web.service import JobService, Settings

ROOT = __import__('pathlib').Path(__file__).resolve().parents[1]


def test_shadow_decision_is_durable_and_creates_no_lease(tmp_path):
    service = JobService(Settings(tmp_path, tmp_path / '.studio', tmp_path / 'ui', testing=True,
                                  code_root=ROOT, engine_mode='shadow'),
                         catalog_from_descriptors())
    try:
        job = {'id': 'job-shadow', 'allocation': {'budget_bytes': 1024, 'reserved_bytes': 2048,
                                                  'cpu_threads': 1}}
        service._shadow_decision(job)
        assert service.shadow_decisions == 1
        page = service.engine.journal.page(0)
        events = [event for event in page.events if event['kind'] == 'job:shadow_decision']
        assert events and events[-1]['payload']['would_admit'] is True
        assert service.engine.store.active_leases(service.engine.spec.pool_id) == []
        assert service.resources()['engine']['shadow_decisions'] == 1
    finally:
        service.shutdown()
