"""Provider-to-application closure without top-level execution or helper allowlists."""
from pathlib import Path
from types import SimpleNamespace
import json
import subprocess
import sys
from copy import deepcopy

import pytest

from operon.contracts.base import ContractError
from operon.export.collector import expand_local_dependencies, collect, CODE_CLOSURE_ABI
from operon.export.automatic import canvas_code_inventory, code_inventory_identity, collect_canvas_code
from operon.environment_store.verification import file_digest

ROOT = Path(__file__).resolve().parents[1]


def write(root, name, content):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')
    return path


def owner(root, name):
    return root, {'path': name, 'sha256': file_digest(root / name), 'role': 'implementation'}


def fixture(tmp_path):
    app, provider = tmp_path / 'application', tmp_path / 'provider'
    write(app, 'src/__init__.py', '')
    write(app, 'src/helpers/__init__.py', 'from . import implementation\n')
    write(app, 'src/helpers/implementation.py', 'from .leaf import VALUE\n')
    write(app, 'src/helpers/leaf.py', 'from . import implementation\nVALUE=42\n')
    write(provider, 'example_ops/__init__.py', '')
    write(provider, 'example_ops/run.py',
          'import math\nfrom src.helpers import implementation\n'
          'def calculate(): return implementation.VALUE\n')
    return app, provider


def test_recursive_relative_cycle_package_attribute_and_isolated_execution(tmp_path):
    app, provider = fixture(tmp_path)
    owners = {'example_ops/run.py': owner(provider, 'example_ops/run.py')}
    files = expand_local_dependencies(owners, application_root=app, roots=[app, provider])
    assert 'src/helpers/leaf.py' in files and 'example_ops/__init__.py' in files
    assert not any(name.startswith('math') for name in files)
    assert 'example_ops' not in sys.modules
    output = tmp_path / 'relocated bundle'
    for name, (root, item) in files.items():
        collect(root, output, {name: item})
    result = subprocess.run([sys.executable, '-I', '-S', '-c',
        'import sys;sys.path.insert(0,sys.argv[1]);from example_ops.run import calculate;assert calculate()==42',
        str(output)], cwd=output, capture_output=True)
    assert result.returncode == 0, result.stderr


def test_missing_required_module_fails_before_launch(tmp_path):
    app, provider = fixture(tmp_path)
    write(provider, 'example_ops/run.py', 'from src.helpers.unavailable import value\n')
    with pytest.raises(ContractError, match='src.helpers.unavailable'):
        expand_local_dependencies({'example_ops/run.py': owner(provider, 'example_ops/run.py')},
                                  application_root=app, roots=[app, provider])


def test_literal_dynamic_import_and_code_identity_track_transitive_change(tmp_path):
    app, provider = fixture(tmp_path)
    write(provider, 'example_ops/run.py',
          'from importlib import import_module as load\nhelper=load("src.helpers.implementation")\n')
    def inventory():
        return {}, expand_local_dependencies({'example_ops/run.py': owner(provider, 'example_ops/run.py')},
                                              application_root=app, roots=[app, provider])
    before = code_inventory_identity(inventory())
    write(app, 'src/helpers/leaf.py', 'VALUE=43\n')
    after = code_inventory_identity(inventory())
    assert before['abi'] == CODE_CLOSURE_ABI and before != after


def test_ambiguous_cross_provider_module_refused(tmp_path):
    app, provider = fixture(tmp_path)
    other = tmp_path / 'other'
    write(provider, 'example_ops/run.py', 'import support\n')
    write(provider, 'support.py', 'VALUE=1\n')
    write(other, 'support.py', 'VALUE=2\n')
    with pytest.raises(ContractError, match='Ambiguous'):
        expand_local_dependencies({'example_ops/run.py': owner(provider, 'example_ops/run.py')},
                                  application_root=app, roots=[app, provider, other])


def test_provider_module_not_executed_and_resources_preserved(tmp_path):
    app, provider = fixture(tmp_path)
    write(provider, 'example_ops/run.py',
          'from src.helpers import implementation\nraise RuntimeError("MUST NOT EXECUTE")\n')
    before = set(sys.modules)
    files = expand_local_dependencies({'example_ops/run.py': owner(provider, 'example_ops/run.py')},
                                     application_root=app, roots=[app, provider])
    assert 'src/helpers/leaf.py' in files
    assert not {'src.helpers', 'example_ops'} & (set(sys.modules) - before)


def test_symlink_dependency_rejected(tmp_path):
    app, provider = fixture(tmp_path)
    outside = write(tmp_path, 'outside.py', 'VALUE=7\n')
    target = app / 'src/helpers/link.py'
    try:
        target.symlink_to(outside)
    except OSError:
        pytest.skip('Windows account cannot create symlinks')
    write(provider, 'example_ops/run.py', 'import src.helpers.link\n')
    with pytest.raises(ContractError, match='alias'):
        expand_local_dependencies({'example_ops/run.py': owner(provider, 'example_ops/run.py')},
                                  application_root=app, roots=[app, provider])


def test_actual_csv_reader_gets_application_dependencies_without_changing_pin(tmp_path):
    from operon_sdk.declarations import source_declarations, compile_declaration
    seed = ROOT / 'library/seed'
    module = 'src.reader.readers.csv_reader'
    raw = source_declarations(seed / 'src/reader/readers/csv_reader.py', module)[0]
    descriptor = compile_declaration(raw, seed)
    pin = {'package': 'fixture-csv', 'version': '1.0.0', 'code_sha': descriptor['code_sha']}
    plan = SimpleNamespace(diagnostics={'native_descriptor_audit': {'CsvReader': descriptor}},
                           implementations={'CsvReader': {'implementation': pin}})
    original = deepcopy(plan.implementations)
    discovered = canvas_code_inventory(plan, application_root=ROOT, roots=[ROOT, seed])
    manifests = collect_canvas_code(plan, tmp_path / 'bundle', application_root=ROOT,
                                   roots=[ROOT, seed], discovered=discovered)
    assert 'src/core/numeric.py' in discovered[1]
    assert 'src/core/numeric.py' in manifests['CsvReader']['files']
    assert plan.implementations == original
    data = write(tmp_path, 'input.csv', 'a,b\n1,2\n3,4\n')
    result = subprocess.run([sys.executable, '-I', '-c',
        'import sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);'
        'from src.reader.readers.csv_reader import CsvReader;'
        'f=CsvReader().read(Path(sys.argv[2]),["sample","feature"],{"sample":"auto","feature":"builtin"});'
        'assert f.data.shape==(2,2) and f.data.tolist()==[[1,2],[3,4]];print("csv-ok")',
        str(tmp_path / 'bundle'), str(data)], cwd=tmp_path, capture_output=True)
    assert result.returncode == 0, result.stderr.decode(errors='replace')


def test_retained_payload_is_not_the_dependency_frontier(tmp_path):
    app, provider = fixture(tmp_path)
    write(provider, 'example_ops/optional/__init__.py', 'from .not_installed import Tool\n')
    write(provider, 'example_ops/optional/foreign.py', 'not valid python here !!!')
    resource = write(provider, 'example_ops/assets/colours.txt', 'blue\ngreen\n')
    owners = {p.relative_to(provider).as_posix(): owner(provider, p.relative_to(provider).as_posix())
              for p in provider.rglob('*') if p.is_file()}
    files = expand_local_dependencies(owners, application_root=app, roots=[app, provider],
                                     entry_files={'example_ops/run.py'})
    assert 'src/helpers/leaf.py' in files
    output = tmp_path / 'relocated selected code'
    for name, (root, item) in files.items():
        collect(root, output, {name: item})
    assert (output / 'example_ops/assets/colours.txt').read_bytes() == resource.read_bytes()
    assert (output / 'example_ops/optional/foreign.py').read_text() == 'not valid python here !!!'
    result = subprocess.run([sys.executable, '-I', '-S', '-c',
        'import sys;sys.path.insert(0,sys.argv[1]);from example_ops.run import calculate;assert calculate()==42',
        str(output)], cwd=output, capture_output=True)
    assert result.returncode == 0, result.stderr
    # Selecting the previously unused subtree must now diagnose its broken import.
    with pytest.raises(ContractError, match='not_installed'):
        expand_local_dependencies(owners, application_root=app, roots=[app, provider],
                                  entry_files={'example_ops/optional/__init__.py'})


def test_reachable_preexisting_file_and_package_initializer_are_checked(tmp_path):
    app, provider = fixture(tmp_path)
    write(provider, 'example_ops/run.py', 'from .helper import VALUE\n')
    write(provider, 'example_ops/helper.py', 'from .missing import VALUE\n')
    owners = {p.relative_to(provider).as_posix(): owner(provider, p.relative_to(provider).as_posix())
              for p in provider.rglob('*.py')}
    with pytest.raises(ContractError, match='example_ops.missing'):
        expand_local_dependencies(owners, application_root=app, roots=[app, provider],
                                  entry_files={'example_ops/run.py'})
    write(provider, 'example_ops/helper.py', 'VALUE=42\n')
    write(provider, 'example_ops/__init__.py', 'from .unavailable import Thing\n')
    owners = {p.relative_to(provider).as_posix(): owner(provider, p.relative_to(provider).as_posix())
              for p in provider.rglob('*.py')}
    with pytest.raises(ContractError, match='example_ops.unavailable'):
        expand_local_dependencies(owners, application_root=app, roots=[app, provider],
                                  entry_files={'example_ops/run.py'})
