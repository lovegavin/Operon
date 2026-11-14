"""Dedicated interpreter environments for operators with conflicting pins."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _manifest_root(root=None) -> Path | None:
    value = root if root is not None else os.environ.get("OPERON_LIBRARY_SOURCE")
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "none":
        return None
    return Path(text).expanduser()


def _installed_library_manifest() -> Path | None:
    """The manifest persisted beside the installed, version-scoped library."""
    try:
        from .installation import library_root
        base = library_root()
    except Exception:
        base = None
    if base is None:
        return None
    candidate = Path(base) / "environments.json"
    return candidate if candidate.is_file() else None


def manifest_path(root=None) -> Path:
    """Return the active imported library manifest, else the application seed.

    An imported root wins even when the file is absent, so an old library tree
    never silently reports environments it did not declare. A root that does not
    exist yet means no library has been imported, so the installed library or the
    bundled seed applies. An empty or literal "None" root is treated as absent;
    installed applications have no source tree and used to fail on that string.
    """
    base = _manifest_root(root)
    if base is not None:
        seed = base / "operon/environments.json"
        installed = base / "environments.json"
        if seed.is_file():
            return seed
        if installed.is_file():
            return installed
        if base.exists():
            return seed
    installed = _installed_library_manifest()
    if installed is not None:
        return installed
    from .library_location import asset_path
    return asset_path('operon/environments.json')


def load(root=None) -> dict:
    path = manifest_path(root)
    if not path.is_file():
        return {}
    document = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(document, dict) or not isinstance(document.get('environments'), dict):
        raise ValueError(f"Invalid isolated environment manifest: {path}")
    return document['environments']


def _install_root(prefix: Path) -> Path | None:
    """Return the managed install root for a bundled runtime, when present."""
    candidate = prefix
    for _ in range(5):
        candidate = candidate.parent
        if (candidate / 'installation.json').is_file() and (candidate / 'versions').is_dir():
            return candidate
    return None


def _native_path(value) -> Path:
    """Strip Windows' extended-length prefix before spawning a child process.

    ``Path.resolve()`` can return an extended-length ``\\\\?\\`` path for an install root that was
    opened through a junction or a long path.  A child started from that form
    reports ``sys.prefix`` with the same prefix, and the OpenMM extension then
    fails to find its dependent DLLs.  Native paths behave correctly.
    """
    if os.name != 'nt':
        return Path(value)
    text = str(value)
    if text.startswith('\\\\?\\UNC\\'):
        return Path('\\\\' + text[8:])
    if text.startswith('\\\\?\\'):
        return Path(text[4:])
    return Path(text)


def root() -> Path:
    """Return the stable directory that keeps isolated interpreters.

    Environments must survive application upgrades, so they never live inside a
    version directory: managed servers keep them next to ``env-*`` under
    ``managed-v1/environments`` and desktop installs under ``<root>/environments``.
    """
    value = os.environ.get('OPERON_ENVIRONMENTS_ROOT')
    if value:
        return _native_path(Path(value).expanduser())
    prefix = _native_path(Path(sys.prefix).resolve())
    parent = prefix.parent
    if parent.name == 'managed-v1' and prefix.name.startswith('env-'):
        return parent / 'environments'
    from operon.installation import library_root as _version_library
    version_library = _version_library()
    if version_library is not None:
        return version_library / 'environments'
    install = _install_root(prefix)
    if install is not None:
        return install / 'environments'
    return prefix / 'external'


def describe(name: str, root=None) -> dict:
    value = load(root).get(name)
    if value is None:
        raise ValueError(f'unknown isolated environment: {name}')
    return value


def resolve(name: str) -> Path | None:
    """Return the interpreter of a declared environment, when it exists."""
    env_var = 'OPERON_ENV_' + name.upper()
    candidates = []
    if os.environ.get(env_var):
        candidates.append(Path(os.environ[env_var]).expanduser())
    base = root() / name
    layouts = ('bin/python', 'Scripts/python.exe', 'python.exe')
    candidates.extend(base / layout for layout in layouts)
    managed = Path(sys.prefix).resolve().parent
    for layout in layouts:
        candidates.extend(sorted(managed.glob(f'env-*/external/{name}/{layout}')))
        candidates.append(managed / 'external' / name / layout)
    for path in candidates:
        if path.is_file() and os.access(path, os.X_OK):
            return _native_path(path)
    return None


def _probe_cwd(python):
    """Neutral working directory outside the environment.

    Holding the environment as a probe's current directory blocks the
    installer from renaming it on Windows (WinError 5).
    """
    return tempfile.gettempdir()


def _probe_environment_variables(python: Path) -> dict[str, str]:
    """Run probes with the same DLL search directories as the real worker."""
    python = Path(str(python))
    env = os.environ.copy()
    for name in ('PYTHONPATH', 'PYTHONHOME'):
        env.pop(name, None)
    env['PYTHONNOUSERSITE'] = '1'
    base = python.parent.parent if python.parent.name.lower() in {'scripts', 'bin'} else python.parent
    folders = [python.parent, base, base / 'Library' / 'bin', base / 'bin']
    env['PATH'] = os.pathsep.join(
        [*(str(item) for item in folders if item.is_dir()), env.get('PATH', '')])
    return env


def probe(name: str, imports=None, root=None) -> tuple[bool, str, str]:
    entry = describe(name, root)
    resolved = resolve(name)
    python = Path(str(resolved)) if resolved is not None else None
    if python is None:
        return False, '', f'isolated environment {name!r} is not installed under {root() / name}'
    names = imports or entry.get('imports', [])
    script = ';'.join('import ' + module for module in names) or 'pass'
    env = _probe_environment_variables(python)
    result = subprocess.run([str(python), '-X', 'utf8', '-c', script], capture_output=True, text=True,
                            encoding='utf-8', errors='replace', timeout=300, env=env, cwd=_probe_cwd(python))
    if result.returncode:
        tail = (result.stderr or result.stdout).strip().splitlines()[-1:] or ['import failed']
        return False, str(python), tail[0]
    return True, str(python), ''


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description='Inspect isolated operator environments.')
    parser.add_argument('name', nargs='?')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    names = [args.name] if args.name else sorted(load())
    report = {}
    for name in names:
        ok, python, error = probe(name)
        report[name] = {'ok': ok, 'python': python, 'error': error}
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for name, value in report.items():
            print(('OK   ' if value['ok'] else 'FAIL ') + name, value['python'], value['error'])
    return 0 if all(value['ok'] for value in report.values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np


def code_root() -> Path:
    """Locate the checkout that provides both ``operon`` and ``src``.

    Managed installs copy the package into ``site-packages`` while the sources
    live in a sibling ``code-<digest>`` directory, so the package parent alone is
    not enough for the worker's ``PYTHONPATH``.
    """
    import os
    import sys
    import operon
    candidates = []
    if os.environ.get("OPERON_CODE_ROOT"):
        candidates.append(Path(os.environ["OPERON_CODE_ROOT"]))
    package = Path(operon.__file__).resolve()
    candidates.append(package.parent.parent)
    candidates.extend(Path(prefix) for prefix in sys.path if prefix)
    # Managed installs keep the sources beside the runtime (``versions/<v>`` or
    # ``managed-v1/code-<digest>``), never inside site-packages.
    for parent in package.parents:
        candidates.append(parent)
        try:
            candidates.extend(sorted(parent.glob("code-*")))
        except OSError:
            continue
    candidates.extend(Path(sys.prefix).resolve().parent.glob("code-*"))
    for candidate in candidates:
        if any(part in {"site-packages", "dist-packages"} for part in candidate.parts):
            continue
        if (candidate / "src/task").is_dir() and (candidate / "operon").is_dir():
            return candidate
    raise RuntimeError("cannot locate the Operon source tree for the environment bridge")


def _write_form(directory: Path, index: int, form) -> dict:
    data_path = directory / f"input{index}.npy"
    np.save(data_path, np.asarray(form.data))
    meta = {"dims": list(form.dims), "labels": {k: dict(v) for k, v in form.labels.items()},
            "info": _jsonable(form.info), "axis_info": _jsonable(form.axis_info)}
    (directory / f"input{index}.json").write_text(json.dumps(meta), encoding="utf-8")
    return meta


def _jsonable(value):
    if hasattr(value, "mapping") and hasattr(value, "inverse"):
        return {"__labelencoder__": dict(value.mapping)}
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, np.generic):
        return _jsonable(value.item())
    if isinstance(value, np.ndarray):
        return _jsonable(value.tolist())
    if isinstance(value, float) and not np.isfinite(value):
        return {"__float__": str(value)}
    return value


def run_step(descriptor: dict, inputs, params: dict, python: Path, *, timeout: int = 3600, paths=()):
    """Execute one step in ``python`` and return (form, export, console tail)."""
    with tempfile.TemporaryDirectory(prefix="envbridge-") as temporary:
        return _run_step(Path(temporary), descriptor, inputs, params, python, timeout=timeout, paths=paths)


def worker_environment(python: Path, paths=()) -> dict[str, str]:
    """Keep OS/DLL/download settings while isolating Python module resolution."""
    env = os.environ.copy()
    env.pop('PYTHONHOME', None)
    entries = [str(code_root())]
    entries.extend(str(value) for value in paths if value)
    env['PYTHONPATH'] = os.pathsep.join(entries)
    env['PYTHONNOUSERSITE'] = '1'
    env['PYTHONUTF8'] = '1'
    env['PYTHONIOENCODING'] = 'utf-8'
    base = python.parent.parent if python.parent.name in {'bin', 'Scripts'} else python.parent
    paths = [python.parent, base / 'Scripts', base / 'Library/bin', base / 'bin']
    env['PATH'] = os.pathsep.join([*(str(p) for p in paths if p.is_dir()), env.get('PATH', '')])
    libs = [p for p in (base / 'lib', base / 'lib64') if p.is_dir()]
    if libs:
        previous = env.get('LD_LIBRARY_PATH', '')
        env['LD_LIBRARY_PATH'] = os.pathsep.join(
            [*(str(p) for p in libs), *([previous] if previous else [])]
        )
    return env


def _run_step(directory, descriptor, inputs, params, python, *, timeout, paths=()):
    from src.core.errors import StepError
    request = {"entry_point": descriptor["entry_point"], "params": params, "inputs": []}
    for index, form in enumerate(inputs):
        request["inputs"].append(_write_form(directory, index, form))
    (directory / "request.json").write_text(json.dumps(request), encoding="utf-8")
    command = [str(python), "-m", "operon.env_worker", str(directory)]
    completed = subprocess.run(command, capture_output=True, text=True, encoding='utf-8',
                               errors='replace', timeout=timeout, env=worker_environment(python, paths), cwd=str(directory))
    if completed.returncode:
        tail = (completed.stderr or completed.stdout).strip().splitlines()[-6:]
        raise StepError("environment bridge failed with exit code " + str(completed.returncode) + ": " + " | ".join(tail))
    message = json.loads((directory / "result.json").read_text(encoding="utf-8"))
    if "error" in message:
        try:
            _log = Path(tempfile.gettempdir()) / 'operon-envbridge-error.log'
            _log.write_text(json.dumps({
                'python': str(python),
                'pythonpath': worker_environment(python, paths).get('PYTHONPATH', ''),
                'command': command,
                'cwd': str(directory),
                'returncode': completed.returncode,
                'stdout': completed.stdout,
                'stderr': completed.stderr,
                'error': message['error'],
                'descriptor': descriptor.get('id'),
            }, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception:
            pass
        raise StepError(message["error"])
    from src.core.forms import Form
    from operon.env_worker import _revive
    data = np.load(directory / "output.npy", allow_pickle=False)
    form = Form(data=data, dims=message["dims"], labels=message["labels"],
                info=_revive(message.get("info", {})), axis_info=message.get("axis_info", {}))
    return form, _revive(message.get("export", {})), "\n".join((completed.stderr or "").strip().splitlines()[-4:])


def proxy_step(descriptor: dict, paths=()):
    """Build a Step-compatible proxy that executes in the environment interpreter."""
    from src.task.step.base import Step
    from src.core.errors import StepError
    _paths = tuple(paths)

    class EnvironmentStep(Step):
        name = descriptor["id"]
        definition = descriptor
        version = str(descriptor.get("version") or "1.0.0")
        inputs_arity = descriptor.get("inputs_arity", 0)
        outputs = list(descriptor.get("outputs") or [])
        output_parameter = descriptor.get("output_parameter")
        parameters_schema = descriptor.get("parameters_schema")
        dependencies = descriptor.get("dependencies")
        dependency_imports = descriptor.get("dependency_imports")
        category = descriptor.get("category")
        icon = descriptor.get("icon")
        input_contracts = descriptor["contracts"]["inputs"]
        output_contract = descriptor["contracts"]["output"]
        supports_streaming = False
        _environment = (descriptor.get("resources") or {}).get("environment")

        def __init__(self):
            self._export_data = {}

        def run(self, ctx, inputs):
            python = resolve(self._environment)
            if python is None:
                raise StepError(f"{descriptor['id']}: isolated environment {self._environment!r} is not installed")
            form, export, tail = run_step(descriptor, inputs, dict(ctx.step_params), python,
                                          timeout=int(ctx.step_params.get("timeout_seconds", 3600)) + 60,
                                          paths=_paths)
            ctx[ctx.step_params["output"]] = form
            self._export_data = export
            if tail:
                print(tail, file=sys.stderr)

        def export(self, ctx):
            return self._export_data

    return EnvironmentStep
