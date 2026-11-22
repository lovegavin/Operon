"""A pool authority failure must reach clients as something they can act on."""

from operon.application import _pool_error


class _PoolError(Exception):
    code = 'pool_upgrade_required'


def test_a_pool_upgrade_is_retryable():
    error = _pool_error(_PoolError('Another Operon version still has active tasks'))
    assert error.code == 'pool_busy'
    assert error.status == 503
    assert error.details['retryable'] is True
    assert 'still has active tasks' in error.details['reason']


def test_another_pool_failure_stays_engine_unavailable():
    error = _pool_error(RuntimeError('socket closed'))
    assert error.code == 'engine_unavailable'
    assert 'retryable' not in error.details
    assert 'socket closed' in error.details['reason']
