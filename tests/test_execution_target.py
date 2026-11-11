from src.web.models import ExecutionTarget


def test_legacy_string_execution_targets_are_normalized():
    assert ExecutionTarget.model_validate('local').kind == 'local'
    assert ExecutionTarget.model_validate('ssh').kind == 'ssh'
    assert ExecutionTarget.model_validate({'kind': 'ssh'}).kind == 'ssh'
