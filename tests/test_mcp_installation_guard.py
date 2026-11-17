"""The MCP adapter must not serve from a removed installation."""

from pathlib import Path

import pytest

from operon import mcp_server


def test_require_installation_accepts_a_live_tree(tmp_path):
    root = tmp_path / 'install'
    (root / 'operon').mkdir(parents=True)
    (root / 'operon' / 'managed_pool.py').write_text('', encoding='utf-8')
    assert mcp_server.require_installation(root) == root.resolve()


def test_require_installation_refuses_a_removed_version(tmp_path):
    root = tmp_path / 'versions' / '5.4.2-gone'
    (root / 'operon').mkdir(parents=True)
    with pytest.raises(SystemExit) as error:
        mcp_server.require_installation(root)
    assert 'was removed or replaced' in str(error.value)


def test_the_checkout_is_a_live_installation():
    root = mcp_server.require_installation()
    assert (root / 'operon' / 'managed_pool.py').is_file()
