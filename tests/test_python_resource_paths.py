"""Actual stripped-runtime probes; no installed .pth hook may hide failures."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from operon.bytecode import io_path
from operon.python_paths import bootstrap_code

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def staged(tmp_path_factory):
    selected = os.environ.get('OPERON_PATH_TEST_PYTHON')
    if os.name != 'nt' or not selected:
        pytest.skip('Requires explicit Windows private Python fixture')
    home = Path(selected).parent
    parent = tmp_path_factory.mktemp('python-resource-paths')
    stem = 'staged environment with spaces '
    root = parent / (stem + 'x' * (190 - len(str(parent)) - 1 - len(stem)))
    io_path(root).mkdir(parents=True)
    shutil.copytree(io_path(home), io_path(root / 'runtime'),
                    ignore=shutil.ignore_patterns('site-packages', '__pycache__', '*.pyc'))
    packages = root / 'packages'; io_path(packages).mkdir()
    for name in ('jsonschema', 'jsonschema_specifications', 'referencing', 'rpds', 'attrs', 'attr',
                 'numpy', 'numpy.libs', 'pydantic', 'pydantic_core', 'psutil', 'yaml', '_yaml',
                 'packaging', 'typing_extensions.py', 'typing_inspection', 'annotated_types'):
        source = home / 'Lib/site-packages' / name
        if not source.exists():
            continue
        if source.is_dir():
            shutil.copytree(io_path(source), io_path(packages / name),
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        else:
            shutil.copyfile(io_path(source), io_path(packages / name))
    return root


def run(root, code, *args):
    return subprocess.run([str(io_path(root / 'runtime/python.exe')), '-I', '-B', '-c', code, *map(str,args)],
                          capture_output=True, text=True, timeout=45)


def test_plain_staged_path_reproduces_and_shared_bootstrap_reads_resources(staged):
    packages = str(staged / 'packages')
    relative = 'jsonschema_specifications/schemas/draft201909/vocabularies/applicator'
    assert len(str(staged / 'packages' / relative)) > 260
    expected = io_path(staged / 'packages' / relative).read_bytes()
    baseline = run(staged, 'import sys;sys.path.insert(0,sys.argv[1]);import jsonschema', packages)
    assert baseline.returncode != 0 and 'FileNotFoundError' in baseline.stderr, baseline.stderr
    code = bootstrap_code(
        'import jsonschema,importlib.resources as r;'
        'data=r.files("jsonschema_specifications").joinpath("schemas/draft201909/vocabularies/applicator").read_bytes();'
        'import hashlib;print(hashlib.sha256(data).hexdigest())',
        paths_expression='[sys.argv[1]]')
    fixed = run(staged, code, packages)
    import hashlib
    assert fixed.returncode == 0, fixed.stderr
    assert fixed.stdout.strip() == hashlib.sha256(expected).hexdigest()


def test_cached_package_loader_resource_path_is_repaired(staged):
    name = 'orfx'
    package = staged / 'packages' / name
    io_path(package).mkdir(exist_ok=True)
    io_path(package / '__init__.py').write_text('VALUE=42\n')
    relative = 'nested/' * 12 + 'value.txt'
    io_path(package / relative).parent.mkdir(parents=True, exist_ok=True)
    io_path(package / relative).write_text('unchanged resource')
    code = ('import sys,importlib.resources as r;sys.path.insert(0,sys.argv[1]);'
            'import orfx as m;'
            'prefix=chr(92)*2+"?"+chr(92);assert not m.__spec__.loader.path.startswith(prefix);\n'
            + bootstrap_code('assert m.__file__==m.__spec__.origin==m.__spec__.loader.path\n'
                'assert m.__file__.startswith(prefix)\n'
                'assert r.files(m).joinpath(' + repr(relative) + ').read_text()=="unchanged resource"\n'))
    result = run(staged, code, staged / 'packages')
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('selected_python', [False, True])
def test_canvas_probes_original_and_relocated_stripped_runtime(staged, monkeypatch, selected_python):
    from operon.environment_store.canvas import CanvasArchiveBuilder
    from operon.environment_store import closures
    # Exercise both concrete probe branches with the same real staged runtime.
    # This is not a Conda acquisition/relocation test.
    original = closures.materialize
    if selected_python:
        def selected(root, *a, **kw):
            value = original(root, *a, **kw)
            value['python'] = str(Path(root) / 'runtime/python.exe')
            return value
        monkeypatch.setattr(closures, 'materialize', selected)
    command = ('runtime/python.exe', '-I', '-B', '-c', bootstrap_code(
        'import jsonschema', paths_expression='[str(Path.cwd()/"packages")]'))
    builder = CanvasArchiveBuilder([], [command], relative_python='runtime/python.exe', imports=['jsonschema'])
    assert builder.verify(staged)['status'] == 'passed'


def test_isolated_runtime_bootstrap_preserves_target_order(staged):
    first, second = staged / 'first target', staged / 'second target'
    for root, value in ((first, 'isolated'), (second, 'shared')):
        p = io_path(root / 'owned_choice'); p.mkdir(parents=True, exist_ok=True)
        (p/'__init__.py').write_text('')
        (p/'answer.txt').write_text(value)
    module = io_path(first / 'check_owned.py')
    module.write_text('import importlib.resources as r\nassert r.files("owned_choice").joinpath("answer.txt").read_text()=="isolated"\n')
    config = io_path(staged / 'bootstrap-config.json')
    config.write_text(json.dumps({'paths':[str(first),str(second),str(ROOT)]}))
    result = subprocess.run([str(io_path(staged/'runtime/python.exe')), '-I', '-S', '-B',
                             str(ROOT/'operon/runtime_bootstrap.py'), str(config), 'check_owned'],
                            capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stderr


def test_bootstrap_does_not_mutate_configured_search_order():
    source = bootstrap_code('print(sys.path[:2])', paths_expression=repr(['first-relative','second-relative']))
    result = subprocess.run([sys.executable,'-I','-S','-c',source],capture_output=True,text=True,timeout=20)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip()=="['first-relative', 'second-relative']"


def test_command_adapter_reads_real_dependency_resources(staged):
    from types import SimpleNamespace
    from operon.contracts.run_plan import InvocationSpec, CodeRef
    from operon.environment_store.verification import file_digest
    from operon.execution.adapters.command import CommandInvocationAdapter
    from operon.execution.invocation import InvocationContext
    # Binding is a fixture; launch and dependency/resource access are real.
    store = SimpleNamespace(binding=lambda key: SimpleNamespace(model_dump=lambda **kw: {}))
    # Keep the interpreter's own DLL search path short, while package resources
    # exceed MAX_PATH, exactly as in the real failing staged environment.
    name = 'adapter ' + 'x' * (190-len(str(staged.parent))-1-len('/generations/fixture/payload')-len('adapter '))
    store.root = staged.parent / name
    payload = store.root / 'generations' / 'fixture' / 'payload'
    io_path(payload.parent).mkdir(parents=True, exist_ok=True)
    # Avoid junction privilege requirements: the real runtime lives inside this generation.
    shutil.copytree(io_path(staged / 'runtime'), io_path(payload / 'runtime'))
    shutil.copytree(io_path(staged / 'packages'), io_path(payload / 'packages'))
    script = staged / 'resource_script.py'
    io_path(script).write_text('import jsonschema\nprint("resource-ready")\n')
    spec = InvocationSpec(kind='python_script', entrypoint='resource_script.py',
                          code_ref=CodeRef(kind='file', ref=script.name, digest=file_digest(script)))
    ctx = InvocationContext(attempt_root=staged/'attempt', attempt_id='attempt', run_id='run', unit_id='unit',
                            fence=1, payload={'executable':'runtime/python.exe'}, memory_bytes=64*1024**2)
    prepared = CommandInvocationAdapter(store,'fixture',package_root=staged).prepare(spec,ctx)
    result = subprocess.run(prepared.command,env=prepared.environment,cwd=prepared.task_dir,
                            capture_output=True,text=True,timeout=45)
    assert result.returncode == 0, result.stderr
    assert 'resource-ready' in result.stdout


def test_export_bootstrap_loads_collected_kernel_at_long_path(staged):
    from operon.export.collector import kernel_files, collect
    from operon.export.service import BOOTSTRAP
    bundle = staged / 'export with spaces'
    files = kernel_files(ROOT)
    assert 'operon/python_paths.py' in files
    collect(ROOT,bundle/'payload/code',files)
    io_path(bundle/'bundle.json').write_text(json.dumps({'management_packages':'../packages'}))
    io_path(bundle/'launch.py').write_text(BOOTSTRAP,encoding='utf-8')
    result = subprocess.run([str(io_path(staged/'runtime/python.exe')),'-I','-B',
                             str(io_path(bundle/'launch.py')),'--help'],capture_output=True,text=True,timeout=45)
    assert result.returncode == 0, result.stderr
    assert '--bundle' in result.stdout
