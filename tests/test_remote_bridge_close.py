from types import SimpleNamespace
from operon.remote.client import SSHConnection
from operon.remote import server


def test_bridge_exit_does_not_stop_shared_service(tmp_path, monkeypatch):
    import sys
    calls=[]
    monkeypatch.setattr(sys,'argv',['remote','--workspace',str(tmp_path)])
    monkeypatch.setattr(server,'ensure_daemon',lambda workspace:calls.append('ensure'))
    monkeypatch.setattr(server,'TerminalInput',lambda:SimpleNamespace(line=lambda:'OPERON_REMOTE_CLOSE 1'))
    monkeypatch.setattr(server,'rpc',lambda *a: calls.append('unexpected-rpc'))
    server.main()
    assert calls==['ensure']


def test_client_close_signals_bridge_then_closes_channel():
    calls=[]
    connection=SSHConnection.__new__(SSHConnection)
    connection.channel=SimpleNamespace(send_ready=lambda:True,send=lambda b:calls.append(b),
        shutdown_write=lambda:calls.append('eof'),close=lambda:calls.append('channel'))
    connection.client=SimpleNamespace(close=lambda:calls.append('ssh'))
    connection.close()
    assert calls==[b'OPERON_REMOTE_CLOSE 1\n','eof','channel','ssh']

def test_dispatch_recovers_missing_daemon_once_with_same_request(monkeypatch):
    calls, ensured, logs = [], [], []
    request = {'id': 'q1', 'method': 'status', 'params': {}}

    def rpc(workspace, value):
        calls.append((workspace, value))
        if len(calls) == 1:
            raise server.DaemonUnavailable(
                'missing', details={'phase': 'connect', 'retryable': True,
                                    'request_id': value['id'], 'cause': 'FileNotFoundError'})
        return {'id': value['id'], 'ok': True, 'value': {'recovered': True}}

    monkeypatch.setattr(server, 'rpc', rpc)
    result = server.dispatch_with_recovery('ws', request, ensure=lambda workspace: ensured.append(workspace),
                                           log=lambda workspace, **fields: logs.append(fields))
    assert result['value'] == {'recovered': True}
    assert len(calls) == 2 and calls[0] == calls[1]
    assert ensured == ['ws']
    assert [item['event'] for item in logs] == ['daemon_missing', 'daemon_recovered']


def test_dispatch_never_replays_after_maybe_sent_request(monkeypatch):
    calls, ensured, logs = [], [], []

    def rpc(workspace, request):
        calls.append(request)
        raise server.RpcTransportError('write failed', details={'phase': 'send', 'retryable': False})

    monkeypatch.setattr(server, 'rpc', rpc)
    with __import__('pytest').raises(server.RpcTransportError):
        server.dispatch_with_recovery('ws', {'id': 'q2', 'method': 'run'},
                                      ensure=lambda workspace: ensured.append(workspace),
                                      log=lambda workspace, **fields: logs.append(fields))
    assert len(calls) == 1 and ensured == []
    assert [item['event'] for item in logs] == ['rpc_transport_failed']


def test_dispatch_reports_recovery_failure_without_a_second_user_request(monkeypatch):
    calls, logs = [], []

    def rpc(workspace, request):
        calls.append(request)
        raise server.DaemonUnavailable('missing', details={'phase': 'connect', 'retryable': True})

    monkeypatch.setattr(server, 'rpc', rpc)
    with __import__('pytest').raises(server.DaemonUnavailable) as error:
        server.dispatch_with_recovery('ws', {'id': 'q3', 'method': 'run'},
                                      ensure=lambda workspace: (_ for _ in ()).throw(RuntimeError('no start')),
                                      log=lambda workspace, **fields: logs.append(fields))
    assert len(calls) == 1
    assert error.value.details['phase'] == 'ensure'
    assert error.value.details['recovery'] == 'failed'
    assert [item['event'] for item in logs] == ['daemon_missing', 'daemon_recovery_failed']

def test_diagnostic_logging_redacts_secret_shaped_text(tmp_path):
    from operon.remote.server import _event_log, _sanitize_diagnostic
    text = _sanitize_diagnostic('password=hunter2 token: abc123 https://user:pass@example.test')
    assert 'hunter2' not in text and 'abc123' not in text and 'user:pass' not in text
    _event_log(tmp_path, 'bridge.events.jsonl', {'event': 'failure',
               'traceback': 'password=hunter2\nFileNotFoundError: /tmp/socket'})
    value = (tmp_path / '.studio/remote/bridge.events.jsonl').read_text(encoding='utf-8')
    assert 'hunter2' not in value and 'FileNotFoundError' in value
