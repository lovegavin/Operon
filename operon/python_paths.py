"""Stdlib-only Python import/resource paths, shared by probes and workers.

This changes process-local path spelling, not filesystem ownership, runtime
identity, dependency order or global Windows configuration.
"""
import importlib
import importlib.machinery
import json
import os
from pathlib import Path
import sys

PYTHON_PATH_ABI = 'operon-python-paths-v1'


def python_path(value):
    """Preserve search semantics; extend only absolute Windows filesystem paths."""
    if not isinstance(value, str) or not value or not os.path.isabs(value) or os.name != 'nt':
        return value
    value = os.path.abspath(value)
    if value.startswith('\\\\?\\'):
        return value
    return '\\\\?\\UNC\\' + value[2:] if value.startswith('\\\\') else '\\\\?\\' + value


def configure_python_paths(paths=()):
    """Prepend explicit owned paths, then repair cached filesystem loaders too.

    sys.path alone is insufficient once importlib has cached a package loader.
    FileReader obtains resource roots from loader.path; spec.origin and __file__
    must agree. Namespace packages keep their lazy path object/recalculation.
    No .pth, user site or operator code is executed here.
    """
    sys.path[:] = [python_path(p) for p in [*map(os.fspath, paths), *sys.path]]
    if os.name != 'nt':
        return
    loaders = (importlib.machinery.SourceFileLoader, importlib.machinery.SourcelessFileLoader,
               importlib.machinery.ExtensionFileLoader)
    for module in tuple(sys.modules.values()):
        if module is None:
            continue
        spec = getattr(module, '__spec__', None)
        loader = getattr(spec, 'loader', None)
        # Some stdlib packages are frozen but still search a filesystem tree.
        for paths in (getattr(module, '__path__', None), getattr(spec, 'submodule_search_locations', None)):
            if isinstance(paths, list):
                paths[:] = [python_path(p) for p in paths]
        if not isinstance(loader, loaders):
            continue
        loader.path = python_path(loader.path)
        for name in ('__file__', '__cached__'):
            value = getattr(module, name, None)
            if isinstance(value, str):
                setattr(module, name, python_path(value))
        spec.origin = python_path(spec.origin)
        if isinstance(spec.cached, str):
            spec.cached = python_path(spec.cached)
    importlib.invalidate_caches()


# END EMBEDDED PYTHON PATH BOOTSTRAP
from functools import lru_cache


@lru_cache(maxsize=1)
def bootstrap_source():
    """Embed the same stdlib implementation where application code is unavailable."""
    source = Path(python_path(str(Path(__file__).absolute()))).read_text(encoding='utf-8')
    return source.split('\n# END EMBEDDED PYTHON PATH BOOTSTRAP\n', 1)[0] + '\n'


def bootstrap_code(code, *, paths_expression='()'):
    """Internal code generator, not an evaluator for user-supplied expressions."""
    return bootstrap_source() + '\nconfigure_python_paths(' + paths_expression + ')\n' + code
