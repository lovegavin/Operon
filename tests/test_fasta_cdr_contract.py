"""Real FASTA reader -> Kabat CDR contract propagation and edge diagnosis."""
from pathlib import Path
import time

import pytest

from biopipe.application import Application
from src.web.models import Graph
from src.web.operator_catalog import catalog_from_descriptors
from src.web.service import Settings

ROOT = Path(__file__).resolve().parents[1]
VHH = (
    "DVQLQASGGGSVQAGGSLRLSCAASGYTIGPYCMGWFRQAPGKEREGVAAINMGGGITYYA"
    "DSVKGRFTISQDNAKNTVYLLMNSLEPEDTAIYYCAADSTIYASYYECGHGLSTGGYGYDS"
    "WGQGTQVTVSSGRYPYDVPDYGSGRA"
)


def graph(root, path='vhh.fasta', reader='FastaReader'):
    source = {'path': path, 'dims': ['sequence', 'position'],
              'labels': {'sequence': 'builtin', 'position': 'auto'}}
    if reader:
        source['reader'] = reader
    return Graph.model_validate({
        'schema_version': 2, 'name': 'VHH CDR contract', 'base_dir': str(root),
        'memory': {'enabled': True, 'auto_spill': True, 'budget_mb': 64,
                   'process_limit_mb': 512},
        'nodes': [{'id': 'fasta', 'kind': 'source', 'position': {'x': 0, 'y': 0},
                   'source': source},
                  {'id': 'cdr', 'kind': 'operator', 'operator': 'antibody_cdr_kabat',
                   'position': {'x': 1, 'y': 0}, 'params': {'output': 'cdr'}}],
        'edges': [{'id': 'edge', 'source': 'fasta', 'target': 'cdr'}]})


def wait_until(check, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = check()
        if value:
            return value
        time.sleep(.05)
    pytest.fail('timed out waiting for FASTA/CDR execution')


def test_fasta_protein_metadata_validates_and_runs_cdr(tmp_path):
    (tmp_path / 'vhh.fasta').write_text('>vhh\n' + VHH + '\n', encoding='utf-8')
    app = Application(Settings(tmp_path, tmp_path / '.studio', tmp_path / 'ui',
                               testing=True, code_root=ROOT), catalog_from_descriptors())
    try:
        result = app.validate(graph(tmp_path), require_files=True)
        assert result['readiness']['status'] == 'ready'
        assert 'FastaReader' in result['readiness']['targets']['local']
        assert 'antibody_cdr_kabat' in result['readiness']['targets']['local']
        job = app.jobs.launch(graph(tmp_path))
        finished = wait_until(lambda: (lambda value: value if value['status'] in
                                       ('complete', 'failed', 'cancelled') else None)(
            app.jobs.details(job['id'])))
        assert finished['status'] == 'complete', finished.get('error')
        assert app.jobs.details(job['id'])['report']['artifacts'], 'CDR output artifact missing'
    finally:
        app.shutdown()


def test_wrong_raw_file_contract_is_rejected_without_bypass(tmp_path):
    (tmp_path / 'vhh.fasta').write_text('>vhh\n' + VHH + '\n', encoding='utf-8')
    (tmp_path / 'raw.csv').write_text('a,b\n1,2\n', encoding='utf-8')
    app = Application(Settings(tmp_path, tmp_path / '.studio', tmp_path / 'ui',
                               testing=True, code_root=ROOT), catalog_from_descriptors())
    try:
        with pytest.raises(Exception, match='sequence|alphabet|representation|numeric|contract'):
            app.validate(graph(tmp_path, path='raw.csv', reader=None), require_files=True)
    finally:
        app.shutdown()


def test_dependency_only_check_does_not_require_data_or_reader(tmp_path):
    app = Application(Settings(tmp_path, tmp_path / '.studio', tmp_path / 'ui',
                               testing=True, code_root=ROOT), catalog_from_descriptors())
    try:
        result = app.check_environment(graph(tmp_path, path='', reader=None))
        assert result['scope'] == 'dependencies'
        assert result['readiness']['status'] in ('ready', 'blocked')
        assert not (tmp_path / '.studio/jobs').exists() or not list(
            (tmp_path / '.studio/jobs').glob('*/job.json'))
    finally:
        app.shutdown()
