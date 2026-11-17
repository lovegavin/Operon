"""The application version shown in the UI must come from the installed build."""

from __future__ import annotations

import json

from operon import __version__, build_info


def test_display_prefers_build_suffix(monkeypatch):
    monkeypatch.setenv("OPERON_BUILD", "0bbcaa570d84")
    assert build_info.info() == {
        "version": __version__,
        "build": "0bbcaa570d84",
        "display": f"{__version__} (0bbcaa57)",
    }


def test_build_without_suffix_renders_version(monkeypatch):
    monkeypatch.setenv("OPERON_BUILD", "")
    monkeypatch.setattr(build_info, "_version_directory", lambda: "")
    monkeypatch.setattr(build_info, "_installation_record", lambda: {})
    assert build_info.build() == ""
    assert build_info.display() == __version__


def test_version_directory_names(monkeypatch):
    monkeypatch.delenv("OPERON_BUILD", raising=False)
    assert build_info._parse_directory("5.4.1-abcdef123456") == ("5.4.1", "abcdef123456")
    assert build_info._parse_directory("5.4.1") == ("", "")
    monkeypatch.setattr(build_info, "_version_directory", lambda: "5.4.1-abcdef123456")
    assert build_info.build() == "abcdef123456"


def test_installation_record_names(monkeypatch):
    monkeypatch.delenv("OPERON_BUILD", raising=False)
    monkeypatch.setattr(build_info, "_version_directory", lambda: "5.4.1")
    monkeypatch.setattr(build_info, "_installation_record", lambda: {"current": "versions/5.4.1-0123456789ab"})
    assert build_info.build() == "0123456789ab"
    assert build_info.info()["display"].endswith("(01234567)")
