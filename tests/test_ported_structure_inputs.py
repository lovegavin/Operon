"""Ported structure/receptor inputs must reach the operator instead of being deleted."""
import pytest

from src.core import StepError
from src.task.step.steps import rfdiffusion_design as rfdiffusion
from src.task.step.steps import vina_dock as vina


class Params:
    def __init__(self, values):
        self.step_params = values


def test_rfdiffusion_uses_the_ported_structure_input(monkeypatch):
    seen = []

    def resolve(*args, **kwargs):
        seen.append((args, kwargs))
        raise StepError('probe: structure input reached the operator')

    monkeypatch.setattr(rfdiffusion._port_inputs, 'structure', resolve)
    with pytest.raises(StepError, match='probe: structure input'):
        rfdiffusion.RfdiffusionDesignStep().run(Params({}), [object()])
    assert seen


def test_vina_uses_the_ported_receptor_input(monkeypatch):
    seen = []

    def resolve(*args, **kwargs):
        seen.append((args, kwargs))
        raise StepError('probe: receptor input reached the operator')

    monkeypatch.setattr(vina._port_inputs, 'file', resolve)
    with pytest.raises(StepError, match='probe: receptor input'):
        vina.VinaDockStep().run(Params({}), [object()])
    assert seen
