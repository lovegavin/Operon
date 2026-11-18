"""Unit downloads: weights resolve to the unit URL, any unit can be fetched."""
from types import SimpleNamespace

import pytest

from src.web import resource_api


def resource(**kwargs):
    base = {'downloads': [], 'components': (), 'files': ()}
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_a_unit_without_downloads_uses_its_url():
    unit = {'name': 'afdb', 'url': 'https://example.org/afdb', 'bytes': 1024, 'files': []}
    downloads, allowed = resource_api.unit_downloads('alphafold2', resource(components=(unit,)), 'afdb')
    assert downloads == [{'path': 'afdb', 'url': 'https://example.org/afdb'}]
    assert allowed is None


def test_a_large_unit_still_resolves_to_a_download():
    unit = {'name': 'bfd', 'url': 'https://example.org/bfd', 'bytes': 2 * 1024 ** 4, 'files': []}
    downloads, allowed = resource_api.unit_downloads(
        'alphafold2', resource(components=(unit,)), 'bfd')
    assert downloads == [{'path': 'bfd', 'url': 'https://example.org/bfd'}]
    assert allowed is None


def test_declared_downloads_are_filtered_to_the_unit_files():
    unit = {'name': 'esm2', 'url': '', 'bytes': 10, 'files': ['weights/a.pt']}
    declared = [{'path': 'weights/a.pt', 'url': 'https://example.org/a'},
                {'path': 'weights/b.pt', 'url': 'https://example.org/b'}]
    downloads, allowed = resource_api.unit_downloads('esm2', resource(downloads=declared, components=(unit,)), 'esm2')
    assert downloads == declared
    assert allowed == {'weights/a.pt'}


def test_an_unknown_unit_is_reported():
    with pytest.raises(ValueError) as error:
        resource_api.unit_downloads('esm2', resource(), 'nope')
    assert 'has no unit named' in str(error.value)


def test_a_resource_without_downloads_and_without_a_unit_is_reported():
    with pytest.raises(ValueError) as error:
        resource_api.unit_downloads('afdb', resource(), None)
    assert 'has no downloadable files' in str(error.value)
