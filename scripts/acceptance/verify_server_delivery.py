"""Install exact Linux delivery bytes and exercise installed CLI/portable export.

Only synthetic inputs and a fresh caller-owned work directory are used. Runtime
acquisition is explicit and hash-bound; no operator library is installed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--runtime-sha256', required=True)
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
    if sys.platform != 'linux':
        parser.error('Linux target required')
    with args.archive.open('rb') as stream:
        assert hashlib.file_digest(stream, 'sha256').hexdigest() == args.sha256
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=False)
    report = {'status': 'failed', 'archive_sha256': args.sha256, 'commands': []}
    python = None
    workspace = work / 'workspace'; workspace.mkdir()
    env = {**os.environ, 'OPERON_ADMISSION_DIR': str(work / 'admission'),
           'PYTHONDONTWRITEBYTECODE': '1'}

    def run(argv, *, timeout=600, check=True, environment=None, cwd=None):
        start = time.monotonic()
        item = subprocess.run(list(map(str, argv)), cwd=cwd or work, env=environment or env,
                              capture_output=True, text=True, timeout=timeout)
        index = len(report['commands'])
        (work / f'{index:03}.stdout').write_text(item.stdout)
        (work / f'{index:03}.stderr').write_text(item.stderr)
        report['commands'].append({'argv': list(map(str, argv)), 'exit': item.returncode,
                                   'seconds': round(time.monotonic() - start, 3)})
        if check and item.returncode:
            raise RuntimeError(f'Command failed: {argv!r}\n{item.stderr[-8000:]}\n{item.stdout[-8000:]}')
        return item

    def cli(*words, **kwargs):
        return json.loads(run([python, '-I', '-m', 'operon', '--workspace', workspace,
                               *words], **kwargs).stdout)

    try:
        bundle = work / 'delivery'
        with zipfile.ZipFile(args.archive) as archive:
            for member in archive.namelist():
                if not (bundle / member).resolve().is_relative_to(bundle):
                    raise ValueError('Archive escapes delivery directory')
            archive.extractall(bundle)
        installer = next(bundle.rglob('install.sh'))
        run(['bash', installer, '--prefix', work / 'installation', '--python', sys.executable,
             '--result', work / 'installation.json'], timeout=900)
        installed = json.loads((work / 'installation.json').read_text())
        assert installed['status'] == 'installed', installed
        python = installed['python']
        report['installed_version'] = run([python, '-I', '-m', 'operon', '--version']).stdout.strip()
        helper = Path(__file__).with_name('prepare_linux_generation.py').resolve()
        fixture = workspace / 'fixture'
        run([python, helper, '--runtime', args.runtime.resolve(), '--sha256', args.runtime_sha256,
             '--work', fixture], timeout=900)
        os.rename(fixture / 'store', fixture / 'env')
        source = run([python, '-I', '-c',
            'import operon;from pathlib import Path;print(Path(operon.__file__).resolve().parent.parent)']).stdout.strip()
        prepare = next(bundle.rglob('prepare_desktop_plan.py'))
        script = (
            'import runpy,json,sys;from pathlib import Path;'
            'from operon.contracts.run_plan import EnvironmentRequirement;'
            'w=Path(sys.argv[2]);f=w/"fixture";e=json.loads((f/"environment.json").read_text());'
            'r=runpy.run_path(sys.argv[1])["write_fixture"](w,"fixture",Path(sys.argv[3]),'
            'EnvironmentRequirement.model_validate(e["requirement"]),e["binding"]["generation_id"],e["executable"]);'
            'print(json.dumps(r))')
        run([python, '-I', '-c', script, prepare, workspace, source])
        request = json.loads((fixture / 'compile-request.json').read_text())
        for name in ('workflow', 'parameters', 'inputs', 'environments'):
            (fixture / (name + '.json')).write_text(json.dumps(request[name]))
        plan = fixture / 'plan.json'
        compiled = cli('plan', 'compile', fixture/'workflow.json', '--parameters', fixture/'parameters.json',
                       '--inputs', fixture/'inputs.json', '--environments', fixture/'environments.json',
                       '--initial', '--require-files', '--output', plan)
        accepted = cli('plan', 'submit', plan, '--binding', fixture/'binding.json', '--request-id', 'delivery-run')
        run_id = accepted['run_id']
        assert cli('plan', 'submit', plan, '--binding', fixture/'binding.json',
                   '--request-id', 'delivery-run')['run_id'] == run_id
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            details = cli('plan', 'details', run_id)
            if details['state'] in ('complete', 'failed', 'cancelled'):
                break
            time.sleep(1)
        assert details['state'] == 'complete', details
        report['run'] = details
        report['events'] = cli('plan', 'events', run_id)
        report['artifacts'] = cli('plan', 'artifacts', run_id)
        export = json.loads((fixture/'export-request.json').read_text()); export.pop('plan')
        (fixture/'cli-export.json').write_text(json.dumps(export))
        submitted = cli('plan', 'export', plan, '--request', fixture/'cli-export.json')
        deadline = time.monotonic() + 900
        while time.monotonic() < deadline:
            result = cli('plan', 'export-status', submitted['id'])
            if result['status'] in ('complete', 'failed', 'cancelled', 'unknown'):
                break
            time.sleep(2)
        assert result['status'] == 'complete', result
        report['export'] = result
        cli('service', 'stop')
        moved = work / 'relocated package'
        shutil.copytree(workspace/export['output'], moved, symlinks=True)
        home = work / 'isolated-home'; home.mkdir()
        portable = run(['/bin/sh', moved/'run.sh', '--memory', str(256*1024**2), '--threads', '1'],
                       environment={'PATH': '/usr/bin:/bin', 'HOME': str(home),
                                    'PYTHONNOUSERSITE': '1', 'PYTHONDONTWRITEBYTECODE': '1'},
                       cwd=home, timeout=600)
        result = json.loads(portable.stdout)
        assert result['status'] == 'complete', result
        published = json.loads((Path(result['results'])/'second.json').read_text())
        value = json.loads(Path(published['outputs']['result']['path']).read_text())
        assert value == {'value': 42}, value
        report.update(status='passed', portable=result, final_value=value, plan_id=compiled['plan_id'])
    except BaseException:
        report['error'] = traceback.format_exc()
    finally:
        if python:
            run([python, '-I', '-m', 'operon', '--workspace', workspace, 'service', 'stop'], check=False)
        (work/'report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({'status': report['status'], 'report': str(work/'report.json'),
                      'error': report.get('error')}, indent=2))
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
