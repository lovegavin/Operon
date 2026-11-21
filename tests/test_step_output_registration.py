"""Coverage for steps that list static ports and name their output by parameter."""
import numpy as np

from src.core import Form
from src.task import Context, STEPS, run
from src.task.step.base import Step


def _form():
    return Form(data=np.zeros((2, 2), dtype=np.float32), dims=["sample", "feature"],
                labels={"sample": {"s0": 0, "s1": 1}, "feature": {"x0": 0, "x1": 1}})


class PortNamedStep(Step):
    name = "port_named"
    parameters_schema = {"type": "object", "properties": {"output": {"type": "string"}}}
    input_contracts = [{}]
    inputs_arity = 1
    outputs = ["annotation"]
    output_parameter = "output"

    def run(self, ctx, inputs):
        ctx[ctx.step_params.get("output", self.name)] = inputs[0]


class MissingStep(Step):
    name = "port_missing"
    parameters_schema = {"type": "object", "properties": {"output": {"type": "string"}}}
    input_contracts = [{}]
    inputs_arity = 1
    outputs = ["annotation"]
    output_parameter = "output"

    def run(self, ctx, inputs):
        pass


def test_parameter_named_output_need_not_register_static_port(tmp_path, monkeypatch):
    monkeypatch.setitem(STEPS, PortNamedStep.name, PortNamedStep)
    steps = [{"name": PortNamedStep.name, "inputs": ["src"], "params": {"output": "n1"}}]
    ctx = Context(tmp_path, {"sources": {}, "steps": steps})
    ctx["src"] = _form()
    run(ctx, steps)
    assert "n1" in ctx.written_outputs


def test_still_rejects_a_run_that_registers_nothing(tmp_path, monkeypatch):
    monkeypatch.setitem(STEPS, MissingStep.name, MissingStep)
    steps = [{"name": MissingStep.name, "inputs": ["src"], "params": {"output": "n1"}}]
    ctx = Context(tmp_path, {"sources": {}, "steps": steps})
    ctx["src"] = _form()
    try:
        run(ctx, steps)
    except Exception as error:  # StepError carries the message the UI shows
        assert "declared output 'n1' but did not register it" in str(error)
    else:
        raise AssertionError("a step that registers no output must fail")
