"""Discover seed declarations and assemble one source set per provider package."""

from __future__ import annotations

import ast
import json
import re
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from operon_sdk.declarations import compile_declaration, declaration_hash, source_declarations
from operon_sdk.protocol import Descriptor

from . import identity

PLACEHOLDER_IDENTITY = "0" * 64
TREES = (("steps", "src/task/step/steps"), ("readers", "src/reader/readers"))
FALLBACK_PROVIDER = {"steps": "operon-core", "readers": "operon-readers"}
CANONICAL_MODULE = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass(frozen=True)
class Declaration:
    tree: str
    path: Path
    module: str
    class_name: str
    parameters_file: str
    provider: str
    descriptor: dict[str, Any]


@dataclass
class PackageCode:
    name: str
    module: str
    files: dict[str, bytes]
    descriptors: list[dict[str, Any]]
    code_sha: str


def canonical_module(name: str) -> str:
    module = name.replace("-", "_").replace(".", "_").lower()
    if not CANONICAL_MODULE.match(module):
        raise ValueError(f"{name}: provider name does not map to a Python module ({module!r})")
    return module


def known_providers(seed_root: Path) -> set[str]:
    path = Path(seed_root) / "operon" / "builtin_packages.json"
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"{path}: builtin package manifest is missing") from error
    packages = document.get("packages")
    if not isinstance(packages, list):
        raise ValueError(f"{path}: expected a 'packages' list")
    names = {package.get("name") for package in packages if isinstance(package, dict)}
    if None in names or not all(isinstance(name, str) and name for name in names):
        raise ValueError(f"{path}: every package needs a non-empty name")
    return names


def discover(seed_root: Path) -> list[Declaration]:
    seed_root = Path(seed_root).resolve()
    providers = known_providers(seed_root)
    found: list[Declaration] = []
    for tree, relative in TREES:
        tree_root = seed_root / relative
        if not tree_root.is_dir():
            raise ValueError(f"{tree_root}: source tree is missing")
        module_prefix = relative.replace("/", ".")
        for path in sorted(tree_root.glob("[!_]*.py")):
            module = f"{module_prefix}.{path.stem}"
            for raw in source_declarations(path, module):
                provider = raw.get("provider") or FALLBACK_PROVIDER[tree]
                if provider not in providers:
                    raise ValueError(
                        f"{path}: provider {provider!r} is not declared in "
                        f"{seed_root / 'operon' / 'builtin_packages.json'}"
                    )
                class_name = str(raw["entry_point"]).split(":", 1)[1]
                compiled = compile_declaration(raw, seed_root, _code_identity=PLACEHOLDER_IDENTITY)
                found.append(
                    Declaration(
                        tree=tree,
                        path=path,
                        module=module,
                        class_name=class_name,
                        parameters_file=_parameters_file(path, class_name),
                        provider=provider,
                        descriptor=compiled,
                    )
                )
    _check_identifiers(found)
    return found


def _parameters_file(path: Path, class_name: str) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != class_name:
            continue
        for statement in node.body:
            value = None
            targets: list[ast.expr] = []
            if isinstance(statement, ast.Assign):
                value, targets = statement.value, statement.targets
            elif isinstance(statement, ast.AnnAssign) and statement.value is not None:
                value, targets = statement.value, [statement.target]
            if any(isinstance(target, ast.Name) and target.id == "parameters_file" for target in targets):
                return str(ast.literal_eval(value))
    return f"{path.stem}.parameters.json"


def _check_identifiers(declarations: list[Declaration]) -> None:
    seen: dict[str, str] = {}
    for declaration in declarations:
        identifier = declaration.descriptor["id"]
        if identifier in seen:
            raise ValueError(f"descriptor {identifier!r} is declared twice ({seen[identifier]} and {declaration.path})")
        seen[identifier] = str(declaration.path)


def _support_modules(seed_root: Path, declarations: list[Declaration]) -> list[tuple[str, Path, Path]]:
    support: list[tuple[str, Path, Path]] = []
    for tree, relative in TREES:
        tree_root = seed_root / relative
        declared = {declaration.path for declaration in declarations if declaration.tree == tree}
        for path in sorted(tree_root.glob("*.py")):
            if path in declared or path.name.startswith("_") or path.stem == "__init__":
                continue
            support.append((tree, tree_root, path))
    return support


def _helpers(seed_root: Path) -> list[tuple[str, Path, Path]]:
    helpers: list[tuple[str, Path, Path]] = []
    for tree, relative in TREES:
        tree_root = seed_root / relative
        for path in sorted(tree_root.rglob("_*.py")):
            if "__pycache__" in path.parts:
                continue
            helpers.append((tree, tree_root, path))
    return helpers


def _rewrite(path: Path, module: str) -> bytes:
    text = path.read_text(encoding="utf-8")
    for tree, relative in TREES:
        text = text.replace(relative.replace("/", "."), f"{module}.{tree}")
    return text.encode("utf-8")


def _relative_reference(path: Path, reference: str, tree_root: Path, *, suffix: str | None = None) -> str:
    posix = PurePosixPath(reference)
    if posix.is_absolute() or not posix.parts or ".." in posix.parts:
        raise ValueError(f"{path}: unsupported relative reference {reference!r}")
    if suffix is not None and posix.suffix != suffix:
        raise ValueError(f"{path}: expected a {suffix} reference, got {reference!r}")
    resolved = (path.parent / reference).resolve()
    try:
        relative = resolved.relative_to(tree_root.resolve())
    except ValueError as error:
        raise ValueError(f"{path}: reference {reference!r} escapes {tree_root}") from error
    return relative.as_posix()


def build_packages(seed_root: Path) -> list[PackageCode]:
    seed_root = Path(seed_root).resolve()
    declarations = discover(seed_root)
    groups: dict[str, list[Declaration]] = {}
    for declaration in declarations:
        groups.setdefault(declaration.provider, []).append(declaration)

    helpers = _helpers(seed_root)
    support = _support_modules(seed_root, declarations)

    packages: list[PackageCode] = []
    for name in sorted(groups):
        members = sorted(groups[name], key=lambda item: (item.tree, item.path.name, item.class_name))
        module = canonical_module(name)
        tree_roots = {tree: seed_root / relative for tree, relative in TREES}
        files: dict[str, bytes] = {}

        def add(destination: str, data: bytes, source: Path) -> None:
            previous = files.get(destination)
            if previous is not None and previous != data:
                raise ValueError(f"{source}: conflicting content for wheel path {destination!r}")
            files[destination] = data

        for declaration in members:
            tree_root = tree_roots[declaration.tree]
            subtree = f"{module}/{declaration.tree}"
            add(f"{subtree}/{declaration.path.name}", _rewrite(declaration.path, module), declaration.path)
            descriptor = declaration.descriptor

            parameters = _relative_reference(
                declaration.path, declaration.parameters_file, tree_root, suffix=".json"
            )
            add(f"{subtree}/{parameters}", (declaration.path.parent / parameters).read_bytes(), declaration.path)

            documentation = descriptor.get("documentation")
            if isinstance(documentation, dict) and documentation.get("path"):
                document = _relative_reference(
                    declaration.path, str(documentation["path"]), tree_root, suffix=".md"
                )
                add(
                    f"{subtree}/{document}",
                    (declaration.path.parent / document).read_bytes(),
                    declaration.path,
                )

            localization = descriptor.get("localization")
            if isinstance(localization, dict) and localization.get("path"):
                translation = _relative_reference(
                    declaration.path, str(localization["path"]), tree_root, suffix=".json"
                )
                add(
                    f"{subtree}/{translation}",
                    (declaration.path.parent / translation).read_bytes(),
                    declaration.path,
                )

            icon = descriptor.get("icon")
            if descriptor.get("icon_image") and isinstance(icon, str):
                asset = _relative_reference(declaration.path, icon, tree_root)
                add(f"{subtree}/{asset}", (declaration.path.parent / asset).read_bytes(), declaration.path)

        for tree, tree_root, path in helpers:
            relative = path.relative_to(tree_root).as_posix()
            add(f"{module}/{tree}/{relative}", _rewrite(path, module), path)
        for tree, tree_root, path in support:
            add(f"{module}/{tree}/{path.name}", _rewrite(path, module), path)

        files[f"{module}/__init__.py"] = f'"""Operon library code for {name}."""\n'.encode("utf-8")

        code_sha = identity.code_identity(files)
        descriptors = [_finalize(member, module, code_sha) for member in members]
        packages.append(
            PackageCode(
                name=name,
                module=module,
                files=files,
                descriptors=descriptors,
                code_sha=code_sha,
            )
        )
    return packages


def _finalize(declaration: Declaration, module: str, code_sha: str) -> dict[str, Any]:
    value = deepcopy(declaration.descriptor)
    value.pop("load_entry_point", None)
    value.pop("load_code_sha", None)
    value["entry_point"] = f"{module}.{declaration.tree}.{declaration.path.stem}:{declaration.class_name}"
    value["code_sha"] = code_sha
    value["declaration_sha"] = declaration_hash(value)
    Descriptor.model_validate(value)
    return value

