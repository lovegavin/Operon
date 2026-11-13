from src.web.models import ExecutionTarget


def test_legacy_string_execution_targets_are_normalized():
    assert ExecutionTarget.model_validate('local').kind == 'local'
    assert ExecutionTarget.model_validate('ssh').kind == 'ssh'
    assert ExecutionTarget.model_validate({'kind': 'ssh'}).kind == 'ssh'

def test_missing_ssh_input_environment_explains_profile_recovery():
    from src.web.execution_plan import unavailable_input

    assert unavailable_input("local") == "Input environment is unavailable: local"
    message = unavailable_input("fcfaf7ce647d400c829ea493e65ae4fd")
    assert "fcfaf7ce647d400c829ea493e65ae4fd" in message
    assert "operon remote-status" in message
