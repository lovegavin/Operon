import json

import pytest

from operon.remote.client import RemoteError
from operon.remote.provision import _retire_old_servers


class Shell:
    def __init__(self, output):
        self.output = output
        self.uploads = []
        self.commands = []

    def upload(self, path, data):
        self.uploads.append((path, data))

    def run(self, command, timeout=None):
        self.commands.append(command)
        if command.startswith('rm -f -- '):
            return ''
        return self.output


def result(**value):
    return 'BP_RETIRE_RESULT ' + json.dumps(value)


def test_retires_idle_daemon_and_reports_progress():
    shell = Shell(result(retired=[{'pid': 12, 'workspace': '/home/u/ws'}], blocked=[], skipped=[]))
    messages = []
    _retire_old_servers(shell, '/home/u', '/home/u/base/managed-v1', messages.append)
    assert messages == ['已释放 1 个旧版服务端']
    assert shell.uploads and b'operon.remote.server' in shell.uploads[0][1]
    assert 'command -v python3' in shell.commands[0]


def test_blocks_upgrade_when_old_daemon_has_active_work():
    shell = Shell(result(retired=[], blocked=[{'pid': 12, 'reason': 'Tasks are still active'}], skipped=[]))
    with pytest.raises(RemoteError, match='仍有任务') as error:
        _retire_old_servers(shell, '/home/u', '/home/u/base/managed-v1', lambda message: None)
    assert error.value.code == 'remote_upgrade_blocked'


def test_blocks_upgrade_when_state_is_unknown():
    shell = Shell('unexpected')
    with pytest.raises(RemoteError, match='无法确认') as error:
        _retire_old_servers(shell, '/home/u', '/home/u/base/managed-v1', lambda message: None)
    assert error.value.code == 'remote_upgrade_blocked'
