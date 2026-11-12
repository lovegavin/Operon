"""Package an already-built Windows host and Python source, without user data."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tomllib
import zipfile
import urllib.request

from audit_portability import audit_files
from operon.bytecode import io_path


def _windows_path(path):
    """PowerShell needs a Windows path when this builder runs under WSL."""
    if os.name == 'nt' or not shutil.which('wslpath'):
        return str(path)
    return subprocess.check_output(['wslpath', '-w', str(path)], text=True).strip()


def verify_frontend_versions(frontend):
    """Reject a build made with dependencies different from its declared lock."""
    lock = json.loads((frontend / 'package-lock.json').read_text(encoding='utf-8'))
    for directory, declared in lock['packages'].items():
        if not directory or declared.get('link'):
            continue
        metadata = frontend / directory / 'package.json'
        # Platform-specific optional packages are absent on other build hosts.
        if not metadata.is_file():
            continue
        installed = json.loads(metadata.read_text(encoding='utf-8')).get('version')
        if installed != declared.get('version'):
            raise ValueError(f'Frontend dependency differs from lock: {directory} '
                             f'(installed {installed}, locked {declared.get("version")}). Run npm ci before building.')
    return lock


def verify_runtime_package(python_root, version):
    """Reject a runtime that carries a different application package version."""
    packages = Path(python_root) / 'Lib' / 'site-packages'
    init = packages / 'operon' / '__init__.py'
    if not init.is_file():
        raise SystemExit(f'Bundled runtime is missing operon: {init}')
    match = re.search(r'__version__\s*=\s*[\'\"]([^\'\"]+)', init.read_text(encoding='utf-8'))
    found = match.group(1) if match else 'unknown'
    if found != version:
        raise SystemExit(f'Bundled runtime carries operon {found}, expected {version}. '
                         'Rebuild it with scripts/build_runtime.py for this release.')
    metadata = sorted(packages.glob('operon_studio-*.dist-info'))
    names = {item.name for item in metadata}
    expected = f'operon_studio-{version}.dist-info'
    if names != {expected}:
        raise SystemExit(f'Bundled runtime distribution metadata is {sorted(names)}, expected {expected}.')
    return found


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--desktop', type=Path, default=root / 'dist/Operon Studio')
    parser.add_argument('--output', type=Path, default=root / 'dist/releases')
    parser.add_argument('--runtime', type=Path, help='Portable Python directory produced by build_runtime.py')
    parser.add_argument('--webview-bootstrapper', type=Path, help='Optional cached official Microsoft WebView2 bootstrapper; signature is verified')
    parser.add_argument('--lite', action='store_true', help='Smaller package requiring an existing Python environment')
    args = parser.parse_args()
    if not args.lite and (not args.runtime or not (args.runtime / 'operon-runtime.json').is_file()):
        parser.error('Full releases require --runtime from build_runtime.py; use --lite only for an environment-free package')
    version = tomllib.loads((root / 'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
    name = f'Operon-Studio-v{version}-Windows-x64' + ('-Lite' if args.lite else '')
    destination = io_path(args.output.resolve() / name)
    if destination.exists():
        parser.error(f'Output already exists: {destination}')
    if not (args.desktop / 'Operon Studio.exe').is_file():
        parser.error('Build the desktop host first.')
    lock = verify_frontend_versions(root / 'frontend')
    destination.mkdir(parents=True)

    def copy(source, rel):
        target = destination / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    copy(args.desktop / 'Operon Studio.exe', 'Operon Studio.exe')
    if not args.lite:
        shutil.copytree(io_path(args.runtime), destination / 'runtime/python')
        copy(root / 'scripts/bundled_paths.pth', 'runtime/python/Lib/site-packages/00_operon_paths.pth')
        copy(root / 'scripts/bundled_imports.py', 'runtime/python/Lib/operon_import_paths.py')
        verify_runtime_package(destination / 'runtime/python', version)
        bootstrapper = destination / 'runtime/MicrosoftEdgeWebview2Setup.exe'
        url = 'https://go.microsoft.com/fwlink/p/?LinkId=2124703'
        if args.webview_bootstrapper:
            shutil.copy2(args.webview_bootstrapper, bootstrapper)
        else:
            with urllib.request.urlopen(url, timeout=90) as response, bootstrapper.open('wb') as output:
                shutil.copyfileobj(response, output)
        # Verify the executable's Authenticode signature before redistribution.
        subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File',
                        _windows_path(root / 'scripts/verify_microsoft_signature.ps1'),
                        _windows_path(bootstrapper)], check=True)
        (destination / 'runtime/webview2.json').write_text(json.dumps({'source': url,
            'sha256': hashlib.sha256(bootstrapper.read_bytes()).hexdigest()}), encoding='utf-8')
    shutil.copytree(root / 'frontend/dist', destination / 'frontend')
    for directory in ('src', 'operon', 'operon_sdk', 'operon', 'library/seed'):
        for source in (root / directory).rglob('*'):
            if source.is_file() and source.suffix.lower() in {'.py', '.json', '.md', '.png', '.jpg', '.jpeg', '.webp', '.gif', '.svg'}:
                copy(source, source.relative_to(root))
    for source in (root / 'tasks').rglob('*'):
        if source.is_file() and source.suffix in {'.py', '.yaml', '.yml', '.json'} and 'output' not in source.relative_to(root).parts:
            copy(source, source.relative_to(root))
    for source in (root / 'library/seed/routes').rglob('*'):
        if source.is_file() and source.suffix in {'.json', '.yaml', '.yml'}:
            copy(source, source.relative_to(root))
    for source in root.glob('requirements*.txt'):
        copy(source, source.name)
    for source in root.glob('constraints*.txt'):
        copy(source, source.name)
    for name_ in ('README.md', 'pyproject.toml', 'LICENSE', 'NOTICE'):
        copy(root / name_, name_)
    for name_ in ('release.json', 'pyproject.toml', 'README.md'):
        if (root / 'library' / name_).is_file():
            copy(root / 'library' / name_, Path('library') / name_)
    for name_ in ('desktop_server.py', 'install_maintenance.py', 'install_server.py', 'install_server.sh', 'run.py', 'diagnose_pins.py',
                  'accept_igv_handoff.py', 'open_igv_handoff.ps1',
                  'verify_release_agent.py', 'verify_release_agent.md', 'verify_operon_candidate.py', 'verify_server_cli.py',
                  'check_resources.py', 'provision_resources.py'):
        copy(root / 'scripts' / name_, Path('scripts') / name_)
    if not args.lite:
        python = destination / 'runtime/python/python.exe'
        # Use the shipped interpreter, never the packaging host's Python tag.
        subprocess.run([python, '-I', '-m', 'compileall', '-q', '-f',
                        '--invalidation-mode', 'unchecked-hash', '-s', str(destination),
                        *[str(destination / p) for p in ('src', 'operon', 'operon_sdk', 'operon', 'scripts', 'library/seed',
                                                       'runtime/python/Lib/operon_import_paths.py')]], check=True)
    shutil.copytree(root / 'docs', destination / 'docs', ignore=shutil.ignore_patterns('verification'))
    # Ship the small SDK examples referenced by the extension guides.
    shutil.copytree(root / 'examples', destination / 'examples',
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'build', 'dist', '*.egg-info'))
    shutil.copytree(root / 'THIRD_PARTY_NOTICES', destination / 'THIRD_PARTY_NOTICES')
    # Regenerate frontend notices from the lockfile actually used for this build.
    notices = ['Licenses for bundled frontend dependencies.\n']
    for directory, meta in sorted(lock['packages'].items()):
        if not directory or (meta.get('dev') and directory not in ('node_modules/tailwindcss', 'node_modules/vite')):
            continue
        module = root / 'frontend' / directory
        licenses = [p for p in module.iterdir() if p.is_file() and p.name.lower().startswith(('license', 'notice', 'copying'))]
        if not licenses:
            raise RuntimeError(f'Missing license text for {directory}')
        notices.append(f'\n{"=" * 72}\n{directory} {meta["version"]}\n')
        notices.extend(p.read_text(encoding='utf-8-sig') for p in sorted(licenses))
    (destination / 'THIRD_PARTY_NOTICES/frontend-licenses.txt').write_text('\n'.join(notices), encoding='utf-8')
    (destination / 'operon-desktop.json').write_text(json.dumps({
        'backendRoot': '.', 'python': 'auto', 'entryPoint': 'scripts/desktop_server.py', 'frontend': 'frontend',
        'bundledRuntime': not args.lite,
    }, indent=2) + '\n', encoding='utf-8')
    command = 'python -m operon' if args.lite else '"%~dp0runtime\\python\\python.exe" -I -m operon'
    (destination / 'operon.cmd').write_text('@echo off\n' + command + ' %*\n', encoding='ascii')
    (destination / 'START_HERE.txt').write_text(f"""Operon Studio {version} - Windows x64

Use Operon_Setup.exe for installation. It owns its management Python and creates a
new isolated profile; previous Operon installations and profiles are retained.
Double-click the installed Operon Studio shortcut. First-time WebView2 setup
may need an internet connection. Do not move individual installed files.

Start with docs/quickstart.md for your first Windows or Linux workflow.
Operon is open source under Apache-2.0; see LICENSE and NOTICE.

The operator library remains independently versioned. Existing v3/v3.5 packages,
.operon workflow bundles, Python imports and MCP identifiers stay compatible.
Use operon.cmd for the bundled CLI or runtime/python/python.exe -I -m operon.
Registration and startup read metadata; scientific dependencies are checked for
the selected execution target at Validate/Run. Missing environments or packages
require explicit Prepare environment; conflict isolation uses the same Python
with private dependency directories and managed worker processes.
The default Setup does not include PyTorch, Pandas, SciPy or plotting packages.
NumPy remains the Form/memory/preview foundation. Local analysis dependencies
are downloaded only after explicit preparation into profile-owned targets;
the application runtime is never pip-upgraded in place. Remote-only routes do
not prepare local analysis targets. First analysis preparation needs networking.

Each workflow keeps frozen parameters.json and independent execution.json.
Import Python/R/C/C++ file scripts, edit code or parameters, and export formatted
YAML. Python literal extraction uses the original imported values as defaults.
Type-safe representation conversions are shown on edges; semantic type changes
require explicit operators. Agent edits are visible transactions with undo.

Settings groups Servers, Outputs and viewers, Appearance, and Language.
Open saved PNG/PDF/SVG figures from run history or configured specialist viewers.
SSH connections reuse a registered server; installation is explicit maintenance.
Computation, memory admission and streaming remain on the execution host.

For supported scope, acceptance procedures and remaining roadmap work, read
  docs/OPERON_3_TEST_ACCEPTANCE.md
  docs/V3_IMPLEMENTATION.md
  docs/rebranding.md
The release page records the validation completed for this exact build.
""", encoding='utf-8')
    audit = audit_files((p for p in destination.rglob('*') if p.is_file()
                        and not {'THIRD_PARTY_NOTICES', 'runtime'}.intersection(p.relative_to(destination).parts)), destination)
    if audit['findings']:
        raise RuntimeError('Developer paths in release: ' + json.dumps(audit['findings']))
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    runtime_mode = 'external' if args.lite else json.loads((args.runtime / 'operon-runtime.json').read_text(encoding='utf-8')).get('mode', 'bundled')
    manifest = {'product': 'operon', 'version': version, 'runtime_mode': runtime_mode, 'source_commit': commit,
                'source_dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=root, text=True).strip()), 'python_bundled': not args.lite, 'files': []}
    for file in sorted(destination.rglob('*')):
        if file.is_file():
            manifest['files'].append({'path': file.relative_to(destination).as_posix(), 'bytes': file.stat().st_size,
                                      'sha256': hashlib.sha256(file.read_bytes()).hexdigest()})
    (destination / 'package-manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    archive = destination.parent / (name + '.zip')
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        for file in sorted(destination.rglob('*')):
            if file.is_file():
                output.write(file, (Path('Operon Studio') / file.relative_to(destination)).as_posix())
    with zipfile.ZipFile(archive) as check:
        assert check.testzip() is None
    print(json.dumps({'archive': str(archive), 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'files': len(manifest['files'])}))


if __name__ == '__main__':
    main()
