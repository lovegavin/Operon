"""Isolated steps must keep the files they produce after the bridge exits."""
import os

from operon import environments


def test_files_written_inside_the_bridge_are_copied_out(tmp_path):
    bridge = tmp_path / 'bridge'
    (bridge / 'out').mkdir(parents=True)
    produced = bridge / 'out' / 'report.csv'
    produced.write_text('a,b\n1,2\n', encoding='utf-8')

    placed = environments._relocate_files({'table': str(produced)}, bridge, tmp_path / 'keep')

    assert placed['table'] != str(produced)
    assert os.path.isfile(placed['table'])
    assert pathlib_path(placed['table']).read_text(encoding='utf-8') == 'a,b\n1,2\n'
    assert not str(placed['table']).startswith(str(bridge))


def pathlib_path(value):
    import pathlib
    return pathlib.Path(value)


def test_files_outside_the_bridge_are_left_alone(tmp_path):
    keep = tmp_path / 'keep.csv'
    keep.write_text('x\n', encoding='utf-8')
    bridge = tmp_path / 'bridge'
    bridge.mkdir()

    placed = environments._relocate_files({'table': str(keep)}, bridge, tmp_path / 'out')

    assert placed['table'] == str(keep.resolve())
