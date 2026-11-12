from src.web.models import Graph
from operon.pins import refresh_missing


def state_with(origin, version='1.0.0', package='operon-core'):
    descriptor = {
        'id': 'demo',
        'origin': origin,
        'distribution': package,
        'implementation': {'version': version, 'package': package,
                           'sha256': 'new' * 20, 'code_sha': 'newcode' * 8},
    }
    return {'descriptors': [descriptor], 'code_paths': [], 'packages': []}


def graph_with(pin):
    graph = Graph.model_validate({
        'nodes': [{'id': 'n1', 'kind': 'operator', 'operator': 'demo',
                   'position': {'x': 0, 'y': 0}, 'params': {}}],
        'edges': []})
    graph.plugin_lock['demo'] = dict(pin)
    return graph


def test_refreshes_rebuilt_provider_pin_of_same_version():
    before = {'version': '1.0.0', 'package': 'operon-core', 'sha256': 'old' * 20}
    graph = graph_with(before)
    migrations = refresh_missing(graph, state_with('wheel'))
    assert len(migrations) == 1
    assert graph.plugin_lock['demo']['sha256'] == 'new' * 20
    assert 'rebuilt' in migrations[0]['reason']


def test_keeps_rebuilt_pin_from_other_version():
    before = {'version': '0.9.0', 'package': 'operon-core', 'sha256': 'old' * 20}
    graph = graph_with(before)
    assert refresh_missing(graph, state_with('wheel')) == []
    assert graph.plugin_lock['demo'] == before


def test_keeps_rebuilt_pin_from_other_distribution():
    before = {'version': '1.0.0', 'package': 'operon-other', 'sha256': 'old' * 20}
    graph = graph_with(before)
    assert refresh_missing(graph, state_with('wheel')) == []


def test_refreshes_legacy_pin_without_distribution_metadata():
    before = {'sha256': 'old' * 20, 'code_sha': 'oldcode' * 8}
    graph = graph_with(before)
    migrations = refresh_missing(graph, state_with('wheel'))
    assert len(migrations) == 1
    assert graph.plugin_lock['demo']['sha256'] == 'new' * 20


def test_refreshes_bundled_pin_without_version_gate():
    before = {'version': '0.9.0', 'package': 'operon-core', 'sha256': 'old' * 20}
    graph = graph_with(before)
    migrations = refresh_missing(graph, state_with('bundled'))
    assert len(migrations) == 1
    assert graph.plugin_lock['demo']['sha256'] == 'new' * 20
    assert 'bundled' in migrations[0]['reason']
