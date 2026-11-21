"""A rejected runtime.memory.keep reports the value it saw, and frozen tuples pass."""
import pytest

from src.core.errors.errors import ManifestError
from src.task.memory.config import MemoryConfig


@pytest.mark.parametrize('keep', ['pca', {'pca': 1}, [1, 2]])
def test_keep_rejection_names_the_offending_value(keep):
    manifest = {'runtime': {'memory': {'enabled': True, 'keep': keep}}}
    with pytest.raises(ManifestError) as excinfo:
        MemoryConfig.parse(manifest, detect_available=False)
    assert 'must be a list of form names' in str(excinfo.value)
    assert repr(keep) in str(excinfo.value)


@pytest.mark.parametrize('keep, expected', [((), []), (('pca',), ['pca']), (['pca'], ['pca'])])
def test_keep_accepts_frozen_sequences_and_normalises_to_a_list(keep, expected):
    manifest = {'runtime': {'memory': {'enabled': True, 'keep': keep}}}
    config = MemoryConfig.parse(manifest, detect_available=False)
    assert config.keep == expected
    assert isinstance(config.keep, list)
