"""Promotion must leave the environment usable on its own."""

from __future__ import annotations

from pathlib import Path

from operon import environment_install


def test_rewrite_shebangs_points_scripts_at_the_promoted_tree(tmp_path: Path) -> None:
    staging = tmp_path / ".staging-demo-1234"
    scripts = staging / "Scripts"
    scripts.mkdir(parents=True)
    script = scripts / "demo-script.py"
    script.write_bytes(
        f"#!{staging.as_posix()}/bin/python\nprint('ok')\n".encode("utf-8")
    )
    plain = scripts / "plain.py"
    plain.write_bytes(b"print('untouched')\n")

    final = tmp_path / "demo-1234"
    staging.rename(final)
    changed = environment_install._rewrite_shebangs(final, staging)

    assert changed == 1
    head = (final / "Scripts" / "demo-script.py").read_bytes().split(b"\n", 1)[0].decode("utf-8")
    assert ".staging-" not in head
    assert head == f"#!{final.as_posix()}/bin/python"
    assert (final / "Scripts" / "plain.py").read_bytes() == b"print('untouched')\n"


def test_activity_signature_tracks_new_files(tmp_path: Path) -> None:
    watched = tmp_path / "cache"
    watched.mkdir()
    before = environment_install._activity_signature([watched])
    (watched / "one.whl").write_bytes(b"x")
    after = environment_install._activity_signature([watched])
    assert before != after
    assert environment_install._activity_signature([tmp_path / "absent"]) == ((str(tmp_path / "absent"), -1),)


def test_pip_transfer_asks_for_line_progress() -> None:
    assert "--progress-bar" in environment_install.PIP_TRANSFER
    assert "raw" in environment_install.PIP_TRANSFER
