"""A declared path parameter falls back to this host when the target lacks it."""
from pathlib import Path

import pytest

from src.web.execution_plan import resolve_reference

SSH = {'kind': 'ssh', 'profile_id': 'abc'}


def statter(hosts):
    """Return a stat callback that knows only the listed hosts."""
    def stat(location, path, base):
        if location.get('kind') in hosts:
            return 12
        raise FileNotFoundError(path)
    return stat


def test_a_missing_remote_file_is_read_from_this_host():
    assert resolve_reference(SSH, 'toy.pdb', '.', statter({'local'})) == {'kind': 'local'}


def test_a_present_remote_file_keeps_the_remote_host():
    assert resolve_reference(SSH, 'toy.pdb', '.', statter({'ssh'})) == SSH


def test_a_file_missing_everywhere_stays_on_the_target():
    assert resolve_reference(SSH, 'gone.pdb', '.', statter(set())) == SSH


def test_a_pinned_location_is_never_rewritten():
    assert resolve_reference(SSH, 'toy.pdb', '.', statter({'local'}), pinned=True) == SSH


def test_a_local_target_is_returned_unchanged():
    assert resolve_reference({'kind': 'local'}, 'toy.pdb', '.', statter({'local'})) == {'kind': 'local'}


def test_a_failing_stat_callback_is_not_fatal():
    def stat(location, path, base):
        raise ValueError('bad base dir')
    assert resolve_reference(SSH, 'toy.pdb', '.', stat) == SSH
