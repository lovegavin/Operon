import os
from pathlib import Path

from operon import environments


def test_native_path_strips_drive_prefix(monkeypatch):
    monkeypatch.setattr(environments.os, "name", "nt")
    value = environments._native_path(r"\\?\D:\Operon Studio\lib\python.exe")
    assert str(value) == r"D:\Operon Studio\lib\python.exe"


def test_native_path_restores_unc(monkeypatch):
    monkeypatch.setattr(environments.os, "name", "nt")
    value = environments._native_path(r"\\?\UNC\server\share\python.exe")
    assert str(value) == r"\\server\share\python.exe"


def test_native_path_is_noop_on_posix(monkeypatch):
    monkeypatch.setattr(environments.os, "name", "posix")
    value = environments._native_path(r"\\?\D:\x")
    assert str(value) == r"\\?\D:\x"
