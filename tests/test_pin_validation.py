"""Historical pin validation must classify unavailable generations."""
import pytest
from types import SimpleNamespace

from src.web.execution_pins import validated_pins


def test_missing_generation_is_classified_and_not_accepted():
    pin = {'version': '1.0', 'package': 'demo', 'sha256': 'a' * 64,
           'code_sha': 'b' * 64}

    def missing(graph):
        raise FileNotFoundError('snapshots/generation.json')

    result = validated_pins(SimpleNamespace(plugins=SimpleNamespace(snapshot=missing)),
                            {'portable': [pin]})
    assert 'portable' not in result
    assert result['__errors__'][0]['operator'] == 'portable'
    assert result['__errors__'][0]['reason'] == 'pin_generation_missing'


def test_unreadable_generation_is_classified():
    pin = {'version': '1.0', 'package': 'demo', 'sha256': 'a' * 64,
           'code_sha': 'b' * 64}

    def unreadable(graph):
        raise PermissionError('snapshots/generation.json')

    result = validated_pins(SimpleNamespace(plugins=SimpleNamespace(snapshot=unreadable)),
                            {'portable': [pin]})
    assert 'portable' not in result
    assert result['__errors__'][0]['reason'] == 'pin_generation_unreadable'


def test_pin_conflict_keeps_its_error_subclass(monkeypatch):
    """A CommandError conflict keeps its code when the missing pins are appended."""
    from operon import pins
    from operon.documents import CommandError

    def requirements(graph, replacements=None, state=None):
        raise CommandError('pin_conflict', '未满足的插件版本')

    monkeypatch.setattr(pins, 'requirements', requirements)
    monkeypatch.setattr(pins, 'refresh_bundled', lambda raw, bundled: raw)
    monkeypatch.setattr(pins, 'unresolved', lambda state, required, limit=5: ' demo (demo, pinned 1.0).')

    candidates = [{'descriptors': [], 'plugin_lock': {}}]
    bundled = {'descriptors': []}
    with pytest.raises(CommandError) as caught:
        pins.resolve(SimpleNamespace(nodes=[], edges=[], plugin_lock={}), candidates, bundled)
    assert isinstance(caught.value, CommandError)
    assert caught.value.code == 'pin_conflict'
    assert '未满足的插件版本' in str(caught.value)
