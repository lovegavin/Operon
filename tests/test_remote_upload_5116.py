import io

from operon.remote.provision import Shell


class _SFTP:
    def __init__(self):
        self.calls = []
        self.closed = False

    def putfo(self, stream, path, confirm=False):
        self.calls.append((stream.read(), path, confirm))

    def close(self):
        self.closed = True


class _Client:
    def __init__(self):
        self.sftp = _SFTP()

    def open_sftp(self):
        return self.sftp


class _Connection:
    def __init__(self):
        self.client = _Client()


def test_upload_uses_one_sftp_request():
    connection = _Connection()
    shell = Shell(connection, lambda message: None, None)
    commands = []
    shell.run = lambda command, **kwargs: commands.append(command) or ''
    data = b'program-archive' * 1000
    shell.upload('/tmp/operon.tar.gz', data)
    assert connection.client.sftp.calls == [(data, '/tmp/operon.tar.gz', True)]
    assert connection.client.sftp.closed
    assert len(commands) == 1
    assert 'sha256sum -c -' in commands[0]
    assert 'parts-' not in commands[0]
