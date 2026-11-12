#!/usr/bin/env python3
"""Validate a frozen-artifact release acceptance record.

This is the executable part of L5 in
``docs/verification/five-layer-test-standard.md``. It refuses source-tree
substitutes: the record must name the uploaded bundle, its SHA256, a clean
application install, an environment prepared from the installed library, and an
operator route run from that installed library.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEXCOMMIT = re.compile(r"^[0-9a-f]{7,40}$")


def _require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def _sha(value: object) -> bool:
    return isinstance(value, str) and bool(HEX64.fullmatch(value))


def validate(data: dict, bundle: Path | None = None) -> list[str]:
    errors: list[str] = []

    _require(data.get("schema_version") == 1, "schema_version must be 1", errors)
    _require(isinstance(data.get("library_version"), str) and bool(data["library_version"]),
             "library_version is required", errors)
    _require(isinstance(data.get("commit"), str) and bool(HEXCOMMIT.fullmatch(data["commit"])),
             "commit must be a git hash", errors)
    _require(isinstance(data.get("application"), str) and bool(data["application"]),
             "application version is required", errors)
    _require(isinstance(data.get("os"), str) and bool(data["os"]), "os is required", errors)

    frozen = data.get("bundle")
    _require(isinstance(frozen, dict), "bundle block is required", errors)
    if isinstance(frozen, dict):
        _require(isinstance(frozen.get("asset"), str) and bool(frozen["asset"]),
                 "bundle.asset is required", errors)
        _require(_sha(frozen.get("sha256")), "bundle.sha256 must be 64 hex chars", errors)
        if bundle is not None:
            actual = hashlib.sha256(bundle.read_bytes()).hexdigest()
            _require(frozen.get("sha256") == actual,
                     f"bundle.sha256 does not match {bundle}: {actual}", errors)
            _require(frozen.get("asset") == bundle.name,
                     "bundle.asset must be the frozen file name", errors)

    profile = data.get("profile")
    _require(isinstance(profile, dict) and profile.get("clean") is True,
             "profile.clean must be true", errors)
    if isinstance(profile, dict):
        _require(isinstance(profile.get("root"), str) and bool(profile["root"]),
                 "profile.root is required", errors)

    install = data.get("install")
    _require(isinstance(install, dict), "install block is required", errors)
    if isinstance(install, dict):
        _require(install.get("status") == "PASS", "install.status must be PASS", errors)
        _require(install.get("exit_code") == 0, "install.exit_code must be 0", errors)
        _require(isinstance(install.get("installed_version"), str) and
                 install.get("installed_version") == data.get("library_version"),
                 "install.installed_version must equal library_version", errors)
        _require(isinstance(install.get("source_root"), str) and bool(install["source_root"]),
                 "install.source_root is required", errors)

    env = data.get("environment")
    _require(isinstance(env, dict), "environment block is required", errors)
    if isinstance(env, dict):
        _require(isinstance(env.get("name"), str) and bool(env["name"]),
                 "environment.name is required", errors)
        _require(env.get("status") == "PASS", "environment.status must be PASS", errors)
        _require(_sha(env.get("spec_sha256")),
                 "environment.spec_sha256 must be 64 hex chars", errors)
        _require(isinstance(env.get("interpreter"), str) and bool(env["interpreter"]),
                 "environment.interpreter is required", errors)
        _require(isinstance(env.get("bytes"), int) and env["bytes"] > 0,
                 "environment.bytes must be positive", errors)
        _require(isinstance(env.get("files"), int) and env["files"] > 0,
                 "environment.files must be positive", errors)
        imports = env.get("imports")
        _require(isinstance(imports, list) and bool(imports) and
                 all(isinstance(x, str) and x for x in imports),
                 "environment.imports must be a non-empty list", errors)
        _require(isinstance(env.get("tool_probe"), str) and bool(env["tool_probe"]),
                 "environment.tool_probe is required", errors)

    op = data.get("operator")
    _require(isinstance(op, dict), "operator block is required", errors)
    if isinstance(op, dict):
        _require(isinstance(op.get("id"), str) and bool(op["id"]),
                 "operator.id is required", errors)
        _require(op.get("status") == "PASS", "operator.status must be PASS", errors)
        _require(isinstance(op.get("command"), str) and bool(op["command"]),
                 "operator.command is required", errors)
        outputs = op.get("outputs")
        _require(isinstance(outputs, list) and bool(outputs),
                 "operator.outputs must be non-empty", errors)
        if isinstance(outputs, list):
            for index, item in enumerate(outputs):
                _require(isinstance(item, dict) and _sha(item.get("sha256")),
                         f"operator.outputs[{index}].sha256 must be 64 hex chars", errors)

    layers = data.get("layers")
    _require(isinstance(layers, dict), "layers block is required", errors)
    if isinstance(layers, dict):
        for name in ("L1", "L2", "L3", "L4", "L5"):
            layer = layers.get(name)
            _require(isinstance(layer, dict) and layer.get("status") == "PASS",
                     f"layers.{name}.status must be PASS", errors)

    _require(data.get("release_blocking") == [],
             "release_blocking must be empty", errors)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--bundle", type=Path, default=None,
                        help="frozen .operon-library.zip to hash and compare")
    args = parser.parse_args()

    try:
        data = json.loads(args.evidence.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"FAIL: cannot read evidence: {exc}", file=sys.stderr)
        return 2
    if not isinstance(data, dict):
        print("FAIL: evidence must be a JSON object", file=sys.stderr)
        return 2

    errors = validate(data, args.bundle)
    if errors:
        print("RELEASE ACCEPTANCE FAILED", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"RELEASE ACCEPTANCE PASS: {data['library_version']} "
          f"{data['bundle']['sha256']} on {data['application']} ({data['os']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
