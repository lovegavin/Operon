"""Report the dependency union each environment needs for its operators.

The operator library declares an environment per descriptor and a set of
``dependencies`` per descriptor.  ``environments.json`` declares the packages
that are installed when an environment is prepared.  When the two drift apart,
operators fail with ``environment_not_ready`` even though the environment is
"installed".

This helper reads a packaged registry (``registry.json``), groups descriptor
dependencies by ``resources.environment`` and prints the union per
environment, together with the packages listed in ``environments.json`` that
no operator needs.  It never modifies the library; pass ``--json`` to get a
machine readable report.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

_NAME = re.compile(r'^[A-Za-z0-9_.-]+')


def package_name(requirement: str) -> str:
    text = str(requirement).strip()
    match = _NAME.match(text)
    return (match.group(0) if match else text).lower()


def merge(requirements) -> list[str]:
    """Keep one specifier per package, preferring the longest constraint."""
    chosen: dict[str, str] = {}
    for requirement in requirements or []:
        text = str(requirement).strip()
        if not text:
            continue
        name = package_name(text)
        current = chosen.get(name)
        if current is None or len(text) > len(current) or (len(text) == len(current) and text > current):
            chosen[name] = text
    return [chosen[name] for name in sorted(chosen)]


def environment_entries(document: dict) -> dict:
    """Return the environment mapping, unwrapping ``{"environments": {...}}``."""
    if isinstance(document.get("environments"), dict):
        return document["environments"]
    return document


def descriptor_environments(registry: dict) -> dict[str, set[str]]:
    mapping: dict[str, set[str]] = {}
    for entry in registry.get("descriptors") or []:
        resources = entry.get("resources") or {}
        environment = str(resources.get("environment") or "core")
        mapping.setdefault(environment, set()).add(str(entry.get("id") or ""))
    return mapping


def requirements_by_environment(registry: dict) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for entry in registry.get("descriptors") or []:
        resources = entry.get("resources") or {}
        environment = str(resources.get("environment") or "core")
        grouped.setdefault(environment, []).extend(entry.get("dependencies") or [])
    return {name: merge(values) for name, values in sorted(grouped.items())}


def compare(environments: dict, registry: dict) -> list[dict]:
    entries = environment_entries(environments)
    table = requirements_by_environment(registry)
    operators = descriptor_environments(registry)
    rows = []
    for name, entry in sorted(entries.items()):
        if not isinstance(entry, dict):
            continue
        declared = merge(entry.get("requirements") or [])
        needed = table.get(name, [])
        declared_names = {package_name(item) for item in declared}
        needed_names = {package_name(item) for item in needed}
        rows.append({
            "environment": name,
            "operators": len(operators.get(name, ())),
            "declared": declared,
            "needed": needed,
            "missing": [item for item in needed if package_name(item) not in declared_names],
            "unused": [item for item in declared if package_name(item) not in needed_names],
        })
    return rows


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environments", required=True, type=Path)
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    environments = json.loads(args.environments.read_text(encoding="utf-8"))
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    rows = compare(environments, registry)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    for row in rows:
        print(f"{row['environment']}: operators {row['operators']} "
              f"declared {len(row['declared'])} needed {len(row['needed'])}")
        for item in row["missing"]:
            print(f"  missing {item}")
        for item in row["unused"]:
            print(f"  unused  {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())