"""All workspaces of one principal share one durable pool by default."""
import os
from pathlib import Path

from src.web.operator_catalog import catalog_from_descriptors
from src.web.service import JobService, Settings
from operon.engine.facade import EngineRuntime

ROOT = Path(__file__).resolve().parents[1]


def test_scheduling_principal_does_not_change_the_physical_pool(tmp_path, monkeypatch):
    shared = tmp_path / 'control'
    first_root, second_root = tmp_path / 'alice', tmp_path / 'bob'
    first_root.mkdir(); second_root.mkdir()
    monkeypatch.setenv('OPERON_ENGINE_PRINCIPAL', 'alice')
    alice = EngineRuntime.open(data_dir=shared, workspace_root=first_root, mode='shadow',
                               ceiling_bytes=64 * 1024 * 1024, cpu_threads=2)
    monkeypatch.setenv('OPERON_ENGINE_PRINCIPAL', 'bob')
    bob = EngineRuntime.open(data_dir=shared, workspace_root=second_root, mode='shadow',
                             ceiling_bytes=64 * 1024 * 1024, cpu_threads=2)
    try:
        assert alice.principal == 'alice' and bob.principal == 'bob'
        assert alice.spec.pool_id == bob.spec.pool_id
        assert alice.spec.principal == bob.spec.principal  # OS owner, not fairness label
        assert alice.spec.ceiling_bytes == bob.spec.ceiling_bytes
    finally:
        alice.close(); bob.close()


def test_two_workspaces_share_the_pool_and_lease_ledger(tmp_path, monkeypatch):
    admission = tmp_path / 'admission'
    monkeypatch.setenv('OPERON_ADMISSION_DIR', str(admission))
    monkeypatch.delenv('OPERON_ENGINE_DIR', raising=False)
    first_root, second_root = tmp_path / 'first', tmp_path / 'second'
    first_root.mkdir(); second_root.mkdir()
    first = JobService(Settings(first_root, first_root / '.studio', first_root / 'ui',
                                testing=True, code_root=ROOT, admission_dir=admission),
                       catalog_from_descriptors())
    second = JobService(Settings(second_root, second_root / '.studio', second_root / 'ui',
                                 testing=True, code_root=ROOT, admission_dir=admission),
                        catalog_from_descriptors())
    try:
        assert first.engine.spec.pool_id == second.engine.spec.pool_id
        assert Path(first.engine.store.path) == Path(second.engine.store.path)
        assert Path(first.engine.store.path).is_relative_to(admission)
        assert first.engine.workspace_id != second.engine.workspace_id
        workspaces = first.engine.store.connection.execute(
            'SELECT workspace_id, root FROM workspaces WHERE pool_id=?',
            (first.engine.spec.pool_id,)).fetchall()
        assert len({row['workspace_id'] for row in workspaces}) == 2
        # The durable pool ceiling is identical in both workspaces and is not
        # recalculated from a fresh free-memory scan.
        assert first.engine.spec.ceiling_bytes == second.engine.spec.ceiling_bytes
    finally:
        first.shutdown()
        second.shutdown()
