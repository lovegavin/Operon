"""Fixture preparation boundaries; no runtime execution is mocked as acceptance."""
import json
from pathlib import Path
import tarfile

import pytest

from operon.contracts.plan_operations import PlanCompileRequest, PlanExecutionBinding
from operon.contracts.plan_export import PlanExportRequest
from operon.contracts.run_plan import EnvironmentRequirement, TargetSpec
from operon.environment_store.verification import file_digest
from operon.planning.authoring_v2 import normalize
from scripts.acceptance.prepare_desktop_plan import archive_runtime, prepare, write_fixture


ROOT = Path(__file__).resolve().parents[1]


def test_preparation_requires_explicit_opt_in_before_touching_paths(tmp_path):
    with pytest.raises(ValueError, match='--prepare-environment'):
        prepare(workspace=tmp_path / 'missing', application_root=ROOT, python_home=tmp_path / 'missing')
    assert list(tmp_path.iterdir()) == []


def test_runtime_snapshot_rejects_virtual_environment(tmp_path):
    (tmp_path / 'pyvenv.cfg').write_text('home = another-runtime')
    with pytest.raises(ValueError, match='virtual environment'):
        archive_runtime(tmp_path, tmp_path / 'runtime.tar')
    assert not (tmp_path / 'runtime.tar').exists()


def test_fixture_cannot_be_created_inside_private_runtime(tmp_path):
    with pytest.raises(ValueError, match='fresh fixture'):
        prepare(workspace=tmp_path, application_root=ROOT, python_home=tmp_path,
                prepare_environment=True)
    assert list(tmp_path.iterdir()) == []


def test_snapshot_archive_is_deterministic_and_preserves_actual_bytes(tmp_path):
    home = tmp_path / 'home'
    home.mkdir()
    (home / 'stdlib.txt').write_bytes(b'fixture-owned runtime-shaped bytes; not executable')
    a, b = tmp_path / 'a.tar', tmp_path / 'b.tar'
    size = archive_runtime(home, a)
    assert size == (home / 'stdlib.txt').stat().st_size
    archive_runtime(home, b)
    assert file_digest(a) == file_digest(b)
    with tarfile.open(a) as archive:
        assert archive.getnames() == ['stdlib.txt']
        assert archive.extractfile('stdlib.txt').read() == (home / 'stdlib.txt').read_bytes()


def test_companion_documents_recompile_same_plan_and_bind_actual_input(tmp_path):
    folder = 'fixture'
    (tmp_path / folder).mkdir()
    # Metadata-only contract check; no generation/probe success is fabricated.
    requirement = EnvironmentRequirement(target=TargetSpec(os='windows', arch='x86_64'),
        runtime='static-fixture', dependency_lock={'artifact_hashes': ['a' * 64]})
    report = write_fixture(tmp_path, folder, ROOT, requirement, 'generation-static', 'runtime/python.exe')
    root = tmp_path / folder
    request = PlanCompileRequest.model_validate(json.loads((root / 'compile-request.json').read_text()))
    normalized = normalize(request.workflow, root, parameters=request.parameters, inputs=request.inputs,
        environments=request.environments, initial=True)
    assert normalized.compile(require_files=True).plan_id == report['plan_id']
    binding = PlanExecutionBinding.model_validate(json.loads((root / 'binding.json').read_text()))
    assert binding.inputs['data'].sha256 == file_digest(root / 'input.json')
    exported = PlanExportRequest.model_validate(json.loads((root / 'export-request.json').read_text()))
    assert exported.plan.plan_id == report['plan_id']
    assert exported.output == 'fixture/exported'
    assert exported.input_formats == {'data': 'json'}
    assert exported.plan.units[1].input_bindings['data'] == 'artifact:first/result'
    for unit in exported.plan.units:
        script = root / 'code' / unit.invocation.code_ref.ref
        assert file_digest(script) == unit.invocation.code_ref.digest
    assert (root / 'code/operon/execution/containment.py').is_file()
    assert not (root / 'preparation.json').exists()
