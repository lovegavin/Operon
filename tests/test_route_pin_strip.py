import hashlib
import io
import json
import zipfile

from src.web.models import Graph
from operon.library_install import install_routes_collection
from operon.planning.parameters import split_execution, split_graph
from operon.pins import strip_pins


def graph_with(lock):
    graph = Graph.model_validate({'nodes': [], 'edges': []})
    graph.plugin_lock.update(lock)
    return graph


def test_strip_pins_returns_and_clears_lock():
    pin = {'package': 'operon-core', 'version': '0.1.28', 'code_sha': 'a' * 40}
    graph = graph_with({'demo': pin})
    removed = strip_pins(graph)
    assert removed == {'demo': pin}
    assert graph.plugin_lock == {}


def test_strip_pins_follows_nested_route_graphs():
    inner = graph_with({'inner': {'package': 'operon-core', 'version': '0.1.28'}})
    outer = graph_with({'outer': {'package': 'operon-readers', 'version': '0.1.28'}})
    outer.nodes = Graph.model_validate({
        'nodes': [{
            'id': 'r1', 'kind': 'route', 'position': {'x': 0, 'y': 0},
            'route': {'id': 'route_0123456789ab', 'version': 1, 'name': 'inner',
                      'graph': inner.model_dump()},
        }],
        'edges': [],
    }).nodes
    removed = strip_pins(outer)
    assert set(removed) == {'outer', 'inner'}
    assert outer.plugin_lock == {}
    assert outer.nodes[0].route.graph.plugin_lock == {}


class _Workflows:
    def __init__(self):
        self.saved = []

    def list(self):
        return []

    def save(self, graph, **kwargs):
        self.saved.append(graph)
        return {'id': f'route_{len(self.saved):012d}'}


class _Routes:
    def __init__(self, directory):
        self.directory = directory
        self.registered = []
        self.catalog_for = lambda graph: {'operators': [], 'readers': []}

    def register(self, ids):
        self.registered.extend(ids)
        return [{'id': value} for value in ids]


class _Plugins:
    def state(self):
        return {'descriptors': [], 'code_paths': [], 'packages': []}


class _Application:
    def __init__(self):
        self.workflows = _Workflows()


class _Service:
    def __init__(self, directory):
        self.application = _Application()
        self.routes = _Routes(directory)
        self.plugins = _Plugins()


def bundle(tmp_path):
    graph = Graph.model_validate({
        'nodes': [{
            'id': 'fasta', 'kind': 'source', 'position': {'x': 0, 'y': 0},
            'source': {'reader': 'FastaReader', 'path': 'x.fasta',
                       'dims': ['sequence'], 'labels': {'sequence': 'builtin'}},
            'route': None,
        }],
        'edges': [],
    })
    graph.plugin_lock['FastaReader'] = {
        'package': 'operon-readers', 'version': '0.1.28', 'code_sha': 'b' * 40}
    inner = io.BytesIO()
    with zipfile.ZipFile(inner, 'w') as archive:
        topology, values = split_graph(graph)
        topology, config = split_execution(topology)
        archive.writestr('graph.json', json.dumps(topology))
        archive.writestr('parameters.json', json.dumps(values))
        archive.writestr('execution.json', json.dumps(config))
    payload = inner.getvalue()
    outer = tmp_path / 'operon-routes-main-v0.1.28.zip'
    with zipfile.ZipFile(outer, 'w') as archive:
        archive.writestr('routes/demo.operon.zip', payload)
        archive.writestr('routes.json', json.dumps({'routes': [{
            'file': 'routes/demo.operon.zip', 'key': 'demo', 'name': 'Demo route',
            'sha256': hashlib.sha256(payload).hexdigest(),
        }]}))
    return outer


def test_collection_import_keeps_pins_as_provenance(tmp_path):
    service = _Service(tmp_path)
    result = install_routes_collection(service, bundle(tmp_path))
    assert result['count'] == 1
    saved = service.application.workflows.saved[0]
    assert saved.plugin_lock == {}
    manifest = json.loads((tmp_path / 'collections' / 'operon-routes-main-v0.1.28.json').read_text('utf-8'))
    assert manifest['routes'][0]['pins']['FastaReader']['version'] == '0.1.28'
