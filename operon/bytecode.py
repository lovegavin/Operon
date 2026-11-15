"""Compile immutable installations once with the interpreter that executes them."""
import importlib.util
import json
import py_compile
import os
from pathlib import Path
import sys


def filesystem_path(path, *, resolve=True):
    # Snapshot/cache I/O must preserve links until their own validation runs.
    # Resolving first would hide a linked source file from the snapshot guard.
    value = str(Path(path).resolve()) if resolve else os.path.abspath(path)
    if os.name == 'nt' and not value.startswith('\\\\?\\'):
        return '\\\\?\\UNC\\' + value[2:] if value.startswith('\\\\') else '\\\\?\\' + value
    return value


def io_path(path):
    """Native I/O alias without following the caller's lexical symlink boundary."""
    return Path(filesystem_path(path, resolve=False))


def enable_long_import_paths():
    """Normalize Windows search paths, including packages loaded at startup.

    Updating sys.path alone cannot repair importlib's already cached __path__.
    CPython loads that package before the invocation bootstrap runs.
    """
    if os.name != 'nt':
        return
    def normalize(paths):
        return [str(io_path(p)) if p and os.path.isabs(p) else p for p in paths]
    sys.path[:] = normalize(sys.path)
    for module in tuple(sys.modules.values()):
        paths = getattr(module, '__path__', None)
        if isinstance(paths, list):
            paths[:] = normalize(paths)
    importlib.invalidate_caches()


def executable_path(path):
    """Use normal Win32 spelling when possible; extend only genuinely long paths.

    Some third-party CRT runtimes derive their installation root from argv[0]
    and cannot open their resources with a gratuitous extended-path prefix.
    Keep lexical junction aliases intact; they are validated by their owner.
    """
    value = os.path.abspath(path)
    if os.name != 'nt':
        return value
    if value.startswith('\\\\?\\UNC\\'):
        value = '\\\\' + value[8:]
    elif value.startswith('\\\\?\\'):
        value = value[4:]
    return value if len(value.encode('utf-16-le')) // 2 < 260 else filesystem_path(value, resolve=False)


def precompile(directory, *, immutable=True):
    # Directory traversal and a single large compilation can both block. Keep
    # all of that work outside the dependency repair thread, under the same
    # cancellation/descendant ownership as pip and dependency probes.
    from operon.plugins import run_process
    output = run_process([sys.executable, '-I', '-S', str(Path(__file__).resolve()),
                          filesystem_path(directory), 'immutable' if immutable else 'checked'], timeout=600)
    return json.loads(output)


def _compile(directory, *, immutable=True):
    directory = Path(directory)
    mode = (py_compile.PycInvalidationMode.UNCHECKED_HASH if immutable
            else py_compile.PycInvalidationMode.CHECKED_HASH)
    directory = Path(filesystem_path(directory))
    sources = list(directory.rglob('*.py'))
    for source in sources:
        py_compile.compile(str(source), cfile=importlib.util.cache_from_source(str(source)),
                           dfile=source.relative_to(directory).as_posix(), doraise=True,
                           invalidation_mode=mode, optimize=0)
    missing = [str(p) for p in sources if not Path(importlib.util.cache_from_source(str(p))).is_file()]
    if missing:
        raise ValueError(f"Incomplete bytecode coverage: {missing[:5]}")
    return {"sources": len(sources), "compiled": len(sources), "mode": mode.name.lower()}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory')
    parser.add_argument('mode', choices=['immutable', 'checked'])
    args = parser.parse_args()
    print(json.dumps(_compile(args.directory, immutable=args.mode == 'immutable')))
