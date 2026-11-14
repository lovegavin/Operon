from pathlib import Path

from src.reader import read_source
from library.seed.src.task.step.steps.structure_extract_chain import StructureExtractChainStep
from library.seed.src.task.step.steps._protein_common import decode_column

ROOT = Path(__file__).resolve().parents[1]


class Ctx(dict):
    def __init__(self, base, params):
        super().__init__()
        self.step_params = params
        self.base = Path(base)

    def artifact_path(self, name):
        return str(self.base / name)


def test_extract_chain(tmp_path):
    form = read_source(ROOT / "tests/fixtures/vhh_1mel.pdb", ["atom", "field"],
                       {"atom": "auto", "field": "builtin"})
    ctx = Ctx(tmp_path, {"chains": "A", "filename": "chainA.pdb"})
    step = StructureExtractChainStep()
    step.run(ctx, [form])
    out = ctx["output"]
    assert out.data.shape[0] > 0
    assert out.data.shape[0] < form.data.shape[0]
    assert {str(v) for v in decode_column(out, "field", "chain")} == {"A"}
    files = step.export(ctx)["result_files"]
    text = Path(files[0]["path"]).read_text()
    assert text.startswith("ATOM")
    assert text.rstrip().endswith("END")
