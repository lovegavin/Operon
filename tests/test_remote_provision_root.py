from pathlib import Path

from operon.remote.provision import application_root


def test_application_root_is_the_shipped_tree():
    root = Path(application_root())
    assert (root / 'operon' / 'remote' / 'provision.py').is_file()
    assert (root / 'src' / 'task').is_dir()


def test_application_root_skips_site_packages(monkeypatch, tmp_path):
    # A runtime import resolves `operon` inside site-packages; the helper must
    # still report the version directory that owns the application payload.
    import operon.remote.provision as provision

    def fake_code_root():
        return tmp_path / 'versions' / '4.1.9-test'

    monkeypatch.setattr('operon.environments.code_root', fake_code_root)
    assert provision.application_root() == fake_code_root()
