"""Zero means unlimited, not invalid."""

import pytest

from src.web.execution_plan import (
    DEFAULT_PARALLEL_TASKS,
    default_parallel_tasks,
    set_default_parallel_tasks,
)
from src.web.preferences import Preferences


def test_preferences_accepts_unlimited():
    assert Preferences.model_validate({'parallel_tasks': 0}).parallel_tasks == 0
    assert Preferences.model_validate({'parallel_tasks': 64}).parallel_tasks == 64
    with pytest.raises(Exception):
        Preferences.model_validate({'parallel_tasks': -1})


def test_default_parallel_tasks_keeps_zero():
    try:
        set_default_parallel_tasks(0)
        assert default_parallel_tasks() == 0
        set_default_parallel_tasks(5)
        assert default_parallel_tasks() == 5
    finally:
        set_default_parallel_tasks(None)
    assert default_parallel_tasks() == DEFAULT_PARALLEL_TASKS
