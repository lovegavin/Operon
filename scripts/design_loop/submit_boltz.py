import json
import subprocess
import sys
from pathlib import Path

PY = r'D:\OperonTest517rc7\versions\5.1.17-f397f8157e17\runtime\python\python.exe'
ROOT = Path(r'D:\OperonTest517rc7\workspace\design_loop\round4')
GRAPHS = ROOT / 'graphs'
GRAPHS.mkdir(exist_ok=True)

BOLTZ_PARAMS = {
    'boltz_path': r'D:\OperonTest517rc7\workspace\rf_boltz\boltz_cli.py',
    'cache_dir': r'C:\Users\梦天曦\.local\share\operon\resources\boltz',
    'model': 'boltz1',
    'device': 'cuda',
    'sampling_steps': 20,
    'diffusion_samples': 1,
    'interface_cutoff': 8,
    'timeout_seconds': 3600,
    'report_dim': 'residue',
    'sequence_dim': 'sequence',
    'position_dim': 'position',
    'output': 'confidence',
}

results = []
for index in range(1, 9):
    graph = {
        'schema_version': 2,
        'name': f'round4 boltz design {index}',
        'base_dir': str(ROOT / 'complexes'),
        'nodes': [
            {
                'id': 'fa', 'kind': 'source', 'operator': None, 'title': 'fa',
                'params': {}, 'input_count': 1,
                'source': {
                    'reader': 'FastaReader', 'path': f'design_{index}.fa',
                    'dims': ['sequence', 'position'],
                    'labels': {'position': 'auto', 'sequence': 'builtin'},
                    'args': {'alphabet': 'auto'}, 'location': None,
                },
            },
            {
                'id': 'boltz', 'kind': 'operator', 'operator': 'boltz_complex_confidence',
                'title': 'boltz', 'input_count': 1, 'params': BOLTZ_PARAMS,
            },
        ],
        'edges': [{'id': 'e1', 'source': 'fa', 'sourceHandle': 'out',
                   'target': 'boltz', 'targetHandle': 'in-0'}],
        'memory': {'enabled': True},
        'runtime': {'execution': {'kind': 'local'}},
        'params': {}, 'manifest_extra': {}, 'interface': None, 'plugin_lock': {},
    }
    path = GRAPHS / f'design_{index}.json'
    path.write_text(json.dumps(graph, indent=2), encoding='utf-8')
    out = subprocess.run(
        [PY, '-m', 'operon', '--workspace', r'D:\OperonTest517rc7\workspace',
         '--data-dir', r'D:\OperonTest517rc7\workspace\.studio', 'run', str(path),
         '--request-id', f'round4-boltz-{index}', '--brief'],
        capture_output=True, text=True, timeout=180,
    )
    if out.returncode != 0:
        results.append({'design': index, 'error': out.stderr[-400:]})
        continue
    payload = json.loads(out.stdout)
    results.append({'design': index, 'id': payload['id'], 'status': payload['status'],
                    'reused': payload.get('reused')})

print(json.dumps(results, indent=1))
