"""Ask the installed generation resolver to prove historical pin availability."""
from .models import Graph


def validated_pins(service, requested):
    if not isinstance(requested, dict):
        raise ValueError('Pin compatibility request must be an object')
    result = {}
    errors = []
    for key, values in requested.items():
        if not isinstance(values, list):
            raise ValueError('Pin compatibility values must be lists')
        for pin in values:
            probe = Graph(nodes=[], edges=[], plugin_lock={key: pin})
            try:
                service.plugins.snapshot(probe)
            except FileNotFoundError as exc:
                errors.append({'operator': key, 'reason': 'pin_generation_missing',
                               'error': f'{type(exc).__name__}: {exc}'})
                continue
            except OSError as exc:
                errors.append({'operator': key, 'reason': 'pin_generation_unreadable',
                               'error': f'{type(exc).__name__}: {exc}'})
                continue
            except ValueError as exc:
                errors.append({'operator': key, 'reason': 'pin_generation_incompatible',
                               'error': str(exc)})
                continue
            result.setdefault(key, []).append(pin)
    if errors:
        result['__errors__'] = errors
    return result
