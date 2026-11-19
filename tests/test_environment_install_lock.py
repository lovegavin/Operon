"""Cross-process installation slot behaviour."""

from __future__ import annotations

import threading
import time

import pytest

from operon import environment_install


def test_slot_is_exclusive_within_a_process(tmp_path):
    order: list[str] = []
    release = threading.Event()

    def holder() -> None:
        environment_install._acquire_slot(environment_install._Control(), tmp_path)
        order.append('first')
        release.wait(10)
        environment_install._release_slot()

    thread = threading.Thread(target=holder)
    thread.start()
    time.sleep(0.3)
    acquired = threading.Event()

    def second() -> None:
        environment_install._acquire_slot(environment_install._Control(), tmp_path)
        order.append('second')
        acquired.set()
        environment_install._release_slot()

    waiter = threading.Thread(target=second)
    waiter.start()
    try:
        assert not acquired.wait(0.8), 'second installer acquired the slot while it was busy'
        release.set()
        assert acquired.wait(10), 'second installer never acquired the released slot'
    finally:
        release.set()
        thread.join(15)
        waiter.join(15)
    assert order == ['first', 'second']


def test_slot_is_backed_by_a_file_lock(tmp_path):
    environment_install._acquire_slot(environment_install._Control(), tmp_path)
    handle = environment_install._LOCK_STATE.get('handle')
    assert handle is not None
    assert (tmp_path / environment_install._INSTALL_LOCK).exists()
    environment_install._release_slot()
    assert environment_install._LOCK_STATE.get('handle') is None


def test_cancelled_waiter_releases_the_slot(tmp_path, monkeypatch):
    control = environment_install._Control()

    def busy(handle):  # noqa: ANN001 - test double
        raise OSError('locked')

    monkeypatch.setattr(environment_install, '_lock_handle', busy)
    threading.Timer(0.4, control.stop).start()
    with pytest.raises(environment_install.Cancelled):
        environment_install._acquire_slot(control, tmp_path)
    # The slot must be free again: a fresh acquire returns promptly.
    environment_install._acquire_slot(environment_install._Control(), tmp_path)
    environment_install._release_slot()

def test_distinct_roots_do_not_share_the_in_process_slot(tmp_path):
    from operon import environment_install

    local = tmp_path / 'local'
    remote = tmp_path / 'remote'
    environment_install._acquire_slot(environment_install._Control(), local)
    try:
        thread = threading.Thread(
            target=lambda: environment_install._acquire_slot(environment_install._Control(), remote),
            daemon=True,
        )
        thread.start()
        thread.join(5.0)
        assert not thread.is_alive(), 'a second root must not wait for the first root slot'
        environment_install._release_slot()
    finally:
        environment_install._release_slot()
