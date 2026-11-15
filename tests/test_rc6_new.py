import json
import os
from pathlib import Path

import pytest

from operon.script_operators import inspect_source, validate_script, _apply_library_path

ROOT = Path(__file__).resolve().parents[1]


def test_script_timeout_comment_is_frozen():
    snapshot = inspect_source(
        'run.py',
        '# timeout: 90\n# input: table file.csv\nprint(1)\n',
    )
    assert snapshot['timeout'] == 90
    assert validate_script(snapshot)['timeout'] == 90


def test_script_timeout_defaults_and_rejects_out_of_range():
    snapshot = inspect_source('run.py', 'print(1)\n')
    assert snapshot['timeout'] == 3600
    with pytest.raises(ValueError):
        validate_script({**snapshot, 'timeout': 0})
    with pytest.raises(ValueError):
        validate_script({**snapshot, 'timeout': 86401})


def test_library_path_exposes_isolated_prefix(tmp_path):
    prefix = tmp_path / 'env'
    (prefix / 'lib').mkdir(parents=True)
    binary = prefix / 'bin' / 'python'
    binary.parent.mkdir()
    binary.write_text('')
    env = {'LD_LIBRARY_PATH': '/host/lib'}
    _apply_library_path(env, str(binary))
    first = env['LD_LIBRARY_PATH'].split(os.pathsep)
    assert first[0] == str(prefix / 'lib')
    assert first[-1] == '/host/lib'


def test_boltz_environment_is_pure_wheel_with_pinned_cuda_torch():
    document = json.loads((ROOT / 'library/seed/operon/environments.json').read_text())
    boltz = document['environments']['boltz']
    assert boltz['conda_packages'] == []
    assert boltz['torch_cuda'] is True
    assert boltz['torch_index_url'].endswith('/cu121')
    assert boltz['torch_version'] == '2.3.1'
    assert 'libstdcxx-ng' not in json.dumps(boltz)
    assert 'omegaconf==2.3.0' in boltz['pip_wheels']
    assert 'antlr4-python3-runtime==4.9.3' in boltz['pip_pypi']
    assert not any(item.startswith('omegaconf') for item in boltz['pip_wheels'] if item != 'omegaconf==2.3.0')
