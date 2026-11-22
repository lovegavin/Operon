"""A wheel URL is a dependency that reports its project name."""

from operon.environment_install import _requirement_name, _wheel_project


URL = (
    "https://data.pyg.org/whl/torch-2.3.0%2Bcu121/"
    "torch_scatter-2.1.2%2Bpt23cu121-cp311-cp311-linux_x86_64.whl"
)


def test_wheel_url_reports_the_project():
    assert _wheel_project(URL) == "torch_scatter"
    assert _requirement_name(URL) == "torch-scatter"


def test_local_path_wheel_reports_the_project():
    assert _requirement_name(r"D:\wheels\torch_scatter-2.1.2-cp311.whl") == "torch-scatter"


def test_plain_requirements_are_unchanged():
    assert _requirement_name("torch==2.3.1") == "torch"
    assert _requirement_name("setuptools>=68,<81") == "setuptools"
    assert _requirement_name("torch_geometric") == "torch-geometric"
