"""Result inventory and download paths for 5.1.13."""
import asyncio
import threading
from pathlib import Path

import pytest

from src.web.service import JobService


def _service(tmp_path):
    service = JobService.__new__(JobService)
    service.root = tmp_path
    service.directory = tmp_path / ".studio"
    service.jobs_dir = service.directory / "jobs"
    service.jobs_dir.mkdir(parents=True)
    output = tmp_path / "task1" / "results" / "job1"
    (output / "runs").mkdir(parents=True)
    (output / "a.csv").write_text("x,y\\n1,2\\n", encoding="utf-8")
    (output / "runs" / "events.jsonl").write_text("{}\\n", encoding="utf-8")
    service.jobs = {"job1": {"id": "job1", "output_dir": str(output)}}
    service.lock = threading.RLock()
    return service, output


def test_result_files_list_nested_and_total(tmp_path):
    service, _ = _service(tmp_path)
    listing = service.result_files("job1")
    assert [item["path"] for item in listing["files"]] == ["a.csv", "runs/events.jsonl"]
    assert listing["total_bytes"] == sum(item["bytes"] for item in listing["files"])


def test_result_path_returns_file_bytes(tmp_path):
    service, output = _service(tmp_path)
    path = service.result_path("job1", "a.csv")
    assert Path(path).read_bytes() == (output / "a.csv").read_bytes()


def test_result_file_alias_matches_result_path(tmp_path):
    service, output = _service(tmp_path)
    path = service.result_file("job1", "a.csv")
    assert Path(path).read_bytes() == (output / "a.csv").read_bytes()


def test_result_path_rejects_traversal_and_absolute(tmp_path):
    service, _ = _service(tmp_path)
    with pytest.raises(ValueError):
        service.result_path("job1", "../secret.txt")
    with pytest.raises(ValueError):
        service.result_path("job1", str(tmp_path / "secret.txt"))
    with pytest.raises(KeyError):
        service.result_path("job1", "missing.csv")


def test_mcp_exposes_download_tools():
    from operon.mcp_server import create_server
    names = {tool.name for tool in asyncio.run(create_server(object()).list_tools())}
    assert {"operon_result_files", "operon_download_result", "operon_download_results",
            "operon_download_artifact", "operon_download_report"} <= names
