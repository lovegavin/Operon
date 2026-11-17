"""MCP list results must not require a hardcoded desktop session ID."""
import asyncio
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.verify_release_agent import Acceptance, packaged_file


def test_packaged_file_requires_real_file_in_selected_root(tmp_path):
    root = tmp_path / 'App With Spaces'
    entry = root / 'scripts' / 'desktop_server.py'
    entry.parent.mkdir(parents=True)
    entry.write_text('# selected installation')
    foreign = tmp_path / 'other' / 'desktop_server.py'
    foreign.parent.mkdir()
    foreign.write_text(entry.read_text())
    assert packaged_file(entry, root)
    assert not packaged_file(foreign, root)
    assert not packaged_file(root / 'missing.py', root)
    assert not packaged_file(entry.parent, root)


@pytest.mark.skipif(os.name != 'nt', reason='Actual Windows extended-path identity')
def test_tauri_extended_path_matches_only_selected_installation(tmp_path):
    root = tmp_path / 'App With Spaces'
    entry = root / 'scripts' / 'desktop_server.py'
    entry.parent.mkdir(parents=True)
    entry.write_text('# selected installation')
    extended = Path('\\\\?\\' + str(entry.resolve()))
    # This is the original RC3 verifier failure, observed on the test machine.
    assert not extended.resolve().is_relative_to(root.resolve())
    assert packaged_file(extended, root)
    assert packaged_file(entry, '\\\\?\\' + str(root.resolve()))
    other = tmp_path / 'other'
    other.mkdir()
    assert not packaged_file(extended, other)


@pytest.mark.parametrize('sessions,structured,as_array', [
    ([], True, False),
    ([{'id': 'actual-window'}], False, False),
    ([{'id': 'one'}, {'id': 'two'}], False, False),
    ([{'id': 'actual-window'}], False, True),
    ([{'id': 'actual-window'}], True, False),
])
def test_real_session_list_transport_shapes(tmp_path, sessions, structured, as_array):
    async def call_tool(*args):
        values = [sessions] if as_array else sessions
        return SimpleNamespace(isError=False,
            content=[SimpleNamespace(text=json.dumps(value)) for value in values],
            structuredContent={'result': sessions} if structured else None)
    run = Acceptance.__new__(Acceptance)
    run.evidence = tmp_path
    assert asyncio.run(run.call(SimpleNamespace(call_tool=call_tool), 'operon_sessions')) == sessions
