import numpy as np
import pytest
from src.core import Form
class Ctx(dict):
    pass
from src.task.step.steps.tree_consensus import TreeConsensusStep
from src.task.step.steps.tree_quartet_support import TreeQuartetSupportStep
from src.task.step.steps.tree_dating import TreeDatingStep


def form(rows, cols):
    return Form(data=np.asarray(rows, dtype=float), dims=["row", "field"],
                labels={"row": {f"r{i}": i for i in range(len(rows))},
                        "field": cols}, info={"encoders": {}})


def tree_form(texts):
    f = form([[i] for i in range(len(texts))], {"tree": 0})
    f.info["encoders"] = {"field": {"tree": {t: i for i, t in enumerate(texts)}}}
    f.labels["row"] = {f"t{i}": i for i in range(len(texts))}
    return f


def ctx(output):
    c = Ctx()
    c.step_params = {"output": output}
    return c


def test_consensus():
    t1 = "((A:1,B:2):1,(C:3,D:4):1);"
    t2 = "((A:2,B:1):1,(C:4,D:3):1);"
    f = tree_form([t1, t2])
    c = ctx("out")
    TreeConsensusStep().run(c, [f])
    out = c["out"]
    assert out.data.shape == (2, 3)
    assert set(out.labels["entry"]) == {"A|B", "C|D"}


def test_quartet():
    t = "((A:1,B:2):1,(C:3,D:4):1);"
    f = tree_form([t])
    q = form([[0], [1], [2]], {"topology": 0})
    q.labels["row"] = {"A,B,C,D": 0, "A,C,B,D": 1, "A,D,B,C": 2}
    c = ctx("out")
    TreeQuartetSupportStep().run(c, [f, q])
    out = c["out"]
    assert out.labels["entry"]["overall"] == 3
    assert abs(out.data[3, 0] - 1 / 3) < 1e-9


def test_dating():
    t = "((A:1,B:2):1,(C:3,D:4):1);"
    f = tree_form([t])
    d = form([[0], [1], [2], [3]], {"date": 0})
    d.labels["row"] = {"A": 0, "B": 1, "C": 2, "D": 3}
    c = ctx("out")
    TreeDatingStep().run(c, [f, d])
    out = c["out"]
    assert abs(out.data[0, 0] - 1.0) < 1e-9
    assert abs(out.data[0, 1] - 2.0) < 1e-9
