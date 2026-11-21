"""Every environment has to provide what its operators actually import.

The hosted install used to report an environment as ready while operators bound
to it failed at run time with ``No module named 'scanpy'``: ``core`` declared
only the analysis stack, so the readiness probe never looked at the imports its
900-odd operators really needed.  The declaration is the contract, so for every
environment the union of ``dependency_imports`` over the descriptors bound to it
has to be covered by what that environment installs -- either an entry in
``imports`` (probed at readiness time), a requirement that provides the module,
or a ``best_effort`` entry, which is attempted without blocking readiness.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Distribution name -> import name, for the ones that do not normalise to each other.
ALIASES = {
    'biopython': 'bio',
    'scikit-learn': 'sklearn',
    'scikit-image': 'skimage',
    'umap-learn': 'umap',
    'viennarna': 'rna',
    'python-louvain': 'community',
    'pyyaml': 'yaml',
    'opencv-python': 'cv2',
    'pillow': 'pil',
    'python-dateutil': 'dateutil',
    'torch-geometric': 'torch_geometric',
}


def _normalise(name: str) -> str:
    key = name.strip().lower().replace('-', '_').replace('.', '_')
    return ALIASES.get(key.replace('_', '-'), key)


def _distribution(requirement: str) -> str:
    for marker in ('==', '>=', '<=', '~=', '!=', '>', '<', '[', ';', ' '):
        index = requirement.find(marker)
        if index > 0:
            return requirement[:index]
    return requirement


def _provided(entry: dict) -> set[str]:
    modules = {_normalise(name) for name in entry.get('imports') or ()}
    for requirement in entry.get('requirements') or ():
        modules.add(_normalise(_distribution(requirement)))
    return modules


def _optional(entry: dict) -> set[str]:
    """Modules an environment attempts without making readiness depend on them."""
    return {_normalise(_distribution(item)) for item in entry.get('best_effort') or ()}


def _declared():
    path = ROOT / 'library/seed/operon/environments.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    return data['environments']


def _required():
    path = ROOT / 'library/seed/operon/builtin_packages.json'
    index = json.loads(path.read_text(encoding='utf-8'))
    union: dict[str, set[str]] = {}
    for package in index['packages']:
        for descriptor in package['descriptors']:
            environment = (descriptor.get('resources') or {}).get('environment')
            if not environment:
                continue
            union.setdefault(environment, set()).update(descriptor.get('dependency_imports') or ())
    return union


def test_every_environment_provides_the_imports_its_operators_need():
    declared = _declared()
    required = _required()
    problems = []
    for environment, modules in sorted(required.items()):
        entry = declared.get(environment)
        if entry is None:
            problems.append(f'{environment}: bound by operators but not declared')
            continue
        installed = _provided(entry) | _optional(entry)
        missing = sorted(module for module in modules if _normalise(module) not in installed)
        if missing:
            problems.append(f'{environment}: does not install {", ".join(missing)}')
    assert not problems, '\n'.join(problems)


def test_core_carries_the_analysis_and_scientific_stack_its_operators_import():
    core = _declared()['core']
    imports = set(core['imports'])
    for module in ('scanpy', 'torch', 'transformers', 'umap', 'RNA', 'pdb2pqr',
                   'posebusters', 'pydeseq2', 'patsy'):
        assert module in imports, f'core must probe {module}'
    # ``vina`` ships no wheel, so building it needs SWIG: keep it best-effort so a
    # missing toolchain cannot take the whole environment down with it.
    assert 'vina' not in imports
    assert any(item.startswith('vina') for item in core['best_effort'])
    assert core.get('torch_cpu') is True


def test_esm2_carries_the_imports_inverse_folding_needs():
    esm2 = _declared()['esm2']
    assert {'biotite', 'torch_geometric'} <= set(esm2['imports'])
    assert any(item.startswith('biotite') for item in esm2['requirements'])
