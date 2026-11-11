"""Branded transport aliases do not relax pins, schema checks or ID ownership."""
from copy import deepcopy
from io import BytesIO
import json
from zipfile import ZipFile

import pytest

from operon.dropins import single_file_wheel
from operon.plugins import PluginManager
from src.web.models import Graph
from src.web.parameters import export_bundle, import_bundle


def branded_bundle(prefix='operon', *, malformed=False):
    graph = Graph(nodes=[{'id': 'pca', 'kind': 'operator', 'operator': 'pca',
                         'position': {'x': 3, 'y': 4}, 'params': {'n_components': 2}}],
                  edges=[], params={'seed': 0}, memory={'enabled': True, 'budget_bytes': 123456},
                  runtime={'execution': {'mode': 'manual'}},
                  plugin_lock={'pca': {'package': 'operon-core', 'version': '1.0.0', 'code_sha': 'a'*64}})
    output = BytesIO()
    with ZipFile(BytesIO(export_bundle(graph))) as source, ZipFile(output, 'w') as target:
        for name in source.namelist():
            data = json.loads(source.read(name))
            if 'format' in data:
                data['format'] = data['format'].replace('operon.', prefix + '.', 1)
            if malformed and name == 'parameters.json':
                data['nodes']['pca']['operator'] = 'different'
            target.writestr(name, json.dumps(data))
    return graph, output.getvalue()


@pytest.mark.parametrize('prefix', ['operon', 'operon'])
def test_route_sidecar_aliases_preserve_values_and_pins(prefix):
    graph, content = branded_bundle(prefix)
    assert import_bundle(content) == graph
    assert import_bundle(export_bundle(import_bundle(content))) == graph


@pytest.mark.parametrize('prefix,malformed', [('unknown', False), ('operon', True)])
def test_sidecar_aliases_keep_strict_validation(prefix, malformed):
    _, content = branded_bundle(prefix, malformed=malformed)
    with pytest.raises(ValueError, match='do not match'):
        import_bundle(content)


def wheel(tmp_path, package, identifier='describe'):
    source = tmp_path / (package + '.py')
    definition = {'protocol_version': 3, 'id': identifier, 'version': '1.0.0', 'kind': 'operator',
                  'title': identifier, 'inputs_arity': 0, 'outputs': [],
                  'contracts': {'version': 1, 'inputs': [], 'output': {'mode': 'report'}},
                  'resources': {'memory_modes': ['full']}}
    source.write_text('from operon_sdk import Step\nOPERON_PLUGIN = ' + repr({'name': package, 'version': '1.0.0'}) +
                      '\nclass Report(Step):\n    parameters_file = ' + repr(source.stem + '.parameters.json') + '\n    definition = ' + repr(definition) +
                      '\n    def run(self, ctx, inputs): pass\n    def export(self, ctx): return {}\n', encoding='utf-8')
    source.with_suffix('.parameters.json').write_text('{"type":"object","properties":{}}')
    return single_file_wheel(source, tmp_path / 'wheels')


@pytest.mark.parametrize('package,identifier', [('operon-core', 'CsvReader'), ('operon-unrelated', 'describe')])
def test_rename_does_not_allow_stealing_another_providers_id(tmp_path, package, identifier):
    manager = PluginManager(tmp_path / 'profile', source_root=None, manifest_only=True)
    previous = deepcopy(manager.state())
    with pytest.raises(ValueError, match='shadows a built-in'):
        manager.install(wheel(tmp_path, package, identifier))
    assert manager.state() == previous


def test_duplicate_alias_inputs_are_rejected_atomically(tmp_path):
    manager = PluginManager(tmp_path / 'profile', source_root=None, manifest_only=True)
    previous = deepcopy(manager.state())
    with pytest.raises(ValueError, match='More than one input'):
        manager.install_many([wheel(tmp_path, 'operon-core'), wheel(tmp_path, 'operon-core')])
    assert manager.state() == previous


@pytest.mark.parametrize('member,message', [('library.json', 'operator library'),
                                           ('routes/demo.operon.zip', 'collection of workflows')])
def test_wrong_archive_type_explains_the_correct_import_entry(member, message):
    output = BytesIO()
    with ZipFile(output, 'w') as archive:
        archive.writestr(member, b'{}')
    with pytest.raises(ValueError, match=message):
        import_bundle(output.getvalue())
