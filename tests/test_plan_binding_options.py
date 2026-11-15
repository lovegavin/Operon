import hashlib
import pytest
from operon.contracts.base import ContractError
from operon.bytecode import io_path
from operon.contracts.run_plan import RunPlan
from operon.environment_store import EnvironmentStore
from operon.plan_binding_options import prepare_options
from test_plan_service import sample_plan
from test_environment_generations import FixtureBuilder, requirement


class ExecutableBuilder(FixtureBuilder):
    def build(self, *args, **kwargs):
        return {**super().build(*args, **kwargs), 'executable': 'runtime/fixture'}


def plan_with_input():
    value=sample_plan().model_dump(mode='json')
    value['units'][0]['input_bindings']={'data':'input:data'}
    return RunPlan.model_validate(value).with_identity()


def test_missing_store_never_installs_or_creates_directories(tmp_path):
    result=prepare_options(tmp_path, {'plan':sample_plan()})
    assert result['environments']=={'runtime':[]}
    assert result['missing']==['environment:runtime']
    assert not list(tmp_path.iterdir())


def test_exact_generation_and_corruption_are_checked(tmp_path):
    store=EnvironmentStore(tmp_path/'environments')
    binding=store.prepare(requirement(),ExecutableBuilder())
    value=sample_plan().model_dump(mode='json')
    value['environment_requirements']=[requirement().model_dump(mode='json')]
    plan=RunPlan.model_validate(value).with_identity()
    result=prepare_options(tmp_path, {'plan':plan})
    assert result['environments']['runtime'][0]['generation_id']==binding.generation_id
    io_path(store.root/'generations'/binding.generation_id/'payload/runtime/fixture').write_text('corrupt')
    assert prepare_options(tmp_path, {'plan':plan})['environments']['runtime']==[]


def test_explicit_input_fingerprint_and_unknown_inputs(tmp_path):
    path=tmp_path/'data.json';path.write_bytes(b'[1,2,3]')
    request={'plan':plan_with_input(),'input_paths':{'data':{'path':'data.json','representation':'json'}}}
    result=prepare_options(tmp_path,request)
    assert result['inputs']['data']['sha256']==hashlib.sha256(path.read_bytes()).hexdigest()
    assert result['inputs']['data']['size_bytes']==7
    request['input_paths']['unknown']={'path':'data.json'}
    with pytest.raises(ContractError):prepare_options(tmp_path,request)


def test_binding_roots_cannot_escape_workspace(tmp_path):
    with pytest.raises(ValueError):
        prepare_options(tmp_path, {'plan':sample_plan(),'environment_store':'../outside'})
