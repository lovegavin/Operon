import json
from pathlib import Path

import pytest

from operon.pins import refresh_missing
from src.web.models import Graph
from src.web.service import JobService


def test_csv_table_pages_exported_files(tmp_path):
    path = tmp_path / "alanine.csv"
    rows = ["label,wt_delta_kj,count"] + [f"L:{index}, {index * 1.5}, {index}" for index in range(23)]
    path.write_text("\n".join(rows), encoding="utf-8")
    payload = {"files": {"data": str(path)}, "fingerprints": {"data": {"size": path.stat().st_size}},
               "format": "csv", "info": {}}
    table = JobService._csv_table(None, payload, offset=20, limit=5)
    assert table["total"] == 23
    assert table["offset"] == 20 and table["limit"] == 5
    assert table["columns"] == ["label", "wt_delta_kj", "count"]
    assert table["rows"] == [["L:20", " 30.0", " 20"], ["L:21", " 31.5", " 21"], ["L:22", " 33.0", " 22"]]
    assert table["file"] == "alanine.csv"


def test_csv_table_accepts_tsv_and_bounds_limit(tmp_path):
    path = tmp_path / "values.tsv"
    path.write_text("a\tb\n1\t2\n", encoding="utf-8")
    payload = {"files": {"data": str(path)}, "fingerprints": {}, "format": "tsv", "info": {}}
    table = JobService._csv_table(None, payload, offset=0, limit=9999)
    assert table["columns"] == ["a", "b"] and table["rows"] == [["1", "2"]]
    assert table["limit"] == 1000


def test_refresh_missing_replaces_only_stale_bundled_pins():
    state = {"packages": [{"name": "operon-core", "origin": "bundled", "sha256": "new", "code_sha": "code-new"}],
             "descriptors": [{"id": "describe", "distribution": "operon-core", "origin": "bundled",
                              "code_sha": "code-new", "implementation": {"sha256": "impl-new", "code_sha": "code-new"}}]}
    graph = Graph.model_validate({
        "nodes": [{"id": "summary", "kind": "operator", "operator": "describe",
                   "position": {"x": 0, "y": 0}, "params": {}}],
        "edges": []})
    graph.plugin_lock["describe"] = {"sha256": "old", "code_sha": "old"}
    migrations = refresh_missing(graph, state)
    assert len(migrations) == 1
    assert graph.plugin_lock["describe"]["sha256"] == "impl-new"
    assert migrations[0]["reason"].startswith("Pinned implementation is no longer installed")


def test_refresh_missing_leaves_matching_and_unknown_pins():
    state = {"packages": [], "descriptors": []}
    graph = Graph.model_validate({
        "nodes": [{"id": "summary", "kind": "operator", "operator": "describe",
                   "position": {"x": 0, "y": 0}, "params": {}}],
        "edges": []})
    graph.plugin_lock["describe"] = {"sha256": "missing-artifact"}
    assert refresh_missing(graph, state) == []
    assert graph.plugin_lock["describe"] == {"sha256": "missing-artifact"}
