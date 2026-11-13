"""Task scaffold and backend-mediated text/binary writes inside the workspace."""
import base64
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from operon.documents import CommandError
from operon.task_files import DEFAULT_FOLDERS, MAX_BINARY_BYTES, MAX_TEXT_BYTES, scaffold, write_binary, write_text
from src.web.api import create_app
from src.web.service import Settings

ROOT = Path(__file__).resolve().parents[1]


def studio(tmp_path):
    return create_app(Settings(tmp_path, tmp_path / 'studio', ROOT / 'frontend/dist',
                               testing=True, code_root=ROOT, desktop=True))


def test_scaffold_creates_default_task_folders(tmp_path):
    root = tmp_path / 'workspace'
    root.mkdir()
    result = scaffold(root, 'task1')
    assert result['base_dir'] == 'task1'
    assert result['folders'] == ['task1/' + name for name in DEFAULT_FOLDERS]
    assert set(result['created']) == {'task1', 'task1/input', 'task1/results', 'task1/reports', 'task1/figures'}
    for name in DEFAULT_FOLDERS:
        assert (root / 'task1' / name).is_dir()


def test_scaffold_supports_nested_base_and_custom_folders(tmp_path):
    root = tmp_path / 'workspace'
    root.mkdir()
    result = scaffold(root, 'project/task2', ['input', 'reports'])
    assert result['folders'] == ['project/task2/input', 'project/task2/reports']
    assert (root / 'project/task2/input').is_dir()
    assert not (root / 'project/task2/results').exists()


@pytest.mark.parametrize('value', ['', '  ', '../escape', '/absolute', 'C:/absolute', '.studio/jobs', '.operon', 'a/../b'])
def test_scaffold_rejects_unsafe_base_dirs(tmp_path, value):
    root = tmp_path / 'workspace'
    root.mkdir()
    with pytest.raises(CommandError):
        scaffold(root, value)


def test_scaffold_rejects_file_conflict(tmp_path):
    root = tmp_path / 'workspace'
    (root / 'task1').mkdir(parents=True)
    (root / 'task1' / 'input').write_text('occupied', encoding='utf-8')
    with pytest.raises(CommandError) as error:
        scaffold(root, 'task1')
    assert error.value.code == 'invalid_folder'


def test_write_text_creates_parents_and_reports_bytes(tmp_path):
    root = tmp_path / 'workspace'
    root.mkdir()
    result = write_text(root, 'task1/reports/summary.md', 'hello 世界\n')
    assert result['path'] == 'task1/reports/summary.md'
    assert result['bytes'] == len('hello 世界\n'.encode('utf-8'))
    assert result['created'] is True
    assert (root / 'task1/reports/summary.md').read_text(encoding='utf-8') == 'hello 世界\n'


def test_write_text_respects_overwrite(tmp_path):
    root = tmp_path / 'workspace'
    root.mkdir()
    write_text(root, 'task1/notes.txt', 'first')
    with pytest.raises(CommandError) as error:
        write_text(root, 'task1/notes.txt', 'second', overwrite=False)
    assert error.value.code == 'file_exists'
    assert (root / 'task1/notes.txt').read_text(encoding='utf-8') == 'first'
    result = write_text(root, 'task1/notes.txt', 'second')
    assert result['created'] is False
    assert (root / 'task1/notes.txt').read_text(encoding='utf-8') == 'second'


@pytest.mark.parametrize('value', ['../escape.txt', '/etc/passwd', 'C:/secret.txt', '.studio/config.json'])
def test_write_text_rejects_unsafe_paths(tmp_path, value):
    root = tmp_path / 'workspace'
    root.mkdir()
    with pytest.raises(CommandError):
        write_text(root, value, 'nope')


def test_write_text_rejects_oversized_content(tmp_path):
    root = tmp_path / 'workspace'
    root.mkdir()
    with pytest.raises(CommandError) as error:
        write_text(root, 'task1/big.txt', 'x' * (MAX_TEXT_BYTES + 1))
    assert error.value.code == 'content_too_large'


def test_write_text_refuses_symlink_target(tmp_path):
    root = tmp_path / 'workspace'
    root.mkdir()
    outside = tmp_path / 'outside.txt'
    outside.write_text('outside', encoding='utf-8')
    link = root / 'link.txt'
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip('symbolic links are unavailable')
    with pytest.raises(CommandError) as error:
        write_text(root, 'link.txt', 'replaced')
    assert error.value.code == 'invalid_path'
    assert outside.read_text(encoding='utf-8') == 'outside'


def test_control_api_scaffold_write_and_capabilities(tmp_path):
    with TestClient(studio(tmp_path)) as client:
        client.headers['X-Studio-Token'] = client.get('/api/bootstrap').json()['token']
        capabilities = client.get('/api/v1/capabilities').json()['capabilities']
        assert 'task-scaffolding' in capabilities and 'workspace-files' in capabilities
        created = client.post('/api/v1/tasks', json={'base_dir': 'demo/task1'})
        assert created.status_code == 200, created.text
        assert created.json()['base_dir'] == 'demo/task1'
        assert (tmp_path / 'demo/task1/results').is_dir()
        written = client.post('/api/v1/workspace/files',
                              json={'path': 'demo/task1/reports/summary.md', 'content': '# hi\n'})
        assert written.status_code == 200, written.text
        assert written.json()['bytes'] == 5
        assert (tmp_path / 'demo/task1/reports/summary.md').read_text(encoding='utf-8') == '# hi\n'
        denied = client.post('/api/v1/workspace/files', json={'path': '../escape.txt', 'content': 'x'})
        assert denied.status_code == 422
        assert denied.json()['code'] == 'invalid_path'


def test_write_binary_writes_exact_bytes(tmp_path):
    root = tmp_path / 'workspace'
    root.mkdir()
    payload = b'\x89PNG\r\n\x1a\n' + bytes(range(64))
    result = write_binary(root, 'task1/figures/plot.png', payload)
    assert result['path'] == 'task1/figures/plot.png'
    assert result['bytes'] == len(payload)
    assert result['created'] is True
    assert (root / 'task1/figures/plot.png').read_bytes() == payload


def test_write_binary_rejects_oversized_content(tmp_path):
    root = tmp_path / 'workspace'
    root.mkdir()
    with pytest.raises(CommandError) as error:
        write_binary(root, 'task1/big.bin', b'x' * (MAX_BINARY_BYTES + 1))
    assert error.value.code == 'content_too_large'


def test_write_binary_rejects_unsafe_paths(tmp_path):
    root = tmp_path / 'workspace'
    root.mkdir()
    with pytest.raises(CommandError):
        write_binary(root, '../escape.bin', b'x')


def test_control_api_binary_write_and_capabilities(tmp_path):
    payload = b'\x89PNG\r\n\x1a\n' + bytes(range(32))
    with TestClient(studio(tmp_path)) as client:
        client.headers['X-Studio-Token'] = client.get('/api/bootstrap').json()['token']
        capabilities = client.get('/api/v1/capabilities').json()['capabilities']
        assert 'workspace-binary-files' in capabilities
        written = client.post('/api/v1/workspace/files/binary', json={
            'path': 'demo/task1/figures/chart.png',
            'content': base64.b64encode(payload).decode('ascii'),
        })
        assert written.status_code == 200, written.text
        assert written.json()['bytes'] == len(payload)
        assert (tmp_path / 'demo/task1/figures/chart.png').read_bytes() == payload
        invalid = client.post('/api/v1/workspace/files/binary', json={
            'path': 'demo/task1/figures/bad.png', 'content': '***not-base64***'})
        assert invalid.status_code == 422
        assert invalid.json()['code'] == 'invalid_content'
        denied = client.post('/api/v1/workspace/files/binary', json={
            'path': '../escape.png', 'content': base64.b64encode(b'x').decode('ascii')})
        assert denied.status_code == 422
        assert denied.json()['code'] == 'invalid_path'
