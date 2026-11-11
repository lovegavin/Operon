"""Historical pin validation must classify unavailable generations."""
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
