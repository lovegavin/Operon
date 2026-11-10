"""Route collection archives and strict library suffixes."""
from copy import deepcopy
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from fastapi.testclient import TestClient

from operon.library_bundle import is_library_bundle
from src.web.api import create_app
from src.web.models import Graph
from src.web.parameters import export_bundle
from src.web.route_archive import route_members
from src.web.service import Settings

ROOT = Path(__file__).resolve().parents[1]


def collection(graphs, names=('route/a.operon.zip', 'routes/sub/b.operon.zip')):
    stream = BytesIO()
    with ZipFile(stream, 'w', ZIP_DEFLATED) as archive:
        archive.writestr('readme.txt', 'ignored')
        for name, graph in zip(names, graphs):
            archive.writestr(name, export_bundle(Graph.model_validate(graph)))
    return stream.getvalue()


@pytest.fixture
def studio(tmp_path):
    app = create_app(Settings(tmp_path, tmp_path / 'studio', ROOT / 'frontend/dist', testing=True, code_root=ROOT, desktop=True))
    with TestClient(app) as client:
        data = client.get('/api/bootstrap').json()
        client.headers['X-Studio-Token'] = data['token']
        yield client, data


def test_collection_members_are_limited_to_route_folders():
    stream = BytesIO()
    with ZipFile(stream, 'w') as archive:
        archive.writestr('route/a.operon.zip', b'one')
        archive.writestr('routes/nested/b.operon.zip', b'two')
        archive.writestr('route/readme.txt', b'ignored')
        archive.writestr('other/c.operon.zip', b'ignored')
    assert route_members(stream.getvalue()) == [('a.operon.zip', b'one'), ('b.operon.zip', b'two')]


def test_collection_members_reject_escaping_paths():
    stream = BytesIO()
    with ZipFile(stream, 'w') as archive:
        archive.writestr('route/../evil.operon.zip', b'bad')
    with pytest.raises(ValueError, match='不安全的路径'):
        route_members(stream.getvalue())


def test_library_suffix_is_strict():
    assert is_library_bundle('Operon-Library-v1.operon-library.zip')
    assert is_library_bundle('x.OPERON-LIBRARY.ZIP')
    assert not is_library_bundle('x.zip')
    assert not is_library_bundle('x.operon.zip')


def test_import_archive_saves_and_registers_every_route(studio):
    client, bootstrap = studio
    first = deepcopy(bootstrap['demo'])
    second = deepcopy(bootstrap['demo'])
    second['name'] = 'Second route'
    payload = collection([bootstrap['demo'], second])
    response = client.post('/api/routes/import-archive', content=payload, headers={'Content-Type': 'application/zip'})
    assert response.status_code == 200, response.text
    registered = response.json()
    assert len(registered) == 2
    assert len(client.get('/api/routes').json()) == 2
    assert {item['name'] for item in registered} == {first['name'], 'Second route'}


def test_import_archive_rejects_empty_collection(studio):
    client, _ = studio
    stream = BytesIO()
    with ZipFile(stream, 'w') as archive:
        archive.writestr('route/readme.txt', 'no bundle')
    response = client.post('/api/routes/import-archive', content=stream.getvalue(), headers={'Content-Type': 'application/zip'})
    assert response.status_code == 422
    assert '没有 route/' in response.json()['message']
