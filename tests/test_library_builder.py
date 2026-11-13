"""Tests for the standalone library builder."""

from __future__ import annotations

import csv
import io
import json
import shutil
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile

import pytest

from operon_library_builder import manifest, wheel
from operon_library_builder.build import build_library
from operon_library_builder.cli import main as cli_main
from operon_library_builder.descriptors import canonical_module
from operon_library_builder.gate import builder_import_violations, gate
from operon_library_builder.identity import code_identity, file_sha256
from operon_sdk.declarations import declaration_hash
from operon_sdk.protocol import Descriptor

REPO = Path(__file__).resolve().parents[1]
SEED = REPO / "library" / "seed"
PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "operon_library_builder"


def _copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture()
def synthetic_seed(tmp_path: Path) -> Path:
    seed = tmp_path / "seed"
    steps = seed / "src" / "task" / "step" / "steps"
    readers = seed / "src" / "reader" / "readers"
    _write(
        seed / "operon" / "builtin_packages.json",
        json.dumps(
            {
                "protocol_version": 3,
                "packages": [
                    {"name": "operon-core"},
                    {"name": "operon-microbiome"},
                    {"name": "operon-readers"},
                ],
            }
        ),
    )
    _write(seed / "operon" / "environments.json", json.dumps({"version": 1, "environments": {}}))

    for name in (
        "sc_spatial_neighbors.py",
        "sc_spatial_neighbors.ScSpatialNeighborsStep.parameters.json",
        "sc_spatial_neighbors.ScSpatialNeighborsStep.md",
    ):
        _copy(SEED / "src" / "task" / "step" / "steps" / name, steps / name)
    for name in (
        "aggregate.py",
        "aggregate.parameters.json",
        "aggregate.AggregateStep.md",
    ):
        _copy(SEED / "src" / "task" / "step" / "steps" / name, steps / name)
    for name in (
        "rnk_reader.py",
        "rnk_reader.RnkReader.parameters.json",
        "rnk_reader.RnkReader.md",
    ):
        _copy(SEED / "src" / "reader" / "readers" / name, readers / name)

    _write(steps / "_b65_common.py", "def numeric(*args, **kwargs):\n    raise NotImplementedError\n")
    _write(steps / "shared_support.py", "VALUE = 1\n")
    _write(
        readers / "_gsea_common.py",
        "from src.reader.readers import _table_common\n\nVALUE = 1\n",
    )
    _write(readers / "_table_common.py", "VALUE = 2\n")
    return seed


def _package(document: dict, name: str) -> dict:
    return next(package for package in document["packages"] if package["name"] == name)


def test_identity_is_deterministic_and_normalizes_newlines() -> None:
    assert code_identity({"a.py": b"x\r\ny\r"}) == code_identity({"a.py": b"x\ny\n"})
    assert code_identity({"a.py": b"x", "b.py": b"y"}) == code_identity({"b.py": b"y", "a.py": b"x"})
    assert code_identity({"a.py": b"x", "notes.md": b"one"}) == code_identity(
        {"a.py": b"x", "notes.md": b"two"}
    )
    assert code_identity({"a.py": b"x"}) != code_identity({"b.py": b"x"})
    assert file_sha256(b"x") == sha256(b"x").hexdigest()
    assert canonical_module("operon-core") == "operon_core"
    assert canonical_module("operon.readers") == "operon_readers"


def test_wheel_is_reproducible() -> None:
    files = {"operon_demo/__init__.py": b'"""demo"""\n', "operon_demo/mod.py": b"VALUE = 1\n"}
    descriptors = [
        {
            "id": "demo",
            "kind": "operator",
            "entry_point": "operon_demo.mod:DemoStep",
            "code_sha": "a" * 64,
        }
    ]
    first = wheel.build_wheel(
        "operon-demo", "0.0.0", files, code_sha="a" * 64, descriptors=descriptors
    )
    second = wheel.build_wheel(
        "operon-demo", "0.0.0", files, code_sha="a" * 64, descriptors=descriptors
    )
    assert first == second
    assert wheel.wheel_filename("operon-demo", "0.0.0") == "operon_demo-0.0.0-py3-none-any.whl"

    with ZipFile(io.BytesIO(first)) as archive:
        names = archive.namelist()
        assert names[:-1] == sorted(names[:-1])
        assert names[-1] == "operon_demo-0.0.0.dist-info/RECORD"
        assert all(info.date_time == (1980, 1, 1, 0, 0, 0) for info in archive.infolist())

        metadata = archive.read("operon_demo-0.0.0.dist-info/METADATA").decode("utf-8")
        assert "Metadata-Version: 2.1" in metadata
        assert "Name: operon-demo" in metadata
        assert "Version: 0.0.0" in metadata
        assert "Requires-Python: >=3.11" in metadata

        wheel_metadata = archive.read("operon_demo-0.0.0.dist-info/WHEEL").decode("utf-8")
        assert "Wheel-Version: 1.0" in wheel_metadata
        assert "Generator: Operon library" in wheel_metadata
        assert "Root-Is-Purelib: true" in wheel_metadata
        assert "Tag: py3-none-any" in wheel_metadata

        identity = json.loads(archive.read("operon_demo-0.0.0.dist-info/operon_identity.json"))
        assert identity == {"package": "operon-demo", "version": "0.0.0", "code_sha": "a" * 64}

        install = json.loads(archive.read("operon_demo-0.0.0.dist-info/operon.json"))
        assert install == {
            "protocol_version": 3,
            "name": "operon-demo",
            "version": "0.0.0",
            "title": None,
            "origin": "wheel",
            "descriptors": descriptors,
        }
        points = archive.read("operon_demo-0.0.0.dist-info/entry_points.txt").decode("utf-8")
        assert "[operon.operators]" in points
        assert "[operon.readers]" in points
        assert "demo = operon_demo.mod:DemoStep" in points

        record = list(csv.reader(io.StringIO(archive.read("operon_demo-0.0.0.dist-info/RECORD").decode())))
        assert record[-1] == ["operon_demo-0.0.0.dist-info/RECORD", "", ""]
        recorded = {row[0]: row for row in record}
        assert set(recorded) == set(names)
        for name, row in recorded.items():
            if name.endswith("RECORD"):
                continue
            algorithm, _, value = row[1].partition("=")
            assert algorithm == "sha256"
            assert value == wheel_b64(archive.read(name))
            assert row[2] == str(len(archive.read(name)))


def wheel_b64(data: bytes) -> str:
    import base64

    return base64.urlsafe_b64encode(sha256(data).digest()).rstrip(b"=").decode("ascii")


def test_synthetic_build_manifest_and_descriptors(synthetic_seed: Path, tmp_path: Path) -> None:
    result = build_library(synthetic_seed, tmp_path / "dist")
    document = result.document

    assert set(document) == manifest.LIBRARY_KEYS
    assert document["format"] == "operon.library"
    assert document["operator_protocol"] == {"version": 3, "revision": "3.7"}
    assert document["descriptor_count"] == result.descriptors == 3
    assert document["operator_count"] == 2
    assert document["reader_count"] == 1
    assert [package["name"] for package in document["packages"]] == [
        "operon-core",
        "operon-microbiome",
        "operon-readers",
    ]

    core = _package(document, "operon-core")
    assert core["kind_counts"] == {"operator": 1, "reader": 0}
    assert core["entry_points"] == {
        "sc_spatial_neighbors": "operon_core.steps.sc_spatial_neighbors:ScSpatialNeighborsStep"
    }
    microbiome = _package(document, "operon-microbiome")
    assert microbiome["entry_points"] == {
        "aggregate": "operon_microbiome.steps.aggregate:AggregateStep"
    }
    readers = _package(document, "operon-readers")
    assert readers["kind_counts"] == {"operator": 0, "reader": 1}
    assert readers["entry_points"] == {"RnkReader": "operon_readers.readers.rnk_reader:RnkReader"}
    assert set(manifest.package_pins(document)) == {
        "sc_spatial_neighbors",
        "aggregate",
        "RnkReader",
    }
    assert manifest.package_pins(document)["aggregate"] == {
        "package": "operon-microbiome",
        "version": "0.0.0",
        "code_sha": microbiome["code_sha"],
    }

    entries = manifest.read_entries(result.path)
    descriptors = json.loads(entries["descriptors.json"])
    assert [descriptor["id"] for descriptor in descriptors] == [
        "aggregate",
        "sc_spatial_neighbors",
        "RnkReader",
    ]
    packages_by_id = {
        identifier: package["code_sha"]
        for package in document["packages"]
        for identifier in package["entry_points"]
    }
    for descriptor in descriptors:
        Descriptor.model_validate(descriptor)
        assert declaration_hash(descriptor) == descriptor["declaration_sha"]
        assert descriptor["code_sha"] == packages_by_id[descriptor["id"]]

    with ZipFile(io.BytesIO(entries["wheels/operon_core-0.0.0-py3-none-any.whl"])) as archive:
        names = set(archive.namelist())
        source = archive.read("operon_core/steps/sc_spatial_neighbors.py").decode("utf-8")
        reader_helper = archive.read("operon_core/readers/_gsea_common.py").decode("utf-8")
    assert "src.task.step.steps" not in source
    assert "src.reader.readers" not in reader_helper
    assert "from operon_core.steps._b65_common import" in source
    assert "from operon_core.readers import _table_common" in reader_helper
    assert "operon_core/steps/_b65_common.py" in names
    assert "operon_core/steps/shared_support.py" in names
    assert "operon_core/readers/_gsea_common.py" in names
    assert "operon_core/__init__.py" in names

    with ZipFile(io.BytesIO(entries["wheels/operon_core-0.0.0-py3-none-any.whl"])) as archive:
        install = json.loads(archive.read("operon_core-0.0.0.dist-info/operon.json"))
    assert [descriptor["id"] for descriptor in install["descriptors"]] == ["sc_spatial_neighbors"]
    assert install["name"] == "operon-core"

    checks = gate(result.path)
    assert len(checks) == 3 + len(document["packages"])


def test_gate_rejects_tampered_code_sha(synthetic_seed: Path, tmp_path: Path) -> None:
    result = build_library(synthetic_seed, tmp_path / "dist")
    entries = manifest.read_entries(result.path)
    document = json.loads(entries["library.json"])
    document["packages"][0]["code_sha"] = "f" * 64
    entries["library.json"] = manifest.json_bytes(document)
    entries.pop("SHA256SUMS")
    entries["SHA256SUMS"] = manifest.sha256sums(entries)
    tampered = manifest.write_bundle(entries, tmp_path / "tampered.zip")

    with pytest.raises(manifest.BundleError, match="code_sha"):
        gate(tampered)


def test_builder_sources_never_import_operon() -> None:
    assert builder_import_violations(PACKAGE_ROOT) == []
    for path in PACKAGE_ROOT.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert "import operon\n" not in source.replace("import operon_sdk", "")
        assert "from operon import" not in source


def test_real_seed_build_and_gate(tmp_path: Path) -> None:
    assert (SEED / "operon" / "builtin_packages.json").is_file()
    dist = tmp_path / "dist"
    assert cli_main(["build", "--source", str(SEED), "--output", str(dist), "--version", "0.0.0"]) == 0
    bundle = dist / "operon-library-v0.0.0.operon-library.zip"
    assert bundle.is_file()
    assert cli_main(["verify", "--dist", str(dist)]) == 0

    document, descriptors = manifest.verify_entries(manifest.read_entries(bundle))
    catalog = json.loads((SEED / "operon" / "builtin_packages.json").read_text(encoding="utf-8"))
    declared = [d for package in catalog["packages"] for d in package["descriptors"]]
    operators = [d for d in declared if d.get("kind") == "operator"]
    readers = [d for d in declared if d.get("kind") == "reader"]
    assert len(document["packages"]) == len(catalog["packages"])
    assert document["descriptor_count"] == len(declared)
    assert document["operator_count"] == len(operators)
    assert document["reader_count"] == len(readers)
    assert len(descriptors) == len(declared)

    checks = gate(bundle)
    assert len(checks) == 3 + len(document["packages"])
    assert any("verify" in check or "archive verified" in check for check in checks)
