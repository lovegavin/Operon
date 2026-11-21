"""A rejected runtime.memory.keep reports the value it saw."""
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
