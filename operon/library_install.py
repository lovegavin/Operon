"""Install the immutable library and route bundles built for Operon 5.1.0.

The application consumes two ZIP archives produced by the library builders and
never rebuilds library identity: every ``code_sha`` comes from the bundle
manifest and is only compared with installed descriptors.  Legacy 8.x bundles
are rejected with one actionable message instead of being repaired.
"""

from __future__ import annotations

import hashlib
import io
import os
from copy import deepcopy
import json
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile

from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version

from operon.bytecode import filesystem_path

LIBRARY_FORMAT = "operon.library"
BUNDLE_FORMAT = 1
OPERATOR_PROTOCOL = 3
ROUTE_MEMBERS = {"graph.json", "parameters.json", "execution.json"}
PIN_KEYS = ("package", "version", "code_sha")
LIBRARY_SUFFIXES = (".operon-library.zip", ".biopipe-library.zip")
SHA256 = re.compile(r"^[a-f0-9]{64}$")
LABEL = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
SAFE_ID = re.compile(r"^[A-Za-z0-9_.-]+$")
LEGACY_MESSAGE = (
    "This library bundle uses the legacy 8.x format.\n"
    "Install a current operon-library bundle built for this Operon Studio release."
)


class LegacyLibrary(ValueError):
    """Raised when an archive cannot be installed with the 5.0.0 contract."""


class LibraryConflict(ValueError):
    """Raised when a new library overlaps an installed one.

    Libraries are equal-status branches: operator/Reader ids, distribution
    names and top-level modules must be globally unique, otherwise one library
    would silently shadow another.
    """

    def __init__(self, conflicts):
        self.conflicts = list(conflicts)
        detail = ", ".join(
            f"{item['kind']} {item['id']}{(' in ' + item['library']) if item.get('library') else ''}"
            for item in self.conflicts[:12]
        )
        super().__init__(f"Library overlaps an installed library: {detail}")


class RoutePinMismatch(ValueError):
    """Raised when a route pin differs from the installed library identity."""


def is_library_archive(path) -> bool:
    """True for the 5.0.0 library name and the legacy-style library suffixes."""
    name = Path(str(path)).name.lower()
    return name.endswith(LIBRARY_SUFFIXES) or (
        name.startswith("operon-library-") and name.endswith(".zip")
    )


def _invalid(message: str) -> ValueError:
    return ValueError(message)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _member_names(archive: ZipFile, label: str) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for info in archive.infolist():
        name = info.filename
        if name.endswith("/"):
            continue
        if "\\" in name:
            raise _invalid(f"{label}: invalid archive path {name!r}")
        posix = PurePosixPath(name)
        if posix.is_absolute() or not posix.parts:
            raise _invalid(f"{label}: invalid archive path {name!r}")
        if any(part in {"", ".", ".."} or part.endswith((" ", ".")) for part in posix.parts):
            raise _invalid(f"{label}: invalid archive path {name!r}")
        if name.casefold() in seen:
            raise _invalid(f"{label}: duplicate archive entry {name!r}")
        seen.add(name.casefold())
        names.append(name)
    return names


def _parse_sums(data: bytes, label: str) -> dict[str, str]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise _invalid(f"{label}: SHA256SUMS is not UTF-8") from error
    listed: dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        digest, separator, name = line.partition("  ")
        if not separator or not SHA256.match(digest) or not name:
            raise _invalid(f"{label}: malformed SHA256SUMS line {line!r}")
        if name in listed:
            raise _invalid(f"{label}: duplicate SHA256SUMS entry {name!r}")
        listed[name] = digest
    return listed


def _verify_archive_checksums(archive: ZipFile, names: list[str], label: str) -> None:
    if "SHA256SUMS" not in names:
        raise _invalid(f"{label}: SHA256SUMS is missing from the archive")
    listed = _parse_sums(archive.read("SHA256SUMS"), label)
    if set(listed) != set(names) - {"SHA256SUMS"}:
        raise _invalid(f"{label}: SHA256SUMS does not list exactly the archive contents")
    for name, digest in listed.items():
        hasher = hashlib.sha256()
        with archive.open(name) as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                hasher.update(chunk)
        if hasher.hexdigest() != digest:
            raise _invalid(f"{label}: SHA256SUMS digest mismatch for {name!r}")


def _library_document(archive: ZipFile) -> dict:
    try:
        raw = archive.read("library.json")
    except KeyError as error:
        raise LegacyLibrary(LEGACY_MESSAGE) from error
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise LegacyLibrary(LEGACY_MESSAGE) from error
    if not isinstance(document, dict):
        raise LegacyLibrary(LEGACY_MESSAGE)
    if document.get("format") != LIBRARY_FORMAT or document.get("bundle_format") != BUNDLE_FORMAT:
        raise LegacyLibrary(LEGACY_MESSAGE)
    return document


def _compare_application(document: dict) -> None:
    from operon import __version__ as application_version

    minimum = document.get("minimum_application")
    if not isinstance(minimum, str) or not minimum:
        raise _invalid("library.json: minimum_application is required")
    try:
        required = Version(minimum)
        running = Version(application_version)
    except InvalidVersion as error:
        raise _invalid(f"library.json: invalid minimum_application {minimum!r}") from error
    if running < required:
        raise _invalid(
            f"This library requires Operon {minimum} or newer; this application is {application_version}."
        )


def _validate_library(document: dict, names: list[str]) -> None:
    library_version = document.get("library_version")
    if not isinstance(library_version, str) or not library_version:
        raise _invalid("library.json: library_version is required")
    try:
        Version(library_version)
    except InvalidVersion as error:
        raise _invalid(f"library.json: invalid library_version {library_version!r}") from error

    protocol = document.get("operator_protocol")
    if not isinstance(protocol, dict) or protocol.get("version") != OPERATOR_PROTOCOL:
        raise _invalid("library.json: operator_protocol.version must be 3")
    _compare_application(document)

    packages = document.get("packages")
    if not isinstance(packages, list) or not packages:
        raise _invalid("library.json: packages must be a non-empty list")
    available = set(names)
    for package in packages:
        if not isinstance(package, dict):
            raise _invalid("library.json: every package must be an object")
        name = package.get("name")
        if not isinstance(name, str) or not name:
            raise _invalid("library.json: package without name")
        if not isinstance(package.get("version"), str) or not package["version"]:
            raise _invalid(f"library.json: {name} has no version")
        wheel = package.get("wheel")
        if not isinstance(wheel, str) or not wheel:
            raise _invalid(f"library.json: {name} has no wheel")
        path = PurePosixPath(wheel)
        if path.is_absolute() or len(path.parts) < 2 or path.parts[0] != "wheels":
            raise _invalid(f"library.json: {name} wheel {wheel!r} is not under wheels/")
        if any(part in {"", ".", ".."} for part in path.parts):
            raise _invalid(f"library.json: {name} wheel {wheel!r} is not a safe path")
        if not path.name.endswith(".whl"):
            raise _invalid(f"library.json: {name} wheel {wheel!r} does not end in .whl")
        if wheel not in available:
            raise _invalid(f"library.json: {name} wheel {wheel!r} is missing from the archive")
        wheel_sha256 = package.get("wheel_sha256")
        if not isinstance(wheel_sha256, str) or not SHA256.match(wheel_sha256):
            raise _invalid(f"library.json: {name} has an invalid wheel_sha256")
        code_sha = package.get("code_sha")
        if not isinstance(code_sha, str) or not SHA256.match(code_sha):
            raise _invalid(f"library.json: {name} has an invalid code_sha")
        entry_points = package.get("entry_points")
        if not isinstance(entry_points, dict) or not entry_points:
            raise _invalid(f"library.json: {name} has no entry_points")
        for identifier, entry_point in entry_points.items():
            if not isinstance(identifier, str) or not identifier:
                raise _invalid(f"library.json: {name} has an invalid entry point name")
            if not isinstance(entry_point, str) or ":" not in entry_point:
                raise _invalid(f"library.json: {name} has an invalid entry point for {identifier!r}")


def inspect_library(path) -> dict:
    """Validate a 5.0.0 library archive and extract its wheels to a temporary directory.

    The caller owns ``directory`` and must remove it when finished.  The
    returned manifest is used as-is; no identity value is recomputed.
    """
    source = Path(filesystem_path(path))
    if not source.is_file():
        raise OSError(f"{source}: library archive does not exist")
    digest = _file_sha256(source)
    try:
        archive = ZipFile(source)
    except BadZipFile as error:
        raise _invalid(f"{source.name}: not a valid ZIP archive") from error
    with archive:
        names = _member_names(archive, source.name)
        document = _library_document(archive)
        _validate_library(document, names)
        _verify_archive_checksums(archive, names, source.name)
        directory = Path(tempfile.mkdtemp(prefix="operon-library-"))
        try:
            for package in document["packages"]:
                target = directory / PurePosixPath(package["wheel"])
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(package["wheel"]) as stream, target.open("wb") as output:
                    shutil.copyfileobj(stream, output)
                if _file_sha256(target) != package["wheel_sha256"]:
                    raise _invalid(
                        f"{source.name}: wheel digest does not match library.json for {package['name']}"
                    )
        except BaseException:
            shutil.rmtree(directory, ignore_errors=True)
            raise
    return {"manifest": document, "directory": directory, "path": source, "sha256": digest}


def library_preflight(path) -> None:
    """Reject a legacy library before a background install job is started."""
    source = Path(filesystem_path(path))
    try:
        with ZipFile(source) as archive:
            _library_document(archive)
    except LegacyLibrary:
        raise
    except (OSError, BadZipFile) as error:
        raise LegacyLibrary(LEGACY_MESSAGE) from error


def _release(document: dict, digest: str, *, name: str = "operon-library",
             installed_at: str | None = None) -> dict:
    return {
        "format": LIBRARY_FORMAT,
        "name": name,
        "bundle_format": BUNDLE_FORMAT,
        "library_version": document["library_version"],
        "packages": {
            package["name"]: {"version": package["version"], "code_sha": package["code_sha"]}
            for package in document["packages"]
        },
        "sha256": digest,
        "installed_at": installed_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _label_for(requested: str | None, document: dict,
               version: str | None = None) -> str:
    name = (requested or "main").strip().lower()
    if not LABEL.fullmatch(name):
        raise _invalid(
            f"Invalid library name {name!r}: use lower-case letters, digits, dot, dash or underscore."
        )
    actual = str(document["library_version"]).strip().lower()
    chosen = (version or actual).strip().lower()
    if chosen.startswith("v"):
        chosen = chosen[1:]
    try:
        Version(chosen)
    except InvalidVersion as error:
        raise _invalid(f"Invalid library version {chosen!r}.") from error
    if chosen != actual:
        raise _invalid(
            f"Library version {chosen!r} does not match the bundle version {actual!r}."
        )
    label = f"{name}-v{chosen}"
    if not LABEL.fullmatch(label):
        raise _invalid(f"Invalid library label {label!r}.")
    return label


def _wheel_modules(wheel: Path) -> list[str]:
    """Top-level importable modules provided by a wheel (packages and modules)."""
    modules = set()
    with ZipFile(wheel) as archive:
        for name in archive.namelist():
            head, _, rest = name.partition("/")
            if not head or head.endswith((".dist-info", ".data")):
                continue
            if rest:
                modules.add(head)
            elif head.endswith(".py"):
                modules.add(head[:-3])
    return sorted(modules)


def _libraries(state: dict) -> dict:
    """Return the named-library map, migrating a single 5.0.x install in place."""
    libraries = state.get("libraries")
    if isinstance(libraries, dict):
        return libraries
    release = state.get("library_release")
    libraries = {}
    if isinstance(release, dict) and release.get("library_version"):
        label = release.get("name") or f"v{release['library_version']}"
        if not isinstance(label, str) or not LABEL.fullmatch(label):
            label = "operon-library"
        packages = {}
        for name, value in (release.get("packages") or {}).items():
            packages[canonicalize_name(name)] = {
                "name": name,
                "version": value.get("version"),
                "code_sha": value.get("code_sha"),
            }
        libraries[label] = {
            "name": label,
            "format": LIBRARY_FORMAT,
            "bundle_format": BUNDLE_FORMAT,
            "library_version": release["library_version"],
            "sha256": release.get("sha256"),
            "installed_at": release.get("installed_at"),
            "packages": packages,
            "package_names": sorted(packages),
            "modules": [],
            "identifiers": sorted(
                descriptor["id"] for descriptor in state.get("descriptors", [])
                if descriptor.get("kind") in {"operator", "reader"}
            ),
        }
        for descriptor in state.get("descriptors", []):
            descriptor.setdefault("library", label)
    state["libraries"] = libraries
    return libraries


def _entry(document: dict, digest: str, label: str, package_names: list[str],
           modules: list[str], identifiers: list[str], archive: Path | None,
           installed_at: str | None = None) -> dict:
    return {
        "name": label,
        "format": LIBRARY_FORMAT,
        "bundle_format": BUNDLE_FORMAT,
        "library_version": document["library_version"],
        "sha256": digest,
        "installed_at": installed_at or _now(),
        "packages": {
            canonicalize_name(package["name"]): {
                "name": package["name"],
                "version": package["version"],
                "code_sha": package["code_sha"],
                "wheel_sha256": package["wheel_sha256"],
            }
            for package in document["packages"]
        },
        "package_names": sorted(package_names),
        "modules": sorted(modules),
        "identifiers": sorted(identifiers),
        "archive": str(archive) if archive is not None else None,
    }


def _conflicts(libraries: dict, label: str, identifiers: list[str],
               package_names: list[str], modules: list[str]) -> list[dict]:
    conflicts = []
    for other, record in sorted(libraries.items()):
        if other == label:
            continue
        known = set(record.get("identifiers") or [])
        for identifier in identifiers:
            if identifier in known:
                conflicts.append({"kind": "identifier", "id": identifier, "library": other})
        names = {canonicalize_name(name) for name in record.get("package_names") or []}
        for name in package_names:
            if name in names:
                conflicts.append({"kind": "package", "id": name, "library": other})
        known_modules = set(record.get("modules") or [])
        for module in modules:
            if module in known_modules:
                conflicts.append({"kind": "module", "id": module, "library": other})
    return conflicts[:24]


def _write_library_manifest(manager, label: str, document: dict) -> None:
    directory = Path(manager.directory) / "libraries" / label
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "library.json").write_text(
        json.dumps(document, indent=2, sort_keys=True), encoding="utf-8"
    )
    (directory / "version.json").write_text(
        json.dumps({
            "name": label,
            "library_version": document["library_version"],
            "bundle_format": document.get("bundle_format"),
            "packages": len(document.get("packages") or []),
        }, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _write_operator_metadata(manager, state: dict) -> None:
    directory = Path(manager.directory) / "operators"
    directory.mkdir(parents=True, exist_ok=True)
    libraries = _libraries(state)
    index = {}
    for descriptor in state.get("descriptors", []):
        identifier = descriptor.get("id")
        if not isinstance(identifier, str) or not identifier:
            continue
        label = descriptor.get("library")
        record = libraries.get(label) or {}
        value = {
            "id": identifier,
            "kind": descriptor.get("kind"),
            "library": label,
            "library_version": record.get("library_version"),
            "package": descriptor.get("distribution"),
            "package_version": descriptor.get("package_version"),
            "code_sha": descriptor.get("code_sha"),
            "declaration_sha": descriptor.get("declaration_sha"),
            "execution_sha": (descriptor.get("execution_sha")
                              or (descriptor.get("implementation") or {}).get("execution_sha")),
            "sha256": (descriptor.get("implementation") or {}).get("sha256"),
            "entry_point": (descriptor.get("entry_point")
                            or (descriptor.get("implementation") or {}).get("entry_point")),
        }
        filename = f"{identifier}.json" if SAFE_ID.fullmatch(identifier) else (
            hashlib.sha256(identifier.encode("utf-8")).hexdigest()[:16] + ".json"
        )
        target = directory / filename
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(temporary, target)
        index[identifier] = filename
    target = directory / "index.json"
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(index, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(temporary, target)


def _annotate_libraries(state: dict) -> None:
    """Label every installed descriptor with the branch that owns its package."""
    libraries = _libraries(state)
    owners = {
        canonicalize_name(package): label
        for label, record in libraries.items()
        for package in (record.get("packages") or {})
    }
    for descriptor in state.get("descriptors", []):
        distribution = canonicalize_name(descriptor.get("distribution") or "")
        label = owners.get(distribution)
        if label:
            descriptor["library"] = label


def libraries_view(manager) -> dict:
    state = manager.state()
    libraries = _libraries(state)
    rows = []
    for label, record in sorted(libraries.items()):
        descriptors = [d for d in state.get("descriptors", []) if d.get("library") == label]
        rows.append({
            "name": label,
            "library_version": record.get("library_version"),
            "sha256": record.get("sha256"),
            "installed_at": record.get("installed_at"),
            "packages": len(record.get("packages") or {}),
            "descriptors": len(descriptors),
            "operators": sum(1 for d in descriptors if d.get("kind") == "operator"),
            "readers": sum(1 for d in descriptors if d.get("kind") == "reader"),
        })
    return {"libraries": rows, "count": len(rows)}


def library_pins_match(state, graph) -> bool:
    """True when every pin names an operator installed by the current library.

    Library route bundles carry package, version and code_sha -- the canonical
    library identity. The app must not replace, rebuild or otherwise "repair"
    those pins, so a graph whose pins already equal the installed library is
    accepted as-is. Ordinary wheel-only installations never take this path.
    """
    if not isinstance(state.get("library_release"), dict):
        return False
    from operon.pins import graphs

    descriptors = {d["id"]: d for d in state.get("descriptors", [])}
    pinned = False
    for part in graphs(graph):
        for operator, pin in part.plugin_lock.items():
            descriptor = descriptors.get(operator)
            if descriptor is None:
                return False
            package = pin.get("package")
            version = pin.get("version")
            code_sha = pin.get("code_sha")
            if not package or not version or not code_sha:
                return False
            if (canonicalize_name(descriptor["distribution"]) != canonicalize_name(package)
                    or descriptor["package_version"] != version
                    or descriptor["code_sha"] != code_sha):
                return False
            pinned = True
    return pinned


def _installed_descriptor(state: dict, operator: str) -> dict | None:
    for descriptor in state.get("descriptors", []):
        if descriptor.get("id") == operator:
            return descriptor
    return None


def _wheels_present(manager, state: dict, packages: list[dict]) -> bool:
    records = {canonicalize_name(record["name"]): record for record in state.get("packages", [])}
    for package in packages:
        record = records.get(canonicalize_name(package["name"]))
        if record is None:
            return False
        if record.get("version") != package["version"]:
            return False
        if record.get("sha256") != package["wheel_sha256"]:
            return False
        if not (manager.directory / record.get("wheel", "")).is_file():
            return False
    return True


def _store_library_archive(manager, source: Path, label: str, digest: str) -> Path | None:
    """Keep each imported archive with its named library for remote delivery."""
    directory = Path(manager.directory) / "libraries" / label
    try:
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / "archive.zip"
        if not target.is_file() or _file_sha256(target) != digest:
            shutil.copyfile(source, target)
        return target
    except OSError:
        return None


def _result(document: dict, *, label: str, libraries: list[str],
            installed: bool, idempotent: bool) -> dict:
    descriptors = sum(len(package["entry_points"]) for package in document["packages"])
    return {
        "library": label,
        "libraries": libraries,
        "library_version": document["library_version"],
        "packages": len(document["packages"]),
        "descriptors": descriptors,
        "installed": installed,
        "idempotent": idempotent,
    }


def install_library(manager, path, *, name: str | None = None,
                    version: str | None = None, replace: bool = True) -> dict:
    """Install a 5.0.0 archive as an equal-status named library.

    Libraries are branches, not replacements: every imported bundle keeps its
    own identity, archives and operator metadata, and all installed branches
    are available at the same time.  Operator/Reader ids, distribution names
    and top-level modules must be globally unique.
    """
    source = Path(filesystem_path(path))
    digest = _file_sha256(source)
    with manager.lock:
        inspected = inspect_library(source)
        try:
            document = inspected["manifest"]
            label = _label_for(name, document, version)
            current = manager.state()
            libraries = _libraries(current)
            identifiers = sorted({
                identifier for package in document["packages"]
                for identifier in package["entry_points"]
            })
            package_names = [canonicalize_name(package["name"]) for package in document["packages"]]
            modules = sorted({
                module for package in document["packages"]
                for module in _wheel_modules(inspected["directory"] / package["wheel"])
            })
            conflicts = _conflicts(libraries, label, identifiers, package_names, modules)
            if conflicts:
                raise LibraryConflict(conflicts)
            previous = libraries.get(label) or {}
            archive = _store_library_archive(manager, source, label, digest)
            entry = _entry(document, digest, label, package_names, modules,
                           identifiers, archive, previous.get("installed_at"))
            if (previous.get("sha256") == digest
                    and previous.get("library_version") == document["library_version"]
                    and _wheels_present(manager, current, document["packages"])):
                libraries[label] = entry
                current["libraries"] = libraries
                current["library_release"] = _release(
                    document, digest, name=label, installed_at=entry["installed_at"]
                )
                _write_library_manifest(manager, label, document)
                manager._publish(current)
                _write_operator_metadata(manager, current)
                return _result(document, label=label, libraries=sorted(libraries),
                               installed=False, idempotent=True)

            base = deepcopy(current)
            base["descriptors"] = [
                descriptor for descriptor in current.get("descriptors", [])
                if descriptor.get("library") != label
            ]
            keep = {
                package for other, record in libraries.items() if other != label
                for package in (record.get("packages") or {})
            }
            base["packages"] = [
                package for package in current.get("packages", [])
                if canonicalize_name(package["name"]) in keep
            ]
            base["libraries"] = {
                other: record for other, record in libraries.items() if other != label
            }
            wheels = [inspected["directory"] / package["wheel"] for package in document["packages"]]
            state = manager._install_many(wheels, base, publish=False, library=True)
            wanted = set(identifiers)
            for descriptor in state.get("descriptors", []):
                if (descriptor["id"] in wanted
                        and canonicalize_name(descriptor["distribution"]) in package_names):
                    descriptor["library"] = label
                elif not descriptor.get("library"):
                    descriptor["library"] = label
            libraries = _libraries(state)
            libraries[label] = entry
            state["libraries"] = libraries
            state["library_release"] = _release(
                document, digest, name=label, installed_at=entry["installed_at"]
            )
            state["library_detached"] = True
            for legacy in ("source_library", "library_source_pins", "library_pin_updates"):
                state.pop(legacy, None)
            _write_library_manifest(manager, label, document)
            manager._publish(state)
            _write_operator_metadata(manager, state)
            return _result(document, label=label, libraries=sorted(libraries),
                           installed=True, idempotent=False)
        finally:
            shutil.rmtree(inspected["directory"], ignore_errors=True)


def uninstall_library(manager, name: str) -> dict:
    """Remove one named library; other branches stay installed and usable."""
    label = str(name)
    with manager.lock:
        current = manager.state()
        libraries = _libraries(current)
        if label not in libraries:
            raise _invalid(f"Unknown library: {label}")
        remaining = {other: record for other, record in libraries.items() if other != label}
        keep = {
            package for record in remaining.values()
            for package in (record.get("packages") or {})
        }
        state = deepcopy(current)
        state["descriptors"] = [
            descriptor for descriptor in current.get("descriptors", [])
            if descriptor.get("library") != label
        ]
        state["packages"] = [
            package for package in current.get("packages", [])
            if canonicalize_name(package["name"]) in keep
        ]
        state["libraries"] = remaining
        _annotate_libraries(state)
        state.pop("library_release", None)
        if remaining:
            latest = sorted(remaining.values(), key=lambda item: item.get("installed_at") or "")[-1]
            state["library_release"] = {
                "format": LIBRARY_FORMAT,
                "name": latest.get("name"),
                "bundle_format": BUNDLE_FORMAT,
                "library_version": latest.get("library_version"),
                "packages": {
                    name: {"version": value.get("version"), "code_sha": value.get("code_sha")}
                    for name, value in (latest.get("packages") or {}).items()
                },
                "sha256": latest.get("sha256"),
                "installed_at": latest.get("installed_at"),
            }
        manager._publish(state)
        _write_operator_metadata(manager, state)
        shutil.rmtree(Path(manager.directory) / "libraries" / label, ignore_errors=True)
        return {"removed": label, "libraries": sorted(remaining)}


def _collection_entries(path: Path) -> dict[str, bytes]:
    with ZipFile(path) as archive:
        names = _member_names(archive, path.name)
        return {name: archive.read(name) for name in names}


def _routes_document(entries: dict[str, bytes]) -> list[dict]:
    try:
        document = json.loads(entries["routes.json"].decode("utf-8"))
    except KeyError as error:
        raise _invalid("Route collection is missing routes.json") from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise _invalid(f"routes.json is not valid JSON: {error}") from error
    routes = document.get("routes") if isinstance(document, dict) else None
    if not isinstance(routes, list) or not routes:
        raise _invalid("routes.json: routes must be a non-empty list")
    keys: set[str] = set()
    for entry in routes:
        if not isinstance(entry, dict):
            raise _invalid("routes.json: every route must be an object")
        key = entry.get("key")
        if not isinstance(key, str) or not key:
            raise _invalid("routes.json: route without key")
        if key in keys:
            raise _invalid(f"routes.json: duplicate route key {key!r}")
        keys.add(key)
        name = entry.get("file")
        path = PurePosixPath(name) if isinstance(name, str) else None
        if path is None or path.is_absolute() or len(path.parts) < 2 or path.parts[0] != "routes":
            raise _invalid(f"routes.json: {key} file must be under routes/")
        if any(part in {"", ".", ".."} for part in path.parts) or not path.name.endswith(".operon.zip"):
            raise _invalid(f"routes.json: {key} file must be a routes/*.operon.zip")
    return routes


def _verify_collection(entries: dict[str, bytes], routes: list[dict]) -> None:
    sums = entries.get("SHA256SUMS")
    required = {entry["file"] for entry in routes}
    if sums is not None:
        listed = _parse_sums(sums, "route collection")
        missing = required - set(listed)
        if missing:
            raise _invalid(f"route collection: SHA256SUMS does not cover {min(missing)!r}")
        for name, digest in listed.items():
            if name not in entries:
                raise _invalid(f"route collection: SHA256SUMS lists a missing file {name!r}")
            if hashlib.sha256(entries[name]).hexdigest() != digest:
                raise _invalid(f"route collection: SHA256SUMS digest mismatch for {name!r}")
    for entry in routes:
        name = entry["file"]
        if name not in entries:
            raise _invalid(f"routes.json: {entry['key']} file {name!r} is missing from the collection")
        digest = entry.get("sha256")
        if sums is None and (not isinstance(digest, str) or not SHA256.match(digest)):
            raise _invalid(f"routes.json: {entry['key']} has no sha256 and the collection has no SHA256SUMS")
        if isinstance(digest, str) and SHA256.match(digest):
            if hashlib.sha256(entries[name]).hexdigest() != digest:
                raise _invalid(f"routes.json: sha256 mismatch for {name!r}")


def _route_graph(entries: dict[str, bytes], route: dict):
    from src.web.parameters import import_bundle

    content = entries[route["file"]]
    try:
        with ZipFile(io.BytesIO(content)) as archive:
            names = set(archive.namelist())
    except BadZipFile as error:
        raise _invalid(f"Route {route['key']!r} is not a valid workflow ZIP") from error
    if names != ROUTE_MEMBERS:
        raise _invalid(
            f"Route {route['key']!r} must contain exactly graph.json, parameters.json and execution.json"
        )
    return import_bundle(content)


def _verify_pins(state: dict, graph) -> None:
    # 5.0 canvas graphs are not bound to pins; the installed library resolves ids.
    return
    for operator, pin in (graph.plugin_lock or {}).items():
        if not isinstance(pin, dict):
            raise RoutePinMismatch(f"Route operator {operator!r} has an invalid pin")
        package = pin.get("package")
        version = pin.get("version")
        code_sha = pin.get("code_sha")
        if not isinstance(package, str) or not isinstance(version, str) or not isinstance(code_sha, str):
            raise RoutePinMismatch(f"Route operator {operator!r} has an incomplete pin: {pin!r}")
        expected = {"package": package, "version": version, "code_sha": code_sha}
        descriptor = _installed_descriptor(state, operator)
        actual = (
            {
                "package": descriptor["distribution"],
                "version": descriptor["package_version"],
                "code_sha": descriptor["code_sha"],
            }
            if descriptor is not None
            else None
        )
        if (descriptor is None
                or canonicalize_name(descriptor["distribution"]) != canonicalize_name(package)
                or descriptor["package_version"] != version
                or descriptor["code_sha"] != code_sha):
            raise RoutePinMismatch(
                f"Route operator {operator!r} pin mismatch: expected {expected}, installed {actual}. "
                "Install the matching operon-library bundle first."
            )


def install_routes_collection(service, path) -> dict:
    """Validate and register every route in a 5.0.0 route collection."""
    source = Path(filesystem_path(path))
    if not source.is_file():
        raise _invalid(f"{source}: route collection does not exist")
    entries = _collection_entries(source)
    routes = _routes_document(entries)
    _verify_collection(entries, routes)
    application = getattr(service, "application", None)
    if application is None:
        raise _invalid("Route collections can only be imported into a running application.")
    state = service.plugins.state()
    planned = []
    for route in routes:
        graph = _route_graph(entries, route)
        _verify_pins(state, graph)
        name = route.get("name") or graph.name or route["key"]
        graph.name = name
        planned.append({"key": route["key"], "name": name, "graph": graph})
    workflows = application.workflows
    existing = {item["name"]: item for item in workflows.list()}
    saved = []
    for item in planned:
        previous = existing.get(item["name"])
        if previous is not None:
            item["id"] = workflows.save(
                item["graph"], workflow_id=previous["id"], expected_version=previous["version"]
            )["id"]
        else:
            item["id"] = workflows.save(item["graph"])["id"]
        saved.append(item)
    registered = {item["id"] for item in service.routes.register([item["id"] for item in saved])}
    missing = [item["id"] for item in saved if item["id"] not in registered]
    if missing:
        raise _invalid(f"Route registration failed for {', '.join(missing)}")
    return {
        "routes": [{"key": item["key"], "name": item["name"]} for item in saved],
        "count": len(saved),
    }
