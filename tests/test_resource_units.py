"""Large resources link and unlink one official maintenance unit at a time."""
from types import SimpleNamespace

import pytest

from src.web import resource_api


class LinkModule:
    def __init__(self):
        self.calls = []

    def link(self, resource, source, *, replace=False, unit=None):
        self.calls.append(('link', source, replace, unit))
        return {'status': 'linked', 'unit': unit or 'tree'}

    def unlink(self, resource, unit=None):
        self.calls.append(('unlink', unit))
        return {'status': 'unlinked', 'unit': unit or 'tree'}


def service(monkeypatch, link_module):
    monkeypatch.setattr(resource_api, '_resource',
                        lambda service, name: (None, SimpleNamespace(), None, link_module,
                                               SimpleNamespace(id=name)))
    monkeypatch.setattr(resource_api, '_record_link',
                        lambda name, kind, result, source=None: {'id': 'job-1'})
    monkeypatch.setattr(resource_api, '_link_roots', lambda common: ['/data'])
    return SimpleNamespace()


def test_link_forwards_the_unit(monkeypatch):
    module = LinkModule()
    result = resource_api.link(service(monkeypatch, module), 'esm2', '/data/esm2',
                               replace=True, unit='esm2_t6_8M_UR50D.pt')
    assert module.calls == [('link', '/data/esm2', True, 'esm2_t6_8M_UR50D.pt')]
    assert result['unit'] == 'esm2_t6_8M_UR50D.pt'
    assert result['id'] == 'esm2'
    assert result['operation'] == 'job-1'


def test_link_without_a_unit_links_the_whole_tree(monkeypatch):
    module = LinkModule()
    result = resource_api.link(service(monkeypatch, module), 'alphafold2', '/data/afdb')
    assert module.calls == [('link', '/data/afdb', False, None)]
    assert result['unit'] == 'tree'


def test_unlink_forwards_the_unit(monkeypatch):
    module = LinkModule()
    result = resource_api.unlink(service(monkeypatch, module), 'esm2', 'esm2_t6_8M_UR50D.pt')
    assert module.calls == [('unlink', 'esm2_t6_8M_UR50D.pt')]
    assert result['unit'] == 'esm2_t6_8M_UR50D.pt'


def test_an_old_library_reports_that_it_cannot_link_a_single_unit(monkeypatch):
    class OldLink:
        def link(self, resource, source, *, replace=False, allowed_roots=None):
            return {'status': 'linked'}

    monkeypatch.setattr(resource_api, '_resource',
                        lambda service, name: (None, SimpleNamespace(), None, OldLink(),
                                               SimpleNamespace(id=name)))
    monkeypatch.setattr(resource_api, '_record_link',
                        lambda name, kind, result, source=None: {'id': 'job-1'})
    monkeypatch.setattr(resource_api, '_link_roots', lambda common: ['/data'])
    with pytest.raises(resource_api.LinkUnsupported):
        resource_api.link(SimpleNamespace(), 'esm2', '/data/esm2', unit='a.pt')
