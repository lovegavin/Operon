"""A tool that imports pkg_resources gets setuptools installed beside it."""
from pathlib import Path

from operon.environment_store import acquisition


def test_tooling_installs_extra_requirements_and_records_them(tmp_path, monkeypatch):
    commands = []

    def fake_run(command, **kwargs):
        commands.append(list(command))
        return ''

    monkeypatch.setattr(acquisition, 'run_process', fake_run)
    directory = acquisition.tooling(tmp_path, 'conda_pack', '0.8.1', extra=('setuptools<81',))

    installs = [cmd for cmd in commands if 'install' in cmd]
    assert installs, commands
    argv = installs[0]
    assert 'conda-pack==0.8.1' in argv
    assert 'setuptools<81' in argv
    assert (directory / '.ready.json').is_file()
    receipt = (directory / '.ready.json').read_text()
    assert 'setuptools<81' in receipt


def test_pack_conda_pins_pkg_resources_provider(tmp_path, monkeypatch):
    seen = {}

    def fake_tooling(root, module, version, extra=()):
        seen.update(root=root, module=module, version=version, extra=extra)
        return tmp_path / 'conda_pack-0.8.1'

    calls = []
    monkeypatch.setattr(acquisition, 'tooling', fake_tooling)
    monkeypatch.setattr(acquisition, 'run_process', lambda command, **kw: calls.append(list(command)) or '')

    acquisition.pack_conda(tmp_path / 'prefix', tmp_path / 'out.tar', tmp_path)

    assert seen['module'] == 'conda_pack'
    assert seen['version'] == '0.8.1'
    assert seen['extra'] == ('setuptools<81',)
    assert calls and 'conda_pack' in calls[0][-4]
