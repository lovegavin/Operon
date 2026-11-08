from types import SimpleNamespace
from biopipe.remote.client import SSHConnection
from biopipe.remote import server


def test_bridge_exit_does_not_stop_shared_service(tmp_path, monkeypatch):
    import sys
    calls=[]
    monkeypatch.setattr(sys,'argv',['remote','--workspace',str(tmp_path)])
    monkeypatch.setattr(server,'ensure_daemon',lambda workspace:calls.append('ensure'))
    monkeypatch.setattr(server,'TerminalInput',lambda:SimpleNamespace(line=lambda:'BIOPIPE_REMOTE_CLOSE 1'))
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
    assert calls==[b'BIOPIPE_REMOTE_CLOSE 1\n','eof','channel','ssh']
