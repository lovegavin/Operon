"""The pool ceiling must leave room for the reservation admission grants."""

from types import SimpleNamespace

from operon.engine.facade import management_reserve, pool_from_host

MIB = 1024 * 1024


def test_admission_driven_pool_schedules_the_whole_frozen_capacity(tmp_path):
    admission = SimpleNamespace(capacity=1843 * MIB, cpus=2)
    spec = pool_from_host(root=tmp_path, admission=admission)
    assert spec.ceiling_bytes == 1843 * MIB
    assert spec.management_reserve_bytes == 0
    # A single slot may reserve the whole admission capacity; that reservation
    # has to fit inside the ceiling the coordinator compares against.
    assert spec.schedulable_bytes == admission.capacity


def test_a_plain_pool_keeps_its_management_reserve(tmp_path):
    ceiling = 4096 * MIB
    spec = pool_from_host(root=tmp_path, ceiling_bytes=ceiling)
    assert spec.management_reserve_bytes == management_reserve(ceiling)
    assert spec.schedulable_bytes == ceiling - management_reserve(ceiling)
