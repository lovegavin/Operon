"""The MCP surface an agent meets first: bounded shapes and a next step.

These assertions cover the five walls a fresh MCP client used to hit:
a sessions object instead of a list, an unfiltered operator search that
answered nothing, a saved-workflow list that returned every stored contract,
and an ambiguous canvas name.
"""
import asyncio
import json
from types import SimpleNamespace

import pytest


def tool_json(server, name, arguments):
    result = asyncio.run(server.call_tool(name, arguments))
    # Newer MCP versions return (content, structured); older ones only content.
    if isinstance(result, tuple) and len(result) == 2 and isinstance(result[1], dict) and 'result' in result[1]:
        return result[1]['result']
    blocks = result[0] if isinstance(result, tuple) else result
    return json.loads(''.join(getattr(block, 'text', '') for block in blocks))


def descriptor(key, kind='operator', category='Statistics', title=None, summary=''):
    return {'id': key, 'kind': kind, 'title': title or key.upper(),
            'description': summary or key, 'category': category, 'version': '1.0.4',
            'title_aliases': [], 'documentation': {'summary': summary or key},
            'implementation': {'code_sha': 'a' * 64}}


def docs_with(tmp_path, monkeypatch, items):
    from operon.operator_docs import OperatorDocs
    monkeypatch.setattr('operon.plugins.active_descriptors', lambda state: items)
    return OperatorDocs(SimpleNamespace(directory=tmp_path, state=lambda: {'generation': 'g'}))


def test_sessions_always_return_an_items_envelope():
    pytest.importorskip('mcp.server.fastmcp')
    from operon.mcp_server import create_server
    rows = [{'id': 'one'}, {'id': 'two'}]
    server = create_server(SimpleNamespace(sessions=lambda: rows))
    assert tool_json(server, 'operon_sessions', {}) == {'items': rows, 'total': 2}

    # A client that already wraps the transport must not be wrapped twice.
    wrapped = create_server(SimpleNamespace(sessions=lambda: {'items': rows, 'total': 2}))
    assert tool_json(wrapped, 'operon_sessions', {}) == {'items': rows, 'total': 2}

    empty = create_server(SimpleNamespace(sessions=lambda: []))
    assert tool_json(empty, 'operon_sessions', {}) == {'items': [], 'total': 0}


def test_workflows_default_to_labels_and_keep_the_full_view_reachable():
    pytest.importorskip('mcp.server.fastmcp')
    from operon.mcp_server import create_server
    calls = []

    def request(*args, **kwargs):
        calls.append((args, kwargs))
        return []

    server = create_server(SimpleNamespace(request=request))
    assert tool_json(server, 'operon_workflows', {}) == {'items': [], 'total': 0}
    assert calls[-1] == (('/v1/workflows?view=brief',), {})

    asyncio.run(server.call_tool('operon_workflows', {'view': 'full'}))
    assert calls[-1] == (('/v1/workflows?view=full',), {})

    asyncio.run(server.call_tool('operon_workflows', {'workflow_id': 'w 1'}))
    assert calls[-1] == (('/v1/workflows/w%201',), {})


def test_brief_workflow_projection_drops_stored_contracts():
    from operon.application import brief_workflow
    interface = {'version': 1,
                 'inputs': [{'node_id': 'csv', 'label': 'matrix.csv', 'contract': {'ndim': 2}}],
                 'outputs': [{'node_id': 'pca', 'label': 'pcs', 'contract': {'ndim': 2}}]}
    item = {'id': 'pca-demo', 'version': 3, 'name': 'PCA demo', 'nodes': 2,
            'updated_at': '2026-11-26T00:00:00Z', 'interface': interface}
    brief = brief_workflow(item)
    assert brief['inputs'] == ['matrix.csv'] and brief['outputs'] == ['pcs']
    assert 'interface' not in brief and json.dumps(brief).find('ndim') == -1
    assert brief['nodes'] == 2 and brief['version'] == 3


def test_empty_operator_search_explains_how_to_narrow(tmp_path, monkeypatch):
    docs = docs_with(tmp_path, monkeypatch,
                     [descriptor('pca', summary='Principal components'),
                      descriptor('tsne', summary='Embedding'),
                      descriptor('FASTA', kind='reader', category='Data')])
    page = docs.search()
    assert page['items'] == [] and page['total'] == 0
    guidance = page['guidance']
    assert guidance['counts'] == {'operator': 2, 'reader': 1}
    assert guidance['categories'][0] == {'name': 'Statistics', 'count': 2}
    assert 'query="pca"' in guidance['examples'] and 'kind="reader"' in guidance['examples']
    assert 'returns nothing on purpose' in guidance['message']


def test_operator_search_browses_a_filter_and_answers_a_miss(tmp_path, monkeypatch):
    docs = docs_with(tmp_path, monkeypatch,
                     [descriptor('pca'), descriptor('tsne'),
                      descriptor('FASTA', kind='reader', category='Data')])
    readers = docs.search(kind='reader')
    assert [item['id'] for item in readers['items']] == ['FASTA']
    assert docs.search(category='Statistics')['total'] == 2
    miss = docs.search('nothing-matches-this')
    assert miss['items'] == [] and "nothing-matches-this" in miss['guidance']['message']


def test_canvas_context_names_the_window_and_the_document(tmp_path, monkeypatch):
    from operon.documents import DocumentHub
    monkeypatch.setattr('operon.documents.analyze_graph', lambda *a, **k: {'nodes': {}, 'edges': []})
    service = SimpleNamespace(directory=tmp_path, root=tmp_path, base_catalog={},
        settings=SimpleNamespace(input_roots=[]), routes=SimpleNamespace(save_workspace=lambda *a: None),
        plugins=SimpleNamespace(pin=lambda x: x, catalog_for=lambda *a: {}))
    hub = DocumentHub(service)
    graph = {'name': 'IL-7RA design', 'nodes': [], 'edges': []}
    session = hub.create({'schema_version': 1, 'active_id': 'main',
        'documents': [{'id': 'main', 'graph': graph}]}, name='表达矩阵 · 质量控制与降维')
    context = hub.context(session['id'])
    assert context['session_name'] == '表达矩阵 · 质量控制与降维'
    assert context['document_name'] == 'IL-7RA design'
    assert context['name'] == context['document_name']  # kept for older clients
    assert context['documents'] == [{'id': 'main', 'name': 'IL-7RA design', 'active': True}]
