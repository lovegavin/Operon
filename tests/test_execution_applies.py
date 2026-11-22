"""A remote target without any source node still belongs to the remote path."""
from __future__ import annotations

from src.web.execution import ExecutionService
from src.web.models import Graph


def _graph(runtime, nodes=()):
    return Graph.model_validate({
        "name": "probe",
        "runtime": runtime,
        "nodes": list(nodes),
        "edges": [],
    })


def _operator(node_id="main"):
    return {
        "id": node_id,
        "kind": "operator",
        "operator": "rdkit_admet_rules",
        "position": {"x": 0, "y": 0},
        "params": {},
    }


def _source():
    return {
        "id": "src0",
        "kind": "source",
        "position": {"x": 0, "y": 0},
        "source": {"reader": "CsvReader", "path": "p6/fixtures/mlf_reg.csv",
                   "location": {"kind": "ssh", "profile_id": "abc"}},
    }


def test_explicit_ssh_target_without_sources_applies():
    graph = _graph({"execution": {"kind": "ssh", "profile_id": "abc"}}, [_operator()])
    assert ExecutionService.applies(graph) is True


def test_local_runtime_without_sources_stays_local():
    graph = _graph({"execution": {"kind": "local"}}, [_operator()])
    assert ExecutionService.applies(graph) is False


def test_source_location_still_applies():
    graph = _graph({}, [_source(), _operator()])
    assert ExecutionService.applies(graph) is True


def test_child_execution_is_never_reexecuted():
    graph = _graph({"execution": {"kind": "ssh", "profile_id": "abc"},
                    "execution_parent_id": "exec-1"}, [_operator()])
    assert ExecutionService.applies(graph) is False
