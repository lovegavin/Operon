"""The resource installer builds the databases a download declares."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from src.web import resource_api


def test_after_argv_expands_root_threads_and_tool(tmp_path, monkeypatch):
    tool = tmp_path / "bin" / "mmseqslike"
    tool.parent.mkdir()
    tool.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    tool.chmod(0o755)
    monkeypatch.setenv("OPERON_MMSEQSLIKE_PATH", str(tool))
    argv = resource_api._after_argv(
        ["{tool:mmseqslike}", "tsv2db", "{root}/db/seq.tsv", "{root}/db/db", "--threads", "{threads}"],
        tmp_path, )
    assert argv[0] == str(tool)
    assert argv[2] == str(tmp_path / "db" / "seq.tsv")
    assert argv[3] == str(tmp_path / "db" / "db")
    assert argv[5].isdigit() and int(argv[5]) >= 1


def test_after_argv_falls_back_to_the_managed_environment(tmp_path, monkeypatch):
    monkeypatch.delenv("OPERON_MMSEQSLIKE_PATH", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    binary = tmp_path / ".local/share/operon/environments/colabfold/bin/mmseqslike"
    binary.parent.mkdir(parents=True)
    binary.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    binary.chmod(0o755)
    assert resource_api._after_argv(["{tool:mmseqslike}", "version"], tmp_path) == [str(binary), "version"]


def test_after_argv_reports_a_missing_tool(tmp_path, monkeypatch):
    monkeypatch.delenv("OPERON_MISSING_PATH", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    with pytest.raises(RuntimeError, match="is not installed"):
        resource_api._after_argv(["{tool:missing}", "version"], tmp_path)


def test_run_after_streams_the_build_output(tmp_path):
    lines = []
    job = {}
    resource_api._run_after(
        [["/bin/sh", "-c", "echo building; echo done"]],
        root=tmp_path, event=threading.Event(), emit=lines.append, job=job, )
    assert any("BUILD building" in line for line in lines)
    assert any("BUILD done" in line for line in lines)


def test_run_after_fails_on_a_non_zero_exit(tmp_path):
    with pytest.raises(RuntimeError, match="exited with 3"):
        resource_api._run_after(
            [["/bin/sh", "-c", "echo broke >&2; exit 3"]],
            root=tmp_path, event=threading.Event(), emit=lambda line: None, job={}, )


def test_run_after_stops_when_the_download_is_cancelled(tmp_path):
    event = threading.Event()
    event.set()
    with pytest.raises(resource_api._Cancelled):
        resource_api._run_after(
            [["/bin/sh", "-c", "echo never"]],
            root=tmp_path, event=event, emit=lambda line: None, job={}, )


def test_flatten_wrapper_promotes_a_single_nested_directory(tmp_path):
    target = tmp_path / "uniref30_2302"
    inner = target / "uniref30_2302"
    inner.mkdir(parents=True)
    (inner / "uniref30_2302_seq.tsv").write_text("seq\n", encoding="utf-8")
    (inner / "sub").mkdir()
    (inner / "sub" / "keep").write_text("x", encoding="utf-8")
    resource_api._flatten_wrapper(target)
    assert (target / "uniref30_2302_seq.tsv").is_file()
    assert (target / "sub" / "keep").is_file()
    assert not inner.exists()


def test_flatten_wrapper_leaves_a_flat_tree_alone(tmp_path):
    target = tmp_path / "db"
    target.mkdir()
    (target / "seq.tsv").write_text("x", encoding="utf-8")
    (target / "other").write_text("y", encoding="utf-8")
    resource_api._flatten_wrapper(target)
    assert (target / "seq.tsv").is_file() and (target / "other").is_file()


def test_colabfold_msa_declares_its_build_steps(tmp_path):
    path = Path(__file__).resolve().parents[1] / "library/seed/src/task/step/steps/resources.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    entry = next(item for item in data["resources"] if item["id"] == "colabfold_msa")
    assert "createindex" in entry["install"]
    for download in entry["downloads"]:
        steps = download["after"]
        verbs = [step[1] for step in steps]
        assert verbs == ["tsv2db", "tsv2db", "createindex"]
        assert all("{root}" in token for step in steps for token in step if token.startswith("{root}"))
        assert any(token == "{tool:mmseqs}" for step in steps for token in step)


def test_download_then_build_runs_the_declared_index_steps(tmp_path):
    """The installer order: download, flatten the wrapper, run ``after``."""

    import functools
    import http.server
    import io
    import tarfile
    import threading
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w:gz") as tar:
        payload = b"entry\n"
        info = tarfile.TarInfo("uniref30_2302/uniref30_2302_seq.tsv")
        info.size = len(payload)
        tar.addfile(info, io.BytesIO(payload))
    data = archive.getvalue()

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - http.server contract
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/uniref30_2302.tar.gz"
        entry = {
            "url": url,
            "path": "uniref30_2302",
            "archive": "tar.gz",
            "after": [["/bin/sh", "-c",
                       "test -f {root}/uniref30_2302/uniref30_2302_seq.tsv && "
                       "echo built > {root}/uniref30_2302/built.txt"]],
        }
        root = tmp_path / "resources"
        lines = []
        job = {"bytes": 0}
        event = threading.Event()
        opener = functools.partial(_open)
        result = resource_api._download(entry, root, overwrite=False, event=event,
                                        job=job, opener=opener)
        assert result["status"] == "extracted"
        resource_api._flatten_wrapper(root / "uniref30_2302")
        resource_api._run_after(entry["after"], root=root, event=event,
                                emit=lines.append, job=job)
        assert (root / "uniref30_2302" / "uniref30_2302_seq.tsv").is_file()
        assert (root / "uniref30_2302" / "built.txt").read_text(encoding="utf-8").strip() == "built"
    finally:
        server.shutdown()


def _open(url, token_env=""):
    import urllib.request

    return urllib.request.urlopen(url)

def test_run_after_skips_an_optional_step_that_fails(tmp_path):
    lines = []
    resource_api._run_after(
        [{"command": ["/bin/sh", "-c", "echo broke; exit 4"], "optional": True}],
        root=tmp_path, event=threading.Event(), emit=lines.append, job={}, )
    assert any("skipped (optional)" in line and "exited with 4" in line for line in lines)


def test_run_after_skips_an_optional_step_without_its_tool(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    lines = []
    resource_api._run_after(
        [{"command": ["{tool:definitelymissing}", "press"], "optional": True}],
        root=tmp_path, event=threading.Event(), emit=lines.append, job={}, )
    assert any("skipped (optional)" in line and "is not installed" in line for line in lines)


def test_manifest_presses_the_databases_it_declares(tmp_path):
    path = Path(__file__).resolve().parents[1] / "library/seed/src/task/step/steps/resources.json"
    entries = {item["id"]: item for item in json.loads(path.read_text(encoding="utf-8"))["resources"]}

    def steps(resource, download):
        entry = next(item for item in entries[resource]["downloads"] if item["path"] == download)
        return entry["after"]

    assert steps("pfam", "Pfam-A.hmm")[0]["command"][0] == "{tool:hmmpress}"
    assert steps("rfam", "Rfam.cm")[0]["command"][0] == "{tool:cmpress}"
    assert steps("antismash", "tigrfam/TIGRFam.hmm")[0]["command"][0] == "{tool:hmmpress}"
    assert steps("antismash", "resfam/Resfams.hmm")[0]["command"][0] == "{tool:hmmpress}"
    assert steps("vina", "vina_1.2.5_linux_x86_64")[0][:2] == ["/bin/chmod", "0755"]
    assert steps("prodigal", "Makefile")[0]["optional"] is True
