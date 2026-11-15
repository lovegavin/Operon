"""The 5.0.0 application installs a library ZIP and route collections without rebuilding identity."""
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import time
import zipfile

from fastapi.testclient import TestClient
import pytest
from packaging.version import Version

import operon
from operon.library_install import (
    LEGACY_MESSAGE,
    LegacyLibrary,
    install_library,
    install_routes_collection,
    inspect_library,
)
from operon.plugins import PluginManager
from operon_sdk.declarations import declaration_hash
from src.web.api import create_app
from src.web.models import Graph
from src.web.parameters import export_bundle
from src.web.service import Settings

ROOT = Path(__file__).resolve().parents[1]
NAME = "operon-synthetic"
VERSION = "0.1.0"
WHEEL_NAME = "operon_synthetic-0.1.0-py3-none-any.whl"
SOURCE = '''\
"""Synthetic operator used only by application installer tests."""


class SyntheticScale:
    """Trivial operator whose declaration is compiled into the wheel."""

    def run(self, inputs, parameters):
        return inputs
'''
PARAMETERS = {
    "type": "object",
    "properties": {"factor": {"type": "number", "title": "Factor", "default": 1.0}},
    "required": ["factor"],
    "additionalProperties": False,
}
OPERATOR = "synthetic_scale"


def _descriptor() -> dict:
    descriptor = {
        "protocol_version": 3,
        "id": OPERATOR,
        "version": VERSION,
        "kind": "operator",
        "entry_point": "operon_synthetic_step:SyntheticScale",
        "code_sha": "",
        "declaration_sha": "",
        "title": "Synthetic Scale",
        "description": "Synthetic operator used by tests.",
        "category": "Test",
        "parameters_schema": PARAMETERS,
        "inputs_arity": 1,
        "outputs": ["result"],
        "output_parameter": None,
        "contracts": {
            "inputs": [{"schema": {"type": "object"}}],
            "output": {"mode": "declare", "schema": {"type": "object"}},
        },
        "resources": {"memory_modes": ["memory"]},
    }
    code = SOURCE.encode("utf-8")
    digest = hashlib.sha256()
    digest.update(b"operon_synthetic_step.py\0")
    digest.update(code.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n").encode("utf-8"))
    descriptor["code_sha"] = digest.hexdigest()
    descriptor["declaration_sha"] = declaration_hash(descriptor)
    return descriptor


DESCRIPTOR = _descriptor()


def _zip_bytes(entries: dict[str, bytes]) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return stream.getvalue()


def _wheel_bytes() -> bytes:
    info = f"operon_synthetic-{VERSION}.dist-info"
    files = {
        "operon_synthetic_step.py": SOURCE.encode("utf-8"),
        "operon_synthetic_step.parameters.json": (json.dumps(PARAMETERS, indent=2) + "\n").encode("utf-8"),
        f"{info}/METADATA": (
            f"Metadata-Version: 2.1\nName: {NAME}\nVersion: {VERSION}\n"
            "Summary: Synthetic operator\nRequires-Python: >=3.10\n"
        ).encode("utf-8"),
        f"{info}/WHEEL": b"Wheel-Version: 1.0\nGenerator: tests\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        f"{info}/operon.json": json.dumps(
            {"protocol_version": 3, "name": NAME, "version": VERSION, "descriptors": [DESCRIPTOR]},
            indent=2,
        ).encode("utf-8"),
    }
    record = [
        f"{name},sha256={hashlib.sha256(content).hexdigest()},{len(content)}"
        for name, content in files.items()
    ]
    record.append(f"{info}/RECORD,,")
    files[f"{info}/RECORD"] = ("\n".join(record) + "\n").encode("utf-8")
    return _zip_bytes(files)


def _library_zip(directory: Path, *, minimum_application=None, bundle_format=1, library_name=None) -> Path:
    wheel = _wheel_bytes()
    document = {
        "format": "operon.library",
        "library_version": "0.0.0",
        "operator_protocol": {"version": 3, "revision": "3.7"},
        "minimum_application": minimum_application or operon.__version__,
        "builder": {"name": "tests", "version": "1.0.0"},
        "packages": [{
            "name": NAME,
            "version": VERSION,
            "wheel": f"wheels/{WHEEL_NAME}",
            "wheel_sha256": hashlib.sha256(wheel).hexdigest(),
            "code_sha": DESCRIPTOR["code_sha"],
            "entry_points": {OPERATOR: DESCRIPTOR["entry_point"]},
        }],
    }
    if bundle_format is not None:
        document["bundle_format"] = bundle_format
    if library_name is not None:
        document["library_name"] = library_name
    entries = {
        "library.json": json.dumps(document, indent=2).encode("utf-8"),
        f"wheels/{WHEEL_NAME}": wheel,
    }
    entries["SHA256SUMS"] = "".join(
        f"{hashlib.sha256(content).hexdigest()}  {name}\n" for name, content in entries.items()
    ).encode("utf-8")
    target = directory / "operon-library-0.0.0.zip"
    target.write_bytes(_zip_bytes(entries))
    return target


def _plain_wheel(directory: Path, name: str, version: str) -> Path:
    info = f"{name.replace('-', '_')}-{version}.dist-info"
    files = {
        f"{info}/METADATA": f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n".encode("utf-8"),
        f"{info}/WHEEL": b"Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
    }
    target = directory / f"{name.replace('-', '_')}-{version}-py3-none-any.whl"
    target.write_bytes(_zip_bytes(files))
    return target


def test_new_library_install_records_manifest_identity(tmp_path):
    library = _library_zip(tmp_path)
    manager = PluginManager(tmp_path / "data")

    result = install_library(manager, library)

    assert result == {
        "library": "main-v0.0.0",
        "libraries": ["main-v0.0.0"],
        "library_version": "0.0.0",
        "packages": 1,
        "descriptors": 1,
        "installed": True,
        "idempotent": False,
    }
    state = manager.state()
    packages = {package["name"]: package for package in state["packages"]}
    assert packages[NAME]["version"] == VERSION
    release = state["library_release"]
    assert release["format"] == "operon.library"
    assert release["bundle_format"] == 1
    assert release["library_version"] == "0.0.0"
    assert release["packages"] == {NAME: {"version": VERSION, "code_sha": DESCRIPTOR["code_sha"]}}
    assert release["sha256"] == hashlib.sha256(library.read_bytes()).hexdigest()
    assert state["library_detached"] is True
    installed = {descriptor["id"]: descriptor for descriptor in state["descriptors"]}
    assert installed[OPERATOR]["distribution"] == NAME
    assert installed[OPERATOR]["package_version"] == VERSION
    # The application keeps the library's canonical identity instead of hashing installed bytes.
    assert installed[OPERATOR]["code_sha"] == DESCRIPTOR["code_sha"]


def test_second_import_is_idempotent(tmp_path):
    library = _library_zip(tmp_path)
    manager = PluginManager(tmp_path / "data")
    first = install_library(manager, library)
    second = install_library(manager, library)

    assert first["installed"] is True
    assert second["installed"] is False
    assert second["idempotent"] is True
    assert second["library_version"] == first["library_version"]
    assert second["packages"] == first["packages"]
    state = manager.state()
    assert [package["name"] for package in state["packages"]].count(NAME) == 1


def test_tampered_wheel_is_rejected(tmp_path):
    library = _library_zip(tmp_path)
    with zipfile.ZipFile(library) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    entries[f"wheels/{WHEEL_NAME}"] = entries[f"wheels/{WHEEL_NAME}"] + b"tampered"
    library.write_bytes(_zip_bytes(entries))
    manager = PluginManager(tmp_path / "data")

    with pytest.raises(ValueError, match="SHA256SUMS digest mismatch"):
        install_library(manager, library)


def test_minimum_application_newer_than_running_is_rejected(tmp_path):
    current = Version(operon.__version__)
    minimum = f"{current.major + 1}.0.0"
    library = _library_zip(tmp_path, minimum_application=minimum)
    manager = PluginManager(tmp_path / "data")

    with pytest.raises(ValueError, match="requires Operon"):
        install_library(manager, library)


def test_legacy_8x_library_is_rejected_with_exact_message(tmp_path):
    library = _library_zip(tmp_path, bundle_format=None)
    with pytest.raises(LegacyLibrary) as error:
        inspect_library(library)
    assert str(error.value) == LEGACY_MESSAGE
    manager = PluginManager(tmp_path / "data")
    with pytest.raises(LegacyLibrary) as error:
        manager.install(library)
    assert str(error.value) == LEGACY_MESSAGE


def test_legacy_builtin_library_wheel_is_rejected(tmp_path):
    wheel = _plain_wheel(tmp_path, "operon_builtin_library", "8.0.9")
    manager = PluginManager(tmp_path / "data")

    with pytest.raises(LegacyLibrary) as error:
        manager.install(wheel)
    assert str(error.value) == LEGACY_MESSAGE


@pytest.fixture(scope="module")
def studio(tmp_path_factory):
    root = tmp_path_factory.mktemp("studio")
    settings = Settings(root, root / "studio", ROOT / "frontend/dist", testing=True, code_root=ROOT, desktop=True)
    service = create_app(settings).state.service
    install_library(service.plugins, _library_zip(root))
    return service


def _pins(service, operators=(OPERATOR,)) -> dict:
    descriptors = {descriptor["id"]: descriptor for descriptor in service.plugins.state()["descriptors"]}
    return {
        operator: deepcopy(descriptors[operator]["implementation"])
        for operator in operators
    }


def _route_graph(service, pins: dict) -> Graph:
    source = next(node for node in service.demo["nodes"] if node["kind"] == "source")
    graph = Graph.model_validate({
        "schema_version": 2,
        "name": "Synthetic route",
        "nodes": [
            deepcopy(source),
            {
                "id": "scale",
                "kind": "operator",
                "operator": OPERATOR,
                "position": {"x": 320, "y": 120},
                "params": {"factor": 2.0},
                "input_count": 1,
            },
        ],
        "edges": [{
            "id": "expression-scale",
            "source": source["id"],
            "target": "scale",
            "sourceHandle": "out",
            "targetHandle": "in-0",
        }],
        "plugin_lock": pins,
    })
    return graph


def _collection(directory: Path, service, *, pins=None, raw_pins=None, tamper=None, extra=None, name="Synthetic route") -> Path:
    graph = _route_graph(service, _pins(service) if pins is None else pins)
    with zipfile.ZipFile(io.BytesIO(export_bundle(graph))) as archive:
        members = {member: archive.read(member) for member in archive.namelist()}
    topology = json.loads(members["graph.json"])
    # Invalid-wire fixtures are injected after normal author export, so their
    # rejection is exercised at the collection import boundary.
    topology["plugin_lock"] = deepcopy(graph.plugin_lock if raw_pins is None else raw_pins)
    if tamper is not None:
        topology["plugin_lock"][tamper]["code_sha"] = "0" * 64
    members["graph.json"] = json.dumps(topology, ensure_ascii=False, indent=2).encode("utf-8")
    if extra is not None:
        members.update(extra)
    route = _zip_bytes(members)
    document = {
        "schema_version": 1,
        "library_version": "0.0.0",
        "routes": [{
            "key": "synthetic",
            "name": name,
            "file": "routes/synthetic.operon.zip",
            "sha256": hashlib.sha256(route).hexdigest(),
        }],
    }
    entries = {
        "routes.json": json.dumps(document, indent=2).encode("utf-8"),
        "routes/synthetic.operon.zip": route,
    }
    entries["SHA256SUMS"] = "".join(
        f"{hashlib.sha256(content).hexdigest()}  {entry}\n" for entry, content in entries.items()
    ).encode("utf-8")
    target = directory / "operon-routes-v0.0.0.zip"
    target.write_bytes(_zip_bytes(entries))
    return target


def test_route_collection_imports_and_reimports_once(tmp_path, studio):
    collection = _collection(tmp_path, studio)
    first = install_routes_collection(studio, collection)
    second = install_routes_collection(studio, collection)

    assert first["count"] == 1
    assert first["routes"] == [{"key": "synthetic", "name": "Synthetic route"}]
    assert second["count"] == 1
    saved = [route for route in studio.application.workflows.list() if route["name"] == "Synthetic route"]
    assert len(saved) == 1
    stored = studio.application.workflows.get(saved[0]['id'])
    assert stored['graph']['plugin_lock'][OPERATOR] == _pins(studio)[OPERATOR]
    registered = [route for route in studio.routes.routes() if route["name"] == "Synthetic route"]
    assert len(registered) == 1


@pytest.mark.parametrize('damage', [
    'version', 'code', 'unknown', 'missing-artifact-identity',
    'wheel-without-execution-identity', 'execution', 'malformed',
])
def test_invalid_route_pin_rejects_import_without_overwriting_saved_draft(tmp_path, studio, damage):
    workflows = studio.application.workflows
    draft = _route_graph(studio, _pins(studio))
    draft.name = 'Pinned draft ' + damage
    saved = workflows.save(draft)
    previous = workflows.get(saved['id'])
    saved_before = deepcopy(workflows.list())
    registered_before = deepcopy(studio.routes.routes())
    pins = _pins(studio)
    pin = pins[OPERATOR]
    if damage == 'version':
        pin['version'] = '9.9.9'
    elif damage == 'code':
        pin['code_sha'] = '0' * 64
    elif damage == 'unknown':
        pins['ghost'] = deepcopy(pin)
    elif damage == 'missing-artifact-identity':
        pin.pop('sha256', None)
        pin.pop('execution_sha', None)
    elif damage == 'wheel-without-execution-identity':
        # A historical pin without execution_sha must match the exact wheel;
        # matching code_sha alone cannot authorize its native/assets closure.
        pin.pop('execution_sha', None)
        pin['sha256'] = 'f' * 64
    elif damage == 'execution':
        pin['execution_sha'] = 'f' * 64
    else:
        pins[OPERATOR] = 'not an implementation record'
    collection = _collection(tmp_path, studio, raw_pins=pins, name=draft.name)
    uploaded = collection.read_bytes()

    message = 'plugin_lock' if damage == 'malformed' else 'Required plugin versions are unavailable'
    with pytest.raises(ValueError, match=message):
        install_routes_collection(studio, collection)

    assert workflows.get(saved['id']) == previous
    assert workflows.list() == saved_before
    assert studio.routes.routes() == registered_before
    assert collection.read_bytes() == uploaded


def test_route_declaration_audit_drift_preserves_exact_executable_pin(tmp_path, studio):
    pins = _pins(studio)
    for pin in pins.values():
        pin["declaration_sha"] = "e" * 64
    collection = _collection(tmp_path, studio, pins=pins, name='Declaration audit drift')

    result = install_routes_collection(studio, collection)

    assert result["count"] == 1


def test_route_member_must_contain_exactly_three_files(tmp_path, studio):
    collection = _collection(tmp_path, studio, extra={"notes.txt": b"extra"})

    with pytest.raises(ValueError, match="must contain exactly graph.json, parameters.json and execution.json"):
        install_routes_collection(studio, collection)


def test_manager_install_routes_the_new_library_archive(tmp_path):
    library = _library_zip(tmp_path)
    manager = PluginManager(tmp_path / "data")

    result = manager.install(library)

    assert result["installed"] is True
    assert result["library_version"] == "0.0.0"


@pytest.fixture
def client(tmp_path):
    settings = Settings(tmp_path, tmp_path / "studio", ROOT / "frontend/dist", testing=True, code_root=ROOT, desktop=True)
    app = create_app(settings)
    with TestClient(app) as value:
        data = value.get("/api/bootstrap").json()
        value.headers["X-Studio-Token"] = data["token"]
        yield value, app


def _wait(client, operation: str) -> dict:
    for _ in range(240):
        current = client.get(f"/api/plugins/operations/{operation}").json()
        if current.get("status") != "running":
            return current
        time.sleep(0.05)
    raise AssertionError(f"plugin operation {operation} did not finish")


def test_plugin_install_endpoint_installs_a_new_library(tmp_path, client):
    web, app = client
    library = _library_zip(tmp_path)

    started = web.post(
        "/api/plugins/install", params={"filename": library.name}, content=library.read_bytes()
    )

    assert started.status_code == 200, started.text
    operation = _wait(web, started.json()["id"])
    assert operation["status"] == "complete", operation
    result = operation["result"]
    assert result == {
        "library": "main-v0.0.0",
        "libraries": ["main-v0.0.0"],
        "library_version": "0.0.0",
        "packages": 1,
        "descriptors": 1,
        "installed": True,
        "idempotent": False,
    }
    assert {package["name"] for package in app.state.service.plugins.state()["packages"]} >= {NAME}


def test_plugin_install_endpoint_rejects_the_legacy_library_synchronously(tmp_path, client):
    web, _ = client
    library = _library_zip(tmp_path, bundle_format=None)

    response = web.post(
        "/api/plugins/install", params={"filename": "Operon-Library-v8.0.9.operon-library.zip"}, content=library.read_bytes()
    )

    assert response.status_code == 400
    assert response.json()["detail"] == LEGACY_MESSAGE


def test_libraries_install_endpoint_accepts_a_path(tmp_path, client):
    web, app = client
    library = _library_zip(tmp_path)

    response = web.post("/api/libraries/install", json={"path": str(library)})

    assert response.status_code == 200, response.text
    assert response.json()["packages"] == 1
    assert app.state.service.plugins.state()["library_release"]["library_version"] == "0.0.0"


def test_libraries_install_endpoint_uploads_a_file(tmp_path, client):
    web, app = client
    library = _library_zip(tmp_path)

    response = web.post(
        "/api/libraries/install",
        files={"file": (library.name, library.read_bytes(), "application/zip")},
    )

    assert response.status_code == 200, response.text
    assert response.json()["installed"] is True
    assert app.state.service.plugins.state()["library_release"]["library_version"] == "0.0.0"


def test_libraries_install_endpoint_returns_400_for_a_legacy_archive(tmp_path, client):
    web, _ = client
    library = _library_zip(tmp_path, bundle_format=None)

    response = web.post("/api/libraries/install", json={"path": str(library)})

    assert response.status_code == 400
    assert response.json()["detail"] == LEGACY_MESSAGE


def test_routes_import_collection_endpoint_uploads_a_collection(tmp_path, client):
    web, app = client
    library = web.post("/api/libraries/install", json={"path": str(_library_zip(tmp_path))})
    assert library.status_code == 200, library.text
    collection = _collection(tmp_path, app.state.service)

    response = web.post(
        "/api/routes/import-collection",
        files={"file": ("operon-routes-v0.0.0.zip", collection.read_bytes(), "application/zip")},
    )

    assert response.status_code == 200, response.text
    assert response.json()["count"] == 1
    assert response.json()["routes"] == [{"key": "synthetic", "name": "Synthetic route"}]
    assert [route for route in app.state.service.routes.routes() if route["name"] == "Synthetic route"]


def test_control_api_uses_bundle_namespace_and_removes_named_library(tmp_path, client):
    web, app = client
    library = _library_zip(tmp_path, library_name='fork')
    installed = web.post("/api/v1/libraries/install", json={"path": str(library), "name": "caller-override"})
    assert installed.status_code == 200, installed.text
    assert installed.json()['library'] == 'fork-v0.0.0'
    listed = web.get("/api/v1/libraries")
    assert listed.status_code == 200, listed.text
    payload = listed.json()
    assert payload["count"] == 1
    assert payload["libraries"][0]["name"] == "fork-v0.0.0"
    assert payload["libraries"][0]["operators"] == 1
    removed = web.delete("/api/v1/libraries/fork-v0.0.0")
    assert removed.status_code == 200, removed.text
    assert removed.json()["removed"] == "fork-v0.0.0"
    assert web.get("/api/v1/libraries").json()["count"] == 0



def test_control_api_installs_a_library_and_a_route_collection(tmp_path, client):
    web, app = client
    library = _library_zip(tmp_path)

    installed = web.post("/api/v1/libraries/install", json={"path": str(library)})

    assert installed.status_code == 200, installed.text
    assert installed.json() == {
        "library": "main-v0.0.0",
        "libraries": ["main-v0.0.0"],
        "library_version": "0.0.0",
        "packages": 1,
        "descriptors": 1,
        "installed": True,
        "idempotent": False,
    }
    assert app.state.service.plugins.state()["library_release"]["library_version"] == "0.0.0"
    collection = _collection(tmp_path, app.state.service)
    imported = web.post("/api/v1/routes/import-collection", json={"path": str(collection)})

    assert imported.status_code == 200, imported.text
    assert imported.json()["count"] == 1


@pytest.mark.parametrize('source_receipt,release', [
    ({'root': 'library/sources/legacy'}, {'version': '8.0.10', 'sha256': 'a' * 64}),
    ({'root': 'library/sources/legacy'}, {}),
    ({'packages': []}, {'version': '8.0.10', 'sha256': 'a' * 64}),
])
def test_legacy_workspace_registry_is_reset_before_the_first_read(tmp_path, monkeypatch, source_receipt, release):
    """A 4.x workspace must not present its dead 8.x library as installed."""
    monkeypatch.setattr("operon.library_location.source_root", lambda root=None: None)
    manager = PluginManager(tmp_path / "data")
    manager.directory.mkdir(parents=True)
    manager.registry.write_text(json.dumps({
        "protocol_version": 3,
        "package_protocol_version": 3,
        "packages": [{"name": "operon-core", "version": "1.0.0", "origin": "wheel"}],
        "descriptors": [{"id": "legacy_operator", "distribution": "operon-core"}],
        "bundled_seen": [],
        "generation": "legacy",
        "library_release": release,
        "source_library": source_receipt,
        "library_source_pins": {"operon-core": {"version": "1.0.0"}},
    }), encoding="utf-8")

    state = manager.state()

    assert state["packages"] == []
    assert state["descriptors"] == []
    assert state["library_release"] is None
    assert state["library_detached"] is False
    assert state["legacy_library_reset"] is True
    assert "source_library" not in state
    assert "library_source_pins" not in state
