import json

import pytest

from operon.cluster.__main__ import ClusterCLIConfig, _read, main


def test_cluster_cli_configuration_is_strict_and_has_no_inline_credentials():
    assert ClusterCLIConfig.model_validate({'principal': 'alice'}).dsn_environment == 'OPERON_CLUSTER_DSN'
    with pytest.raises(ValueError):
        ClusterCLIConfig.model_validate({'principal': 'alice', 'password': 'forbidden'})
    with pytest.raises(ValueError):
        ClusterCLIConfig.model_validate({'principal': 'alice', 'schema_name': 'public;DROP'})


def test_cluster_cli_missing_dsn_is_structured_without_leaking_config(tmp_path, monkeypatch, capsys):
    path = tmp_path / 'cluster.json'
    path.write_text(json.dumps({'principal': 'alice', 'dsn_environment': 'OPERON_TEST_MISSING_DSN'}))
    monkeypatch.delenv('OPERON_TEST_MISSING_DSN', raising=False)
    assert main(['--config', str(path), 'lookup', 'key']) == 1
    result = json.loads(capsys.readouterr().out)
    assert result['ok'] is False and result['error']['code'] == 'cluster_command_failed'


def test_cluster_cli_rejects_duplicate_and_oversized_json(tmp_path):
    path = tmp_path / 'duplicate.json'
    path.write_text('{"principal":"alice","principal":"bob"}')
    with pytest.raises(ValueError, match='Duplicate'): _read(path, limit=1024)
    with pytest.raises(ValueError, match='byte limit'): _read(path, limit=1)
