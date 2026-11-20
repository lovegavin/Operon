"""Execute one step inside an isolated interpreter; invoked by operon.environments."""
from __future__ import annotations

import importlib
import json
import os
import sys
import traceback
from pathlib import Path

class _Memory:
    """Minimal stand-in for the host memory object inside the bridge."""

    def __init__(self, run_dir):
        self.run_dir = run_dir
        self.data_dir = run_dir
        self.cache_dir = run_dir


class Context:
    def __init__(self, params, directory=None):
        self.step_params = params
        self.params = {}
        self.manifest = {}
        self.metadata = {}
        self.artifacts = {}
        self.out_dir = Path(directory) if directory else Path.cwd()
        self.memory = _Memory(self.out_dir)
        self.values = {}

    def artifact_path(self, relative: str) -> Path:
        """Resolve a path inside this run's output directory, creating parents."""
        target = self.out_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    def __setitem__(self, key, value):
        self.values[key] = value

    def __getitem__(self, key):
        return self.values[key]

    def event(self, *args, **kwargs):
        pass


def _revive(value):
    if isinstance(value, dict):
        if set(value) == {"__float__"}:
            return float(value['__float__'])
        if set(value) == {"__labelencoder__"}:
            from src.core.encoding import LabelEncoder
            encoder = LabelEncoder()
            encoder.mapping = {k: int(v) for k, v in value["__labelencoder__"].items()}
            encoder.inverse = {code: label for label, code in encoder.mapping.items()}
            return encoder
        return {k: _revive(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_revive(v) for v in value]
    return value


def _prepend_environment_path() -> None:
    """Expose the executing environment's executables to child processes."""
    executable = Path(sys.executable).resolve()
    directories = [executable.parent]
    scripts = executable.parent / "Scripts"
    if scripts.is_dir():
        directories.append(scripts)
    current = os.environ.get("PATH", "")
    parts = [str(item) for item in directories]
    if current:
        parts.append(current)
    os.environ["PATH"] = os.pathsep.join(parts)


def main():
    _prepend_environment_path()
    directory = Path(sys.argv[1])
    request = json.loads((directory / "request.json").read_text(encoding="utf-8"))
    try:
        from src.core.forms import Form
        module, name = request["entry_point"].split(":", 1)
        cls = getattr(importlib.import_module(module), name)
        inputs = []
        from src.core.files import FileArtifact
        for index, meta in enumerate(request["inputs"]):
            if meta.get("kind") == "file":
                inputs.append(FileArtifact(
                    format=meta["format"],
                    files={str(key): str(value) for key, value in meta["files"].items()},
                    info=_revive(meta.get("info", {})),
                    fingerprints={str(key): dict(value)
                                  for key, value in (meta.get("fingerprints") or {}).items()}))
                continue
            import numpy as np
            data = np.load(directory / f"input{index}.npy", allow_pickle=False, mmap_mode='c')
            inputs.append(Form(data=data, dims=meta["dims"], labels=meta["labels"],
                               info=_revive(meta.get("info", {})), axis_info=meta.get("axis_info", {})))
        ctx = Context(request["params"], directory)
        step = cls()
        step.run(ctx, inputs)
        export = step.export(ctx) or {}
        output_name = request["params"].get("output")
        form = ctx.values.get(output_name) if output_name else None
        if form is None:
            (directory / "result.json").write_text(
                json.dumps({"kind": "none", "export": _jsonable(export)}), encoding="utf-8")
            return
        if isinstance(form, FileArtifact):
            result = {"kind": "file", "format": form.format,
                      "files": {str(key): str(value) for key, value in form.files.items()},
                      "info": _jsonable(form.info),
                      "fingerprints": {str(key): dict(value)
                                        for key, value in form.fingerprints.items()},
                      "export": _jsonable(export)}
        else:
            import numpy as np
            np.save(directory / "output.npy", np.asarray(form.data))
            result = {"dims": list(form.dims), "labels": {k: dict(v) for k, v in form.labels.items()},
                      "info": _jsonable(form.info), "axis_info": _jsonable(form.axis_info),
                      "export": _jsonable(export)}
    except Exception as exc:  # noqa: BLE001 - returned to the parent process
        traceback.print_exc(file=sys.stderr)
        message = str(exc)
        if type(exc).__name__ == "StepError":
            message = str(exc)
        result = {"error": message}
    (directory / "result.json").write_text(json.dumps(result), encoding="utf-8")


def _jsonable(value):
    from operon.environments import _jsonable as encode
    return encode(value)


if __name__ == "__main__":
    main()
