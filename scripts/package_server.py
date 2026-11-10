"""Build a version-consistent Linux bundle from explicit application/library wheels."""
import argparse
import hashlib
from pathlib import Path
import tomllib
import zipfile


def build(root, application, library, output):
    root, application, library, output = map(Path, (root, application, library, output))
    version = tomllib.loads((root / 'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
    if application.name != f'operon_studio-{version}-py3-none-any.whl':
        raise ValueError('Application wheel must match the source release version')
    if not library.name.startswith('operon_builtin_library-') or library.suffix != '.whl':
        raise ValueError('Expected the independently versioned factory library wheel')
    files = {'wheels/' + p.name: p.read_bytes() for p in (application, library)}
    for name in ('LICENSE', 'NOTICE', 'scripts/install_server.py', 'scripts/install_server.sh'):
        files[name] = (root / name).read_bytes()
    for folder in ('docs', 'examples/workflows/script_pipeline'):
        for path in (root / folder).rglob('*'):
            if path.is_file() and path.suffix in {'.md', '.py', '.json', '.yaml', '.yml'} and '__pycache__' not in path.parts:
                files[path.relative_to(root).as_posix()] = path.read_bytes()
    # Generate from the actual selected wheels, never copy an older release wrapper.
    files['install.sh'] = ('''#!/usr/bin/env bash
set -euo pipefail
bundle_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
exec bash "$bundle_dir/scripts/install_server.sh" \\
  --app-wheel "$bundle_dir/wheels/APP" \\
  --library-wheel "$bundle_dir/wheels/LIBRARY" "$@"
'''.replace('APP', application.name).replace('LIBRARY', library.name)).encode()
    files['README.md'] = f'''# Operon {version} Linux server

From this extracted directory:

```sh
bash install.sh --prefix "$HOME/apps/operon" --result "$PWD/server-install.json"
```

The installer selects the included application and unchanged independent library
wheels. Python dependencies require networking. If no usable Python 3.11+ exists,
Linux x86_64 can bootstrap a checksum-verified private Python without sudo. Use
`--python` and `--wheel-dir` for a supplied Python and offline dependency wheels.

Read `install_dir`, `workspace`, `command` and `log` from the result JSON. An
occupied prefix uses an Operon child; it is not necessarily the requested path.
Reinstallation retains workspace data and creates a fresh runtime generation.

```sh
"$HOME/apps/operon/bin/operon" --version
mkdir -p "$HOME/apps/operon/workspace"
cp -R examples/workflows/script_pipeline "$HOME/apps/operon/workspace/demo"
"$HOME/apps/operon/bin/operon" environment check "$HOME/apps/operon/workspace/demo/workflow.yaml"
"$HOME/apps/operon/bin/operon" run "$HOME/apps/operon/workspace/demo/workflow.yaml" --progress --brief
"$HOME/apps/operon/bin/operon" service stop
```

The example uses standard-library Python scripts. Scientific dependencies are
prepared explicitly for the selected execution environment. Existing server
installations can be selected in the desktop SSH settings. The shared pool starts
automatically; see [quick start](docs/quickstart.md), [pool setup](docs/design/pool_service.md), [server CLI](docs/server_cli.md),
[installation](docs/command_line_installation.md), [stage cache](docs/stage_cache.md)
and [release notes](docs/releases/v{version}.md).
'''.encode()
    files['SHA256SUMS'] = ''.join(f'{hashlib.sha256(data).hexdigest()}  {name}\n'
                                for name, data in sorted(files.items())).encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            item = zipfile.ZipInfo(f'Operon-{version}-Server/{name}')
            item.create_system = 3
            item.external_attr = (0o100755 if name.endswith('.sh') else 0o100644) << 16
            item.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(item, data)
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app-wheel', type=Path, required=True)
    parser.add_argument('--library-wheel', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(build(Path(__file__).resolve().parents[1], args.app_wheel, args.library_wheel, args.output))
