from pathlib import Path

import pytest

from operon import environment_install
from src.web.admission import HostAdmission


def _manifest(steps=1, gpu=0, device=None):
    params = {} if device is None else {'device': device}
    return {
        'runtime': {'memory': {'enabled': True, 'budget_mb': 16}, 'execution': {'gpu_count': gpu}},
        'steps': [{'params': dict(params)} for _ in range(steps)],
    }


def test_gpu_reservation_assigns_visible_device(tmp_path):
    admission = HostAdmission(tmp_path, available_bytes=1024 ** 3, cpu_threads=8, gpu_devices=2)
    allocation = admission.request(_manifest(steps=41, gpu=1))
    assert allocation['gpu_count'] == 1
    assert allocation['cpu_threads'] == 5
    assert admission.reserve('gpu-job', allocation)
    assert allocation['gpu_devices'] == [0]

    other = HostAdmission(tmp_path, available_bytes=1024 ** 3, cpu_threads=8, gpu_devices=2)
    second = other.request(_manifest(steps=1, gpu=1))
    assert other.reserve('second-gpu-job', second)
    assert second['gpu_devices'] == [1]

    third = HostAdmission(tmp_path, available_bytes=1024 ** 3, cpu_threads=8, gpu_devices=2)
    assert not third.reserve('third-gpu-job', third.request(_manifest(steps=1, gpu=1)))


def test_gpu_request_rejected_when_none_visible(tmp_path):
    admission = HostAdmission(tmp_path, available_bytes=1024 ** 3, cpu_threads=8, gpu_devices=0)
    with pytest.raises(ValueError, match='only 0 are visible'):
        admission.request(_manifest(gpu=1))


def test_difficulty_threads_without_gpu(tmp_path):
    admission = HostAdmission(tmp_path, available_bytes=1024 ** 3, cpu_threads=8, gpu_devices=0)
    assert admission.request(_manifest(steps=41))['cpu_threads'] == 3
    assert admission.request(_manifest(steps=1))['cpu_threads'] == 1


def test_environment_validation_cuda():
    environment_install._validate({'torch_cuda': True, 'torch_index_url': 'https://download.pytorch.org/whl/cu121', 'gpu_count': 1})
    with pytest.raises(ValueError, match='mutually exclusive'):
        environment_install._validate({'torch_cuda': True, 'torch_cpu': True})
    with pytest.raises(ValueError, match='https URL'):
        environment_install._validate({'torch_index_url': 'http://example.invalid/cuda'})


def test_install_uses_cuda_index(monkeypatch):
    calls = []
    monkeypatch.setattr(environment_install, '_python', lambda staging: Path('python'))
    monkeypatch.setattr(environment_install, '_run', lambda command, **kwargs: calls.append(command))
    environment_install._install({'torch_cuda': True, 'torch_version': '2.3.1',
                                  'torch_index_url': 'https://download.pytorch.org/whl/cu121'}, Path('env'), lambda line: None)
    torch_command = [command for command in calls if 'torch==2.3.1' in command][0]
    assert 'https://download.pytorch.org/whl/cu121' in torch_command


def test_probe_asserts_cuda(monkeypatch):
    calls = []
    monkeypatch.setattr(environment_install, '_run', lambda command, **kwargs: calls.append(command))
    environment_install._probe(Path('python'), {'imports': ['torch'], 'torch_cuda': True}, print)
    assert 'torch.cuda.is_available()' in calls[0][-1]
