"""Explicit export-time acquisition, confined to the environment store.

Never install into the selected scientific interpreter or the user's PATH.
The first acquisition may use the network; exported packages do not.
"""
from pathlib import Path
import json
import os
import shutil
import sys

from operon.contracts.base import ContractError
from operon.engine.fs import FileLock, atomic_json
from operon.plugins import run_process


def tooling(root, module, version):
    directory = Path(root) / 'export-tools' / (module + '-' + version)
    receipt = directory / '.ready.json'
    with FileLock(directory.with_suffix('.lock'), timeout=1200):
        identity = {'module': module, 'version': version}
        ready = (receipt.is_file() and json.loads(receipt.read_text()) == identity
                 and (directory / module).is_dir())
        if not ready:
            # A cancelled pip invocation must never become a reusable tool.
            if directory.exists():
                if not directory.resolve().is_relative_to((Path(root) / 'export-tools').resolve()):
                    raise ContractError('Tool cache escaped its owner', code='environment_unverified')
                shutil.rmtree(directory)
            directory.mkdir(parents=True, exist_ok=True)
            run_process([sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check',
                         '--no-compile', '--target', str(directory), module.replace('_', '-') + '==' + version],
                        timeout=900)
            run_process([sys.executable, '-I', '-c',
                         'import sys,importlib;sys.path.insert(0,sys.argv[1]);importlib.import_module(sys.argv[2])',
                         str(directory), module], timeout=45)
            atomic_json(receipt, identity)
    return directory


def standalone_python(root, details):
    """Acquire the exact CPython patch/architecture; never silently change ABI."""
    uv = shutil.which('uv')
    if not uv:
        folder = tooling(root, 'uv', '0.9.11')
        uv = str(folder / ('bin/uv.exe' if os.name == 'nt' else 'bin/uv'))
        if not Path(uv).is_file():
            candidates = list(folder.rglob('uv.exe' if os.name == 'nt' else 'uv'))
            uv = next((str(p) for p in candidates if p.is_file()), None)
    if not uv:
        raise ContractError('Portable Python acquisition tool is unavailable', code='environment_preparation_required')
    directory = Path(root) / 'portable-python'
    directory.mkdir(parents=True, exist_ok=True)
    request = '.'.join(map(str, details['version']))
    env = {**os.environ, 'UV_PYTHON_INSTALL_DIR': str(directory), 'UV_PYTHON_BIN': '0',
           'UV_CACHE_DIR': str(Path(root) / 'acquisition-cache')}
    with FileLock(directory / (request + '.lock'), timeout=1800):
        run_process([uv, '--no-config', 'python', 'install', '--no-bin', request], env=env, timeout=1200)
        selected = run_process([uv, '--no-config', 'python', 'find', '--managed-python', request],
                               env=env, timeout=60).strip()
    if not Path(selected).resolve().is_relative_to(directory.resolve()):
        raise ContractError('Acquired Python escaped its managed directory', code='environment_unverified')
    from .canvas import PROBE
    actual = json.loads(run_process([selected, '-I', '-c', PROBE], timeout=45))
    if (actual['version'], actual['os'], actual['arch']) != (details['version'], details['os'], details['arch']):
        raise ContractError('Acquired Python does not match the selected interpreter', code='environment_unverified')
    return actual


def pack_conda(prefix, output, root):
    """conda-pack owns prefix relocation; editable/missing files are NOT ignored."""
    module = tooling(root, 'conda_pack', '0.8.1')
    code = ('import sys; sys.path.insert(0,sys.argv[1]); import conda_pack; '
            'conda_pack.pack(prefix=sys.argv[2],output=sys.argv[3],format="tar",verbose=False)')
    run_process([sys.executable, '-I', '-c', code, str(module), str(prefix), str(output)], timeout=1800)


def managed_r(root, executable):
    """Recreate only a system R runtime at its exact version, not its packages."""
    from operon.environment_install import _micromamba, _mamba_env
    from operon.contracts.base import sha256_hex
    version = run_process([str(executable), '--vanilla', '-e', 'cat(as.character(getRversion()))'], timeout=45).strip()
    from packaging.version import Version
    Version(version)  # do not pass unvalidated output as a solver expression
    root = Path(root) / 'export-r'
    root.mkdir(parents=True, exist_ok=True)
    prefix = root / sha256_hex(version)[:16]
    selected = prefix / ('Scripts/Rscript.exe' if os.name == 'nt' else 'bin/Rscript')
    with FileLock(prefix.with_suffix('.lock'), timeout=1800):
        if not selected.is_file():
            mamba = _micromamba(root, lambda value: None)
            run_process([str(mamba), '--no-rc', 'create', '-y', '-p', str(prefix), '--override-channels',
                         '-c', 'conda-forge', '--strict-channel-priority', 'r-base==' + version],
                        env=_mamba_env(root), timeout=1800)
    from operon.r_runtime import RRuntime
    actual = run_process([str(selected), '--vanilla', '-e', 'cat(as.character(getRversion()))'],
                         env=RRuntime._env(None, selected), timeout=45).strip()
    if actual != version:
        raise ContractError('Acquired R differs from selected R', code='environment_unverified')
    return selected
