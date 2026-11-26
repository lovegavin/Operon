from __future__ import annotations

import re
from pathlib import Path

STEPS = Path(__file__).resolve().parents[1] / "library" / "seed" / "src" / "task" / "step" / "steps"
RESOLVERS = ("resolve_proteinmpnn_path", "resolve_ligandmpnn_path")


def _imported_names(text: str) -> set[str]:
    names: set[str] = set()
    for match in re.finditer(
        r"^from\s+[\.\w]*_protein_common\s+import\s+\(?([^)\n]+)\)?",
        text,
        re.MULTILINE,
    ):
        names.update(part.strip().rstrip(",") for part in match.group(1).split(","))
    return names


def test_every_step_imports_the_resolver_it_uses() -> None:
    missing: dict[str, list[str]] = {}
    for path in sorted(STEPS.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        used = {
            name for name in RESOLVERS if re.search(rf"\b{name}\s*\(", text)
        }
        if not used:
            continue
        if re.search(r"^def\s+resolve_", text, re.MULTILINE):
            continue
        absent = sorted(used - _imported_names(text))
        if absent:
            missing[path.name] = absent
    assert missing == {}, f"steps call a resolver they do not import: {missing}"
