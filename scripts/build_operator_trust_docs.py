#!/usr/bin/env python3
"""Generate per-operator trust sheets from descriptors and audit evidence.

Every sheet answers, in about five minutes of reading:

* what the code does (entry point, source size, docstring, parameters);
* which evidence exists at each of the five layers and where it lives;
* what that evidence does and does not prove;
* how to reproduce it.

Evidence is never upgraded.  ``compiled`` (route only) is weaker than
``executed`` (a recorded real run), which is weaker than ``oracle`` (an
independent implementation with a measured delta).
"""

from __future__ import annotations

import ast
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "library" / "seed"
OUT = ROOT / "docs" / "operators"
LEDGER = ROOT / "verification" / "coverage-8.0.1" / "operator_coverage.csv"
LOCAL_RUNS = ROOT / "verification" / "coverage-8.0.1" / "evidence" / "local_runs.json"
SRV_RUNS = ROOT / "verification" / "coverage-8.0.1" / "evidence" / "srv_runs.json"
ORACLES = ROOT / "verification" / "operator-audit-8.0.1" / "l2_oracle.json"
PACKAGES = SEED / "operon" / "builtin_packages.json"


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_descriptors() -> dict[str, dict]:
    data = load_json(PACKAGES)
    out: dict[str, dict] = {}
    for package in data.get("packages", []):
        for item in package.get("descriptors", []):
            if item.get("kind") == "operator":
                out[item["id"]] = item
    return out


def load_ledger() -> dict[str, dict]:
    with LEDGER.open(newline="", encoding="utf-8") as handle:
        return {row["id"]: row for row in csv.DictReader(handle)}


def load_runs() -> tuple[dict[str, dict], dict[str, dict]]:
    local_raw = load_json(LOCAL_RUNS).get("runs", {})
    local: dict[str, dict] = {}
    for op, entry in (local_raw.items() if isinstance(local_raw, dict) else []):
        if isinstance(entry, dict) and entry.get("status") == "PASS":
            local[op] = entry
    srv: dict[str, dict] = {}
    for entry in load_json(SRV_RUNS).get("runs", []):
        op = entry.get("operator")
        if op and entry.get("exports"):
            current = srv.get(op)
            if current is None or entry.get("total_elapsed", 0) < current.get("total_elapsed", 1e9):
                srv[op] = entry
    return local, srv


def source_path(entry_point: str) -> Path | None:
    module = entry_point.split(":", 1)[0]
    path = SEED / (module.replace(".", "/") + ".py")
    return path if path.exists() else None


def source_facts(path: Path | None) -> tuple[int, list[str], str, str]:
    if path is None:
        return 0, [], "", ""
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.count("\n") + 1
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return lines, [], "", ""
    symbols: list[str] = []
    class_doc = ""
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            symbols.append(f"class {node.name} (line {node.lineno})")
            class_doc = ast.get_docstring(node) or class_doc
        elif isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
            symbols.append(f"def {node.name}() (line {node.lineno})")
    doc = ast.get_docstring(tree) or class_doc
    return lines, symbols[:8], re.sub(r"\s+", " ", doc).strip(), path.name


def markdown_sections(descriptor: dict) -> dict[str, str]:
    rel = (descriptor.get("documentation") or {}).get("path")
    if not rel:
        return {}
    path = SEED / "src/task/step/steps" / rel
    if not path.exists():
        return {}
    sections: dict[str, list[str]] = {}
    key = ""
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = re.match(r"^##\s+(.+?)\s*$", line)
        if match:
            key = match.group(1).strip().lower().replace(" ", "-")
            sections[key] = []
        elif key:
            sections[key].append(line)
    return {k: "\n".join(v).strip() for k, v in sections.items()}


def first_sentence(text: str, limit: int = 320) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return ""
    return text[:limit].rsplit(" ", 1)[0] + ("…" if len(text) > limit else "")


def trust_level(row: dict) -> tuple[str, str]:
    l2, l3 = row.get("l2", ""), row.get("l3", "")
    executed = l3 in {"EXECUTED", "EXECUTED_SRV", "EXECUTED_SRV_DRIFT"}
    routed = l3 in {"ROUTE", "EXECUTED", "EXECUTED_SRV"}
    if l2 == "ORACLE" and executed:
        return "A", "独立 oracle + 真实执行"
    if l2 == "ORACLE":
        return "A-", "独立 oracle（未记录真实执行）"
    if executed:
        return "B", "真实执行（本地或 srv）"
    if l2 == "UNIT" and routed:
        return "C", "专用测试引用 + 可编译路线"
    if l2 == "UNIT":
        return "D", "专用测试引用（无真实执行）"
    if l2 == "SMOKE":
        return "D", "冒烟测试引用（无独立 oracle）"
    return "E", "仅静态契约（尚无行为证据）"


def param_rows(schema: dict) -> list[tuple[str, str, str, str]]:
    rows = []
    for name, spec in (schema.get("properties") or {}).items():
        default = spec.get("default", "")
        if isinstance(default, (list, dict)):
            default = json.dumps(default, ensure_ascii=False)
        default = str(default)
        if len(default) > 36:
            default = default[:36] + "…"
        title = str(spec.get("title") or "").strip()
        bits = []
        if spec.get("type") == "integer" or spec.get("type") == "number":
            if "minimum" in spec:
                bits.append(f"min {spec['minimum']}")
            if "maximum" in spec:
                bits.append(f"max {spec['maximum']}")
        if spec.get("enum"):
            bits.append("choices: " + ", ".join(str(x) for x in spec["enum"]))
        if spec.get("x-ui-group") == "advanced":
            bits.append("advanced")
        meaning = title or first_sentence(spec.get("description", ""), 90)
        if bits:
            meaning = (meaning + "; " if meaning else "") + "; ".join(bits)
        rows.append((name, default, meaning, str(spec.get("description", ""))))
    return rows


def evidence_sentence(level: str, row: dict, local: dict | None, srv: dict | None, oracle: dict | None) -> str:
    if level.startswith("A") and oracle:
        delta = oracle.get("delta")
        detail = f"独立实现「{oracle.get('oracle', '')}」"
        if isinstance(delta, (int, float)):
            detail += f"，实测差值 {delta:.3e}"
        elif oracle.get("got") is not None:
            detail += f"，算子 {oracle.get('got')} vs 参考 {oracle.get('expected')}"
        return detail + "。"
    if local:
        artifacts = local.get("artifacts") or []
        sha = str(artifacts[0].get("sha256", ""))[:16] if artifacts else "n/a"
        return (
            f"真实运行通过（{local.get('seconds', '?')} s），导出 {local.get('export_rows', '?')} 行，"
            f"产物 sha256 {sha}…。"
        )
    if srv:
        exports = srv.get("exports") or []
        return (
            f"服务器真实运行通过（{srv.get('total_elapsed', '?')} s），{len(exports)} 个步骤产物，"
            f"首个 sha256 {str(exports[0].get('sha256', ''))[:16]}…。"
        )
    if level == "C":
        return "路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。"
    if level == "D":
        return "只有专用/冒烟测试引用；没有记录真实执行。"
    return "目前只有静态契约，没有行为证据；不要把它当成已验证算子。"


def render(
    descriptor: dict,
    row: dict,
    local: dict | None,
    srv: dict | None,
    oracle: dict | None,
) -> str:
    op = descriptor["id"]
    entry = descriptor.get("entry_point", "")
    path = source_path(entry)
    loc, symbols, doc, filename = source_facts(path)
    sections = markdown_sections(descriptor)
    level, level_text = trust_level(row)
    source = f"library/seed/src/task/step/steps/{filename}" if path else "n/a"

    out = [
        f"# {descriptor['title']} (`{op}`)",
        "",
        f"**Category:** {descriptor.get('category', '')}  ",
        f"**Entry point:** `{entry}`  ",
        f"**Source:** [`{source}`](../../{source}) ({loc} lines)  ",
        f"**Trust level: {level} — {level_text}**",
        "",
        "## 1. 代码说明",
        "",
        first_sentence(descriptor.get("description", ""), 700) or "(descriptor has no description)",
        "",
    ]
    if doc:
        out += [f"> {first_sentence(doc, 600)}", ""]
    if symbols:
        out += ["关键符号：", ""] + [f"- `{s}`" for s in symbols] + [""]
    out += [
        f"协议：v3 / revision `{descriptor.get('protocol_revision', '')}`；输出参数 `{descriptor.get('output_parameter', '')}`。",
        "",
        "### 输入与输出",
        "",
    ]
    contracts = descriptor.get("contracts") or {}
    for index, contract in enumerate(contracts.get("inputs") or [], 1):
        dims = ", ".join(
            (d.get("param", "?") if isinstance(d, dict) else str(d))
            for d in contract.get("dims") or []
        ) or "—"
        info = ", ".join(sorted((contract.get("info") or {}).keys())) or "—"
        out.append(
            f"- 输入 {index}: ndim={contract.get('ndim', '?')}, numeric={contract.get('numeric', '?')}, "
            f"dims=({dims}), info=({info})"
        )
    output = contracts.get("output") or {}
    out.append(
        f"- 输出: mode={output.get('mode', '?')}, schema={json.dumps(output.get('schema', {}), ensure_ascii=False)[:300]}"
    )
    out.append("")

    rows = param_rows(descriptor.get("parameters_schema") or {})
    if rows:
        out += ["### 参数", "", "| 参数 | 默认值 | 含义/约束 |", "| --- | --- | --- |"]
        for name, default, meaning, _ in rows[:20]:
            out.append(f"| `{name}` | `{default}` | {meaning or '—'} |")
        if len(rows) > 20:
            out.append(f"| … | | 另有 {len(rows) - 20} 个参数，见 parameters schema |")
        out.append("")

    purpose = sections.get("purpose", "")
    if purpose:
        cleaned = "\n".join(
            line.lstrip("> ").rstrip() if line.startswith(">") else line
            for line in purpose.splitlines()
        ).strip()
        if cleaned:
            out += ["## 2. 用途与解释", "", cleaned[:900], ""]

    out += ["## 3. 正确性依据", ""]
    out.append(f"**结论：{level} 级。** {evidence_sentence(level, row, local, srv, oracle)}")
    out.append("")
    out += [
        "| 层 | 状态 | 证据 |",
        "| --- | --- | --- |",
        f"| L1 契约/清单 | {row.get('l1', '?')} | {row.get('l1_evidence', '')} |",
        f"| L2 单元/oracle | {row.get('l2', '?')} | {row.get('l2_evidence', '')} |",
        f"| L3 真实执行 | {row.get('l3', '?')} | {row.get('l3_evidence', '')} |",
        f"| L4 资源 | {row.get('l4', '?')} | {row.get('l4_evidence', '')} |",
        f"| L5 应用安装 | {row.get('l5', '?')} | {row.get('l5_evidence', '')} |",
        "",
    ]
    if oracle:
        out += [
            "独立 oracle 细节：",
            "",
            f"- 参考实现：{oracle.get('oracle', '')}",
            f"- 结果：pass={oracle.get('pass')}, delta={oracle.get('delta')}, tolerance={oracle.get('tolerance')}",
        ]
        if oracle.get("note"):
            out.append(f"- 说明：{oracle['note']}")
        out.append("")
    if local:
        out += [
            "本次执行细节：",
            "",
            f"- 状态：{local.get('status')}，耗时 {local.get('seconds')} s，导出 {local.get('export_rows')} 行。",
            f"- 归档路线：`{local.get('route')}`。",
            f"- 命令：`{local.get('command')}`。",
            "",
        ]
    if srv:
        out += [
            "服务器执行细节：",
            "",
            f"- 状态：complete，总耗时 {srv.get('total_elapsed')} s，步骤 {srv.get('n_steps')}。",
            f"- 路线：`{srv.get('route_dir')}`；run_id `{srv.get('run_id')}`。",
            "",
        ]

    out += [
        "### 这个证据证明什么、不证明什么",
        "",
        "- 证明：契约可解析、输入输出维度一致；有执行记录时，真实数据能跑到 `Task finished` 并产生可校验产物。",
        "- 不证明：该算子在该数据集上的生物学结论正确；统计假设是否成立仍需使用者判断。",
    ]
    if level in {"C", "D", "E"}:
        out.append("- 注意：该算子没有独立数值 oracle， correctness 仅到“契约/测试/执行”层级。")
    out.append("")

    limits = sections.get("limitations", "")
    out += ["## 4. 限制与失败模式", ""]
    out.append(limits[:1200] if limits else "相邻算子 Markdown 是参数约束与失败模式的权威说明；未找到单独的限制段。")
    out.append("")

    examples = sections.get("examples", "")
    out += ["## 5. 复现", "", "```bash", "cd /home/gavin/Operon-7015-native", "python -m operon registry check --json", f"grep '^{op},' verification/coverage-8.0.1/operator_coverage.csv", "```", ""]
    if examples:
        out += ["算子手册中的示例：", "", "```text", examples[:1200], "```", ""]
    if row.get("gaps"):
        out += [f"未补齐证据：`{row['gaps']}`。", ""]
    out += ["---", "", "由 `scripts/build_operator_trust_docs.py` 生成；审计基线 8.0.1。", ""]
    return "\n".join(out)


def main() -> None:
    descriptors = load_descriptors()
    ledger = load_ledger()
    local_runs, srv_runs = load_runs()
    oracle_results = load_json(ORACLES).get("results", {})
    missing = sorted(set(descriptors) - set(ledger))
    if missing:
        raise SystemExit(f"ledger misses {len(missing)} operators: {missing[:5]}")
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.md"):
        old.unlink()

    counts: Counter[str] = Counter()
    by_category: defaultdict[str, Counter[str]] = defaultdict(Counter)
    index_rows = []
    for op in sorted(descriptors):
        descriptor = descriptors[op]
        row = ledger[op]
        level, _ = trust_level(row)
        counts[level] += 1
        by_category[descriptor.get("category", "")][level] += 1
        (OUT / f"{op}.md").write_text(
            render(descriptor, row, local_runs.get(op), srv_runs.get(op), oracle_results.get(op)),
            encoding="utf-8",
        )
        index_rows.append((op, descriptor, row, level))

    index = [
        "# Operator trust sheets",
        "",
        "One page per operator: what the code does, the evidence behind it, its",
        "limits, and how to reproduce the evidence. Generated from the 8.0.1",
        "descriptor set and five-layer coverage ledger.",
        "",
        "Trust levels are conservative:",
        "",
        "- **A** independent numeric oracle plus a recorded real execution;",
        "- **A-** independent numeric oracle, execution not recorded;",
        "- **B** recorded real execution (local or srv);",
        "- **C** dedicated test reference plus a compiled route;",
        "- **D** dedicated or smoke test reference only;",
        "- **E** static contract only — not behaviourally verified.",
        "",
        "`UNIT` means a test file references the operator and the 8.0.1 full suite",
        "passed; it does not mean every operator was independently re-inspected.",
        "",
        "## Coverage summary",
        "",
        "| Level | Operators |",
        "| --- | ---: |",
    ]
    for level in ("A", "A-", "B", "C", "D", "E"):
        index.append(f"| {level} | {counts.get(level, 0)} |")
    index += ["", f"Total: **{len(descriptors)}** operators.", "", "## By category", "", "| Category | A/A- | B | C | D | E |", "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for category in sorted(by_category):
        c = by_category[category]
        index.append(
            f"| {category} | {c.get('A', 0) + c.get('A-', 0)} | {c.get('B', 0)} | {c.get('C', 0)} | {c.get('D', 0)} | {c.get('E', 0)} |"
        )
    index += ["", "## All operators", "", "| Operator | Title | Trust | Evidence |", "| --- | --- | --- | --- |"]
    for op, descriptor, row, level in index_rows:
        index.append(
            f"| [`{op}`]({op}.md) | {descriptor.get('title', '')} | {level} | L2 {row.get('l2', '')}; L3 {row.get('l3', '')} |"
        )
    (OUT / "README.md").write_text("\n".join(index) + "\n", encoding="utf-8")
    print(f"generated {len(descriptors)} sheets -> {OUT}")
    print("levels", dict(sorted(counts.items())))


if __name__ == "__main__":
    main()
