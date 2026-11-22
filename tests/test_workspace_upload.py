"""Streamed workspace uploads: raw request bodies instead of 50 MiB base64."""
import hashlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from operon.documents import CommandError
from operon.task_files import open_stream, write_stream
from src.web.api import create_app
from src.web.service import Settings

ROOT = Path(__file__).resolve().parents[1]


def studio(tmp_path):
    return create_app(Settings(tmp_path, tmp_path / 'studio', ROOT / 'frontend/dist',
                               testing=True, code_root=ROOT, desktop=True))


def test_write_stream_writes_chunks_and_hashes(tmp_path):
    root = tmp_path / 'workspace'
    root.mkdir()
    payload = b'\x89PNG\r\n\x1a\n' + bytes(range(256)) * 3
    result = write_stream(root, 'task1/figures/big.png', [payload[i:i + 64] for i in range(0, len(payload), 64)])
    assert result['path'] == 'task1/figures/big.png'
    assert result['bytes'] == len(payload)
    assert result['sha256'] == hashlib.sha256(payload).hexdigest()
    assert result['created'] is True
    assert (root / 'task1/figures/big.png').read_bytes() == payload


def test_write_stream_respects_overwrite(tmp_path):
    root = tmp_path / 'workspace'
    root.mkdir()
    write_stream(root, 'task1/data.bin', [b'first'])
    with pytest.raises(CommandError) as error:
        write_stream(root, 'task1/data.bin', [b'second'], overwrite=False)
    assert error.value.code == 'file_exists'
    assert (root / 'task1/data.bin').read_bytes() == b'first'
    replaced = write_stream(root, 'task1/data.bin', [b'second'])
    assert replaced['created'] is False
    assert (root / 'task1/data.bin').read_bytes() == b'second'


def test_open_stream_removes_the_temporary_file_when_the_writer_fails(tmp_path):
    root = tmp_path / 'workspace'
    root.mkdir()
    with pytest.raises(RuntimeError):
        with open_stream(root, 'task1/broken.bin') as sink:
            sink.write(b'partial')
            raise RuntimeError('connection dropped')
    assert not (root / 'task1/broken.bin').exists()
    assert list((root / 'task1').iterdir()) == []


@pytest.mark.parametrize('value', ['../escape.bin', '/etc/passwd', 'C:/secret.bin', '.studio/state.bin'])
def test_open_stream_rejects_unsafe_paths(tmp_path, value):
    root = tmp_path / 'workspace'
    root.mkdir()
    with pytest.raises(CommandError):
        with open_stream(root, value):
            pass


def test_control_api_streams_a_raw_body(tmp_path):
    payload = b'\x1f\x8b' + bytes(range(200)) * 7
    with TestClient(studio(tmp_path)) as client:
        client.headers['X-Studio-Token'] = client.get('/api/bootstrap').json()['token']
        capabilities = client.get('/api/v1/capabilities').json()['capabilities']
        assert 'workspace-stream-uploads' in capabilities
        written = client.post('/api/v1/workspace/files/raw?path=demo/input/reads.fastq.gz',
                              content=payload, headers={'Content-Type': 'application/octet-stream'})
        assert written.status_code == 200, written.text
        body = written.json()
        assert body['bytes'] == len(payload)
        assert body['sha256'] == hashlib.sha256(payload).hexdigest()
        assert (tmp_path / 'demo/input/reads.fastq.gz').read_bytes() == payload
        denied = client.post('/api/v1/workspace/files/raw?path=../escape.bin', content=b'x')
        assert denied.status_code == 422
        assert denied.json()['code'] == 'invalid_path'
