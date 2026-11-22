"""A registration without an explicit library keeps the running binding."""
from pathlib import Path

from operon.pool_service import _registration_binding


def test_omitted_library_keeps_the_bound_policy():
    library, policy = _registration_binding(
        explicit_library=False, library_root=Path('/app/library'),
        previous_library=Path('/deploy/library'), requested_manifest=True)
    assert library == Path('/deploy/library')
    assert policy is False


def test_explicit_library_still_changes_the_binding():
    library, policy = _registration_binding(
        explicit_library=True, library_root=Path('/app/library'),
        previous_library=Path('/deploy/library'), requested_manifest=True)
    assert library == Path('/app/library')
    assert policy is False


def test_manifest_only_policy_survives_without_a_library():
    library, policy = _registration_binding(
        explicit_library=False, library_root=None,
        previous_library=None, requested_manifest=True)
    assert library is None
    assert policy is True
