"""Assemble the universal library bundle from a seed tree."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from . import descriptors, manifest, wheel
from .identity import file_sha256


@dataclass
class BuildResult:
    path: Path
    document: dict
    packages: int
    descriptors: int


def build_library(
    source: Path,
    output: Path,
    version: str = "0.0.0",
    minimum_application: str = "5.0.0",
    library_name: str = "main",
) -> BuildResult:
    source = Path(source).resolve()
    if not (source / "operon" / "builtin_packages.json").is_file():
        raise ValueError(f"{source}: not a library seed (operon/builtin_packages.json is missing)")
    for label, value in (("version", version), ("minimum application", minimum_application)):
        if not manifest.VERSION.match(value):
            raise ValueError(f"{label} must look like 1.2.3, got {value!r}")

    package_codes = descriptors.build_packages(source)
    if not package_codes:
        raise ValueError(f"{source}: no declarations found")

    modules: dict[str, str] = {}
    wheels: dict[str, bytes] = {}
    records: list[dict] = []
    flat: list[dict] = []
    for package in package_codes:
        previous = modules.get(package.module)
        if previous is not None:
            raise ValueError(f"providers {previous!r} and {package.name!r} share module {package.module!r}")
        modules[package.module] = package.name
        filename = wheel.wheel_filename(package.name, version)
        data = wheel.build_wheel(
            package.name,
            version,
            package.files,
            code_sha=package.code_sha,
            descriptors=package.descriptors,
        )
        wheels[filename] = data
        records.append(
            manifest.package_record(
                name=package.name,
                version=version,
                wheel=f"wheels/{filename}",
                wheel_sha256=file_sha256(data),
                code_sha=package.code_sha,
                descriptors=package.descriptors,
            )
        )
        flat.extend(package.descriptors)

    flat.sort(key=lambda descriptor: (descriptor["kind"], descriptor["id"]))
    counts = Counter(descriptor["kind"] for descriptor in flat)
    document = manifest.library_document(
        library_name=library_name,
        version=version,
        minimum_application=minimum_application,
        packages=records,
        descriptor_count=len(flat),
        operator_count=counts.get("operator", 0),
        reader_count=counts.get("reader", 0),
    )
    environments = (source / "operon" / "environments.json").read_bytes()
    entries = manifest.bundle_entries(
        document=document,
        descriptors=flat,
        environments=environments,
        readme_text=manifest.readme(document, document["packages"]),
        wheels=wheels,
    )
    path = manifest.write_bundle(entries, Path(output) / f"operon-library-{library_name}-v{version}.operon-library.zip")
    return BuildResult(path=path, document=document, packages=len(records), descriptors=len(flat))
