#!/usr/bin/env python3
"""L0 static consistency audit for every library operator and Reader.

Checks per descriptor in the frozen builtin manifest:
  * module parses; declared entry point class exists
  * ``definition`` is a literal dict inside the class
  * descriptor declaration identity re-hashes to declaration_sha
  * literal fields agree with the frozen descriptor
  * parameter JSON agrees with parameters_schema
  * port count equals inputs_arity, contract/output/format declarations exist
  * dims bindings name declared string parameters; logical_type is valid
  * adjacent Markdown hash matches the frozen documentation hash

Legacy shapes (plain string dims, absent protocol_revision, polymorphic
operators) are recorded as warnings instead of failures.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

ROOT = Path(__file__).resolve().parents[2]
SEED = ROOT / "library" / "seed"
LOGICAL = re.compile(r"^[a-z][a-z0-9_.-]{0,79}$")
LEGACY_POLYMORPHIC = {"analyze_contacts", "export_results", "order_axis", "select", "sequence_stats"}
RUNTIME_ONLY = {"code_sha", "declaration_sha", "documentation", "parameters_schema",
                "dependencies", "dependency_imports", "provider", "resources", "entry_point"}


def load_descriptors() -> tuple[list[dict], list[str]]:
    doc = json.loads((SEED / "operon" / "builtin_packages.json").read_text(encoding="utf-8"))
    out: list[dict] = []
    errors: list[str] = []
    seen: dict[str, str] = {}
    for package in doc.get("packages", []):
        for descriptor in package.get("descriptors", []):
            item = dict(descriptor)
            item["_package"] = package.get("name")
            if item.get("id") in seen:
                errors.append(f"duplicate id {item.get('id')} in {seen[item.get('id')]} and {package.get('name')}")
            seen[item.get("id")] = package.get("name")
            out.append(item)
    return out, errors


def find_class(tree: ast.Module, name: str) -> ast.ClassDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    return None


def class_attributes(node: ast.ClassDef) -> dict[str, ast.expr]:
    result: dict[str, ast.expr] = {}
    for stmt in node.body:
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    result[target.id] = stmt.value
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.value is not None:
            result[stmt.target.id] = stmt.value
    return result


def literal(value: ast.expr) -> object:
    return ast.literal_eval(value)


def check_doc(path: Path, declared: dict, errors: list[str], warnings: list[str]) -> None:
    if not declared:
        warnings.append("documentation entry missing")
        return
    doc_path = path.parent / declared.get("path", "")
    if not doc_path.is_file():
        errors.append(f"documentation file missing: {doc_path.name}")
        return
    try:
        from operon_sdk.documentation import canonical_content, sections
    except Exception as exc:  # noqa: BLE001
        errors.append(f"documentation helper unavailable: {exc.__class__.__name__}")
        return
    content = canonical_content(doc_path.read_bytes())
    digest = hashlib.sha256(content).hexdigest()
    if digest != declared.get("sha256"):
        errors.append(f"doc sha mismatch {doc_path.name}: {digest} != {declared.get('sha256')}")
    elif list(sections(content.decode("utf-8"))) != declared.get("sections"):
        errors.append(f"doc section index differs: {doc_path.name}")


def check_format_entry(label: str, index: int, item: object, errors: list[str]) -> None:
    if not isinstance(item, dict):
        errors.append(f"data_formats.{label}[{index}] is not an object")
        return
    logical = item.get("logical_type")
    if not isinstance(logical, str) or not LOGICAL.match(logical):
        errors.append(f"data_formats.{label}[{index}] invalid logical_type {logical!r}")
    reps = item.get("representations")
    if not isinstance(reps, list) or not reps or not all(isinstance(rep, str) for rep in reps):
        errors.append(f"data_formats.{label}[{index}] representations invalid")
    metadata = item.get("metadata", {})
    if not isinstance(metadata, dict):
        errors.append(f"data_formats.{label}[{index}] metadata must be an object")


def audit_one(descriptor: dict) -> dict:
    oid = descriptor.get("id")
    kind = descriptor.get("kind")
    entry = descriptor.get("entry_point") or ""
    errors: list[str] = []
    warnings: list[str] = []
    checks: dict[str, object] = {}
    module_name, _, class_name = entry.partition(":")
    if oid in LEGACY_POLYMORPHIC:
        warnings.append("documented polymorphic legacy operator")
    if not module_name or not class_name:
        return record(descriptor, ["invalid entry_point"], warnings, checks)

    module_path = SEED / (module_name.replace(".", "/") + ".py")
    if not module_path.is_file():
        errors.append(f"module missing: {module_path.relative_to(SEED).as_posix()}")
        return record(descriptor, errors, warnings, checks)
    try:
        tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
    except (SyntaxError, UnicodeDecodeError) as exc:
        errors.append(f"ast parse failed: {exc.__class__.__name__}: {exc}")
        return record(descriptor, errors, warnings, checks)
    checks["ast_parse"] = True

    node = find_class(tree, class_name)
    if node is None:
        errors.append(f"class {class_name} not found")
        return record(descriptor, errors, warnings, checks)
    attrs = class_attributes(node)
    if attrs.get("definition") is None:
        errors.append("class has no literal definition attribute")
        return record(descriptor, errors, warnings, checks)
    try:
        definition = literal(attrs["definition"])
    except (ValueError, TypeError) as exc:
        errors.append(f"definition is not a literal: {exc.__class__.__name__}: {exc}")
        return record(descriptor, errors, warnings, checks)
    if not isinstance(definition, dict):
        errors.append("definition literal is not a dict")
        return record(descriptor, errors, warnings, checks)
    checks["definition_literal"] = True

    try:
        from operon_sdk.declarations import declaration_hash
        expected = declaration_hash(descriptor)
        if expected != descriptor.get("declaration_sha"):
            errors.append(f"descriptor declaration hash mismatch {expected[:12]}")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"declaration rehash failed: {exc.__class__.__name__}: {exc}")

    for key, value in definition.items():
        if key in RUNTIME_ONLY or key not in descriptor:
            continue
        if descriptor.get(key) != value:
            errors.append(f"definition[{key!r}] differs from builtin_packages.json")
    for key in ("id", "kind", "protocol_version"):
        if key not in definition:
            errors.append(f"definition missing {key}")
    if definition.get("protocol_version") != 3:
        errors.append("protocol_version is not 3")
    revision = str(definition.get("protocol_revision", ""))
    if revision and not re.match(r"^3\.[0-9]+$", revision):
        errors.append(f"invalid protocol_revision {revision!r}")
    if not revision:
        warnings.append("protocol_revision absent (pre-3.7 metadata)")
    if definition.get("kind") != kind:
        errors.append(f"kind mismatch {definition.get('kind')} != {kind}")

    contracts = definition.get("contracts") or {}
    inputs = contracts.get("inputs")
    if not isinstance(inputs, list):
        errors.append("contracts.inputs is not a list")
        inputs = []
    if not isinstance(contracts.get("output"), dict):
        errors.append("contracts.output missing")
    arity = definition.get("inputs_arity")
    if arity == "*":
        warnings.append("variadic inputs_arity")
    elif arity is None and kind == "reader":
        if inputs:
            errors.append(f"reader declares {len(inputs)} input contracts without inputs_arity")
    elif arity != len(inputs):
        errors.append(f"inputs_arity {arity} != contracts.inputs {len(inputs)}")
    output_parameter = definition.get("output_parameter")
    if output_parameter is not None and not isinstance(output_parameter, str):
        errors.append("output_parameter must be a string or null")
    elif not output_parameter:
        warnings.append("no output_parameter (streaming, plot or file-output operator)")
    outputs = definition.get("outputs")
    if outputs is None:
        warnings.append("definition.outputs null (file outputs declared through contracts)")
    elif not isinstance(outputs, list) or not all(isinstance(item, str) for item in outputs):
        errors.append("definition.outputs must be a list of strings or null")
    elif not outputs:
        warnings.append("definition.outputs empty")

    formats = definition.get("data_formats") or {}
    fin, fout = formats.get("inputs"), formats.get("outputs")
    if not isinstance(fin, list) or not isinstance(fout, list):
        if revision.startswith("3.7"):
            errors.append("data_formats must contain inputs/outputs lists")
        else:
            warnings.append("data_formats missing (legacy)")
        fin, fout = [], []
    if revision.startswith("3.7") and len(fin) != len(inputs):
        errors.append(f"data_formats.inputs {len(fin)} != contracts.inputs {len(inputs)}")
    if revision.startswith("3.7") and not fout:
        warnings.append("data_formats.outputs empty (pass-through, plot or streaming output)")
    for label, entries in (("input", fin), ("output", fout)):
        for index, item in enumerate(entries):
            check_format_entry(label, index, item, errors)

    schema = descriptor.get("parameters_schema")
    if not isinstance(schema, dict):
        errors.append("descriptor parameters_schema missing")
        schema = {}
    else:
        if schema.get("type") != "object":
            errors.append("parameters_schema type is not object")
        if schema.get("additionalProperties") is not False:
            warnings.append("parameters_schema allows additionalProperties (dynamic parameter operator)")
        props = schema.get("properties")
        if not isinstance(props, dict):
            errors.append("parameters_schema properties must be an object")
            props = {}
    props = (schema.get("properties") or {}) if isinstance(schema, dict) else {}

    params_name = attrs.get("parameters_file")
    if params_name is None:
        params_rel = module_path.stem + ".parameters.json"
        warnings.append(f"parameters_file implicit: {params_rel}")
        if not (module_path.parent / params_rel).is_file():
            errors.append("class has no parameters_file attribute")
            params_rel = None
    else:
        try:
            params_rel = literal(params_name)
        except (ValueError, TypeError):
            params_rel = None
            errors.append("parameters_file is not a literal")
        if isinstance(params_rel, str):
            params_path = module_path.parent / params_rel
            if not params_path.is_file():
                errors.append(f"parameters file missing: {params_rel}")
            else:
                try:
                    params_doc = json.loads(params_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError as exc:
                    errors.append(f"parameters file invalid JSON: {exc}")
                    params_doc = None
                if params_doc is not None and params_doc != schema:
                    errors.append("parameters file schema differs from builtin_packages.json")

    for index, contract in enumerate(inputs):
        if not isinstance(contract, dict):
            errors.append(f"contracts.inputs[{index}] is not an object")
            continue
        dims = contract.get("dims") or []
        if isinstance(dims, dict) and isinstance(dims.get("param"), str):
            if dims["param"] not in props:
                errors.append(f"dims param {dims[param]!r} not declared in parameters_schema")
            else:
                warnings.append(f"contracts.inputs[{index}] uses a single parameter-reference dims spec")
            continue
        if not isinstance(dims, list):
            errors.append(f"contracts.inputs[{index}].dims is not a list or parameter reference")
            continue
        seen_params: set[str] = set()
        for binding in dims:
            if isinstance(binding, str):
                if revision.startswith("3.7"):
                    warnings.append(f"contracts.inputs[{index}] legacy string dim {binding!r}")
                continue
            if not isinstance(binding, dict):
                errors.append(f"contracts.inputs[{index}] dims entry is not an object")
                continue
            param = binding.get("param")
            if not isinstance(param, str) or not param:
                if revision.startswith("3.7"):
                    errors.append(f"contracts.inputs[{index}] dims entry lacks param")
                else:
                    warnings.append(f"contracts.inputs[{index}] dims entry lacks param (legacy)")
                continue
            suffix = binding.get("suffix") or ""
            key = f"{param}{suffix}"
            if key in seen_params:
                errors.append(f"contracts.inputs[{index}] duplicate dims param {key}")
            seen_params.add(key)
            if param not in props:
                errors.append(f"dims param {param!r} not declared in parameters_schema")
                continue
            declared = props[param]
            if declared.get("type") not in ("string", None):
                errors.append(f"dims param {param!r} must be a string parameter")
            default = binding.get("default")
            if default is not None and not isinstance(default, str):
                if isinstance(default, (dict, list)):
                    warnings.append(f"dims param {param!r} uses a dynamic default")
                else:
                    errors.append(f"dims param {param!r} default must be a string or binding")
            if "default" in declared and default is not None and declared["default"] != default:
                warnings.append(f"dims param {param!r} default differs from parameters_schema")

    check_doc(module_path, descriptor.get("documentation") or {}, errors, warnings)
    return record(descriptor, errors, warnings, checks)


def record(descriptor: dict, errors: list[str], warnings: list[str], checks: dict) -> dict:
    return {
        "id": descriptor.get("id"),
        "kind": descriptor.get("kind"),
        "package": descriptor.get("_package"),
        "entry_point": descriptor.get("entry_point"),
        "status": "PASS" if not errors else "FAIL",
        "error_count": len(errors),
        "warning_count": len(warnings),
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(ROOT / "verification" / "operator-audit-7.0.2"))
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    descriptors, manifest_errors = load_descriptors()
    rows = [audit_one(item) for item in descriptors]
    with (out / "l0_static.jsonl").open("w", encoding="utf-8") as handle:
        for item in rows:
            handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
    by_kind = Counter((item["kind"], item["status"]) for item in rows)
    error_counter = Counter(error.split(":")[0] for item in rows for error in item["errors"])
    warning_counter = Counter(warning.split(":")[0] for item in rows for warning in item["warnings"])
    failures = [item["id"] for item in rows if item["status"] != "PASS"]
    summary = {
        "layer": "L0",
        "library_version": json.loads((ROOT / "library" / "release.json").read_text())["version"],
        "counts": {
            "total": len(rows),
            "operators": sum(1 for r in rows if r["kind"] == "operator"),
            "readers": sum(1 for r in rows if r["kind"] == "reader"),
            "failures": len(failures),
        },
        "status": {f"{kind}:{status}": count for (kind, status), count in sorted(by_kind.items())},
        "manifest_errors": manifest_errors,
        "top_errors": error_counter.most_common(30),
        "top_warnings": warning_counter.most_common(20),
        "failures": failures,
    }
    (out / "l0_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if not failures and not manifest_errors else 1


if __name__ == "__main__":
    sys.exit(main())
