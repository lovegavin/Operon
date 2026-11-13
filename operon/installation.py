"""Setup identity shared by desktop, CLI and headless profile resolution."""
import json
import os
import pathlib
from pathlib import Path
import re
import sys


def isolated_root(code_root):
    root = Path(code_root).resolve()
    if (root / 'operon-install.json').is_file():
        return root
    executable = Path(sys.executable).resolve()
    if len(executable.parents) >= 3 and executable.parent.name == 'python' and executable.parent.parent.name == 'runtime':
        candidate = executable.parents[2]
        if root.is_relative_to(candidate) and (candidate / 'operon-install.json').is_file():
            return candidate
    return None


def library_root(code_root=None):
    """Return ``<install>/versions/<version>/library`` for an installed app.

    The library, its wheels and isolated environments belong to the application
    version; the user workspace holds only data.  Returns None for a source
    checkout so development keeps its isolated state under the data directory.
    """
    candidates = []
    if code_root is not None:
        candidates.append(Path(code_root).resolve())
    try:
        import operon
        candidates.append(Path(operon.__file__).resolve())
    except Exception:  # pragma: no cover - import always succeeds in the app
        pass
    for start in candidates:
        for parent in (start, *start.parents):
            if parent.parent.name == 'versions':
                directory = parent / 'library'
                if os.name == 'nt' and str(directory).startswith('\\\\?\\'):
                    text = str(directory)
                    directory = pathlib.Path('\\\\' + text[8:] if text.startswith('\\\\?\\UNC\\') else text[4:])
                return directory
    return None


def profile_id(root):
    value = json.loads((Path(root) / 'operon-install.json').read_text(encoding='utf-8'))
    if (value.get('schema_version') != 1 or value.get('isolated') is not True or
            not re.fullmatch(r'[a-f0-9]{32}', str(value.get('profile_id', '')))):
        raise ValueError('Invalid isolated installation identity; rerun Operon Setup.')
    return value['profile_id']


def profile_namespace(root):
    """New branded installs cannot attach to an older product's profile."""
    profile_id(root)
    value = json.loads((Path(root) / 'operon-install.json').read_text(encoding='utf-8'))
    product = value.get('product', 'operon')
    if not isinstance(product, str) or product not in {'operon', 'operon'}:
        raise ValueError('Unknown installation product; rerun Operon Setup.')
    return '.' + product


def workspace_root(root):
    """Optional install-owned workspace; absent markers keep the legacy profile path."""
    root = Path(root).resolve()
    value = json.loads((root / 'operon-install.json').read_text(encoding='utf-8'))
    raw = value.get('workspace')
    if raw is None:
        return None
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError('Invalid installation workspace; rerun Operon Setup.')
    base = root.parent.parent if root.parent.name == 'versions' else root
    candidate = Path(os.path.expandvars(raw))
    if not candidate.is_absolute():
        candidate = base / candidate
    candidate = candidate.resolve()
    if candidate == base or not candidate.is_relative_to(base):
        raise ValueError('Installation workspace must be inside the installation root; rerun Operon Setup.')
    return candidate


def configure_environment(code_root):
    """Also isolate direct CLI/MCP starts, which do not pass through the EXE."""
    root = isolated_root(code_root)
    if root is None:
        return
    profile_namespace(root)  # Reject an invalid identity/product before changing the environment.
    for key in list(os.environ):
        upper = key.upper()
        if upper.startswith(('OPERON_', 'PYTHON', 'CONDA')) or upper in {
            'VIRTUAL_ENV', 'R_HOME', 'R_LIBS', 'R_LIBS_USER', 'R_PROFILE', 'R_ENVIRON',
            'PIP_TARGET', 'PIP_PREFIX', 'PIP_USER', 'PIP_REQUIRE_VIRTUALENV'}:
            del os.environ[key]
    python = root / 'runtime/python'
    windows = Path(os.environ.get('SystemRoot', str(Path(sys.executable).anchor)))
    os.environ['PATH'] = os.pathsep.join(map(str, (python, python / 'Scripts', windows / 'System32', windows)))
    os.environ['PYTHONNOUSERSITE'] = '1'
    os.environ['PIP_CONFIG_FILE'] = os.devnull
