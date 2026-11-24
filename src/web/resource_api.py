"""Large-resource downloads and external links for the installed library.

The library declares downloadable weights and databases in ``resources.json``;
this module lists them, runs the library's own downloader in a background
thread, tracks progress, and supports cancellation.  It also links an existing
local directory into a resource root without copying bytes, and reports which
operators declare each resource.  It deliberately keeps the HTTP surface tiny so
the same functions back the desktop API, the versioned control API and the MCP
adapter.
"""
from __future__ import annotations

import gzip
import hashlib
import importlib
import os
import pathlib
import shutil
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

from fastapi import HTTPException

_jobs: dict[str, dict] = {}
_running: dict[str, str] = {}
_cancel: dict[str, threading.Event] = {}
_lock = threading.Lock()

_SCAN_SUFFIXES = ('.parameters.json', '.py', '.md')
_SCAN_LIMIT = 256 * 1024
_used_by_cache: dict[tuple[str, str], dict[str, tuple[str, ...]]] = {}
_used_by_lock = threading.Lock()


class LinkUnsupported(RuntimeError):
    """The installed operator library predates external resource linking."""


def _now() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def _code_root(service) -> Path:
    state = service.plugins.state()
    paths = state.get('code_paths') or []
    if not paths:
        raise ValueError('The installed library has no code root; import a library first.')
    return Path(service.plugins.directory) / paths[0]


def _manifest(root: Path) -> Path:
    for pattern in ('*/steps/resources.json', 'resources.json', '*/resources.json'):
        for path in sorted(root.glob(pattern)):
            return path
    raise ValueError('The installed library has no resources.json.')


def _modules(service):
    root = _code_root(service)
    text = str(root)
    if text not in sys.path:
        sys.path.insert(0, text)
    common = importlib.import_module('operon_core.steps._resources_common')
    fetch = importlib.import_module('operon_core.steps.resource_fetch')
    try:
        link = importlib.import_module('operon_core.steps.resource_link')
    except ImportError:
        link = None
    return root, common, fetch, link


def _resource(service, name: str):
    root, common, fetch, link = _modules(service)
    resources = common.load_resources(_manifest(root))
    if name not in resources:
        raise KeyError(name)
    return root, common, fetch, link, resources[name]


def _expected_files(common, resource) -> list[str]:
    """Expected relative file names, tolerating a library without the helper."""
    def normalise(entry) -> str:
        if isinstance(entry, dict):
            return str(entry.get('path') or '')
        return str(entry)

    getter = getattr(common, 'expected_files', None)
    if callable(getter):
        try:
            return [normalise(name) for name in getter(resource) if normalise(name)]
        except Exception:  # noqa: BLE001 - a broken helper must not break listing
            pass
    declared = getattr(resource, 'expected_files', ()) or getattr(resource, 'files', ())
    return [normalise(name) for name in declared or () if normalise(name)]


def _link_roots(common) -> list[str]:
    getter = getattr(common, 'link_roots', None)
    if callable(getter):
        try:
            return [str(path) for path in getter() or []]
        except Exception:  # noqa: BLE001 - an old helper must not break listing
            pass
    return []


def _link_state(common, resource) -> dict:
    getter = getattr(common, 'link_state', None)
    if callable(getter):
        try:
            state = dict(getter(resource) or {})
            return {'linked': bool(state.get('linked')), 'source': state.get('source'),
                    'mode': state.get('mode'), 'state': state.get('state'),
                    'root_target': state.get('root_target') or '',
                    'units': [dict(unit) for unit in state.get('units') or []]}
        except Exception:  # noqa: BLE001
            pass
    return {'linked': False, 'source': None, 'mode': None, 'state': None,
            'root_target': '', 'units': []}


def _size_bytes(root, names) -> int:
    if not root:
        return 0
    base = Path(str(root))
    total = 0
    for name in names:
        try:
            path = base / str(name)
            if path.is_file():
                total += path.stat().st_size
        except OSError:
            continue
    return total


def _used_by_map(root: Path, release: dict, probes: list[str]) -> dict[str, list[str]]:
    """Map each resource env (or id) to operators whose files mention it."""
    version = str(release.get('version') or release.get('tag') or '')
    key = (str(root), version)
    with _used_by_lock:
        cached = _used_by_cache.get(key)
    if cached is None:
        found: dict[str, set[str]] = {}
        try:
            candidates = [path for path in root.rglob('*')
                          if path.is_file() and path.name != 'resources.json'
                          and path.name.endswith(_SCAN_SUFFIXES)]
        except OSError:
            candidates = []
        for path in candidates:
            try:
                if path.stat().st_size > _SCAN_LIMIT:
                    continue
                content = path.read_text(encoding='utf-8', errors='replace')
            except OSError:
                continue
            owner = path.name.split('.')[0]
            if not owner:
                continue
            for probe in probes:
                if not probe:
                    continue
                if probe.isupper():
                    # Environment variables are read straight from the process
                    # environment, so any mention of the name is a real use.
                    if probe in content:
                        found.setdefault(probe, set()).add(owner)
                elif any(
                    probe in line and not line.lstrip().startswith(('import ', 'from '))
                    for line in content.splitlines()
                ):
                    # A lower-case resource id counts when the code mentions it
                    # for real; importing a helper from a similarly named module
                    # is not the same as consuming the resource.
                    found.setdefault(probe, set()).add(owner)
        cached = {probe: tuple(sorted(owners)) for probe, owners in found.items()}
        with _used_by_lock:
            _used_by_cache[key] = cached
    return {probe: list(owners) for probe, owners in cached.items()}


def _environment_map(service) -> dict[str, str]:
    """Map each operator id to the isolated environment its descriptor declares."""
    catalog = getattr(service, 'catalog', None) or {}
    found: dict[str, str] = {}
    for entry in list(catalog.get('operators') or []) + list(catalog.get('readers') or []):
        environment = (entry.get('resources') or {}).get('environment')
        identifier = entry.get('id')
        if environment and identifier:
            found[str(identifier)] = str(environment)
    return found


def _declared_environments() -> set[str]:
    """Return the isolated environment names the imported library declares.

    A resource whose id equals an environment name belongs to that environment
    even when no operator descriptor mentions it, because the environment is
    what consumes the weights or database the resource provides.
    """
    try:
        from operon import environments
        return {str(name) for name in environments.load()}
    except Exception:  # noqa: BLE001
        return set()


def _with_percent(job: dict) -> dict:
    """Copy one job and add the progress fields the panel renders.

    ``completed_bytes`` only moves when a whole file finishes; ``bytes`` tracks
    the partial file too, so use the larger of the two or a multi-gigabyte
    download would look frozen between two files.

    A manifest whose files do not all declare a size reports a zero
    ``planned_bytes``.  Returning 0% there would claim the download made no
    progress, so the total is marked indeterminate and the bytes written so far
    are exposed instead; when the total is known the percentage keeps its
    original integer meaning.
    """
    result = dict(job)
    planned = int(result.get("planned_bytes") or 0)
    done = max(int(result.get("completed_bytes") or 0), int(result.get("bytes") or 0))
    result["downloaded_bytes"] = done
    result["indeterminate"] = planned <= 0
    result["percent"] = min(100, max(0, int(done * 100 / planned))) if planned > 0 else None
    return result


def operation(job_id: str) -> dict | None:
    job = _jobs.get(job_id)
    return _with_percent(job) if job else None



def unit_coverage(resource, unit: str | None) -> tuple[list[str], list[str]]:
    """Return the unit files that have a download source and the ones that do not."""
    names: list[str] = []
    for component in getattr(resource, 'components', ()) or ():
        if str(component.get('name')) == unit:
            names = [str(entry) for entry in component.get('files') or ()]
            break
    if not names:
        declared = getattr(resource, 'expected_files', ()) or getattr(resource, 'files', ())
        names = [str(entry.get('path') if isinstance(entry, dict) else entry)
                 for entry in declared or ()]
        names = [name for name in names if name]
    sources = [(str(entry.get('path') or ''), str(entry.get('member') or ''))
               for entry in getattr(resource, 'downloads', ()) or ()]
    # A git entry fills a directory from a repository instead of streaming one
    # file, so it covers the declared names below its path (an empty path means
    # the whole resource comes from the checkout).
    git_paths = [str(entry.get('path') or '').strip().replace('\\', '/').strip('/')
                 for entry in getattr(resource, 'downloads', ()) or ()
                 if isinstance(entry.get('git'), dict)]
    archive_prefixes = [str(entry.get('path') or '').strip().replace('\\', '/').strip('/')
                        for entry in getattr(resource, 'downloads', ()) or ()
                        if str(entry.get('archive') or '').strip()]
    if not names and any(path and path == unit for path, _member in sources):
        return [str(unit or 'archive')], []
    covered: list[str] = []
    missing: list[str] = []
    def base(value: str) -> str:
        return value.replace('\\', '/').rsplit('/', 1)[-1]

    for name in names:
        text = str(name)
        if text.strip().startswith('{'):
            try:
                import ast

                parsed = ast.literal_eval(text)
            except (ValueError, SyntaxError):
                parsed = None
            if isinstance(parsed, dict):
                text = str(parsed.get('path') or '')
        if not text:
            continue
        normalised = text.replace('\\', '/').strip('/')
        matched = any(
            text == source
            or (source and base(source) == base(text))
            or (member and (text == member or base(member) == base(text)))
            for source, member in sources
        ) or any(
            not prefix
            or normalised == prefix
            or normalised.startswith(prefix + '/')
            for prefix in git_paths
        ) or any(
            normalised == prefix or normalised.startswith(prefix + '/')
            for prefix in archive_prefixes if prefix
        )
        (covered if matched else missing).append(text)
    if not covered:
        # A unit that ships one archive (declared under the unit name, no
        # member) is the HTTP source for every file it declares, even though no
        # per-file path equals the archive path.
        for source, member in sources:
            if source and source == str(unit or '') and not member:
                return list(names), []
    return covered, missing


def _declared_names(entries) -> list[str]:
    """Normalise a manifest file list into plain relative names."""
    names: list[str] = []
    for entry in entries or ():
        if isinstance(entry, dict):
            text = str(entry.get('path') or entry.get('name') or '')
        else:
            text = str(entry or '')
        text = text.strip()
        if text and text not in names:
            names.append(text)
    return names


def unit_declared_files(resource, unit: str) -> list[str]:
    """Return the file names one unit must have on disk.

    The manifest may leave ``units[].files`` empty and declare the payload only
    at resource level (``expected_files`` / ``files``).  With a single unit that
    list unambiguously belongs to it, so the card stays checkable instead of
    being reported as never inspected; a multi-unit resource never guesses.
    """
    units = [entry for entry in getattr(resource, 'components', ()) or ()
             if isinstance(entry, dict)]
    files: list[str] = []
    for entry in units:
        if str(entry.get('name') or '') == unit:
            files = _declared_names(entry.get('files'))
            break
    if files or len(units) > 1:
        return files
    return _declared_names(getattr(resource, 'expected_files', ())
                           or getattr(resource, 'files', ()))


def _split_presence(base, declared, common=None) -> tuple[list[str], list[str]]:
    """Split declared names into the ones present under ``base`` and the rest.

    ``base`` is the only directory those files can live in; without it nothing is
    on disk, which must read as "all missing" rather than "nothing declared".
    ``common`` is the library module, so its explicit old-name aliases count as
    present; without it only the exact path is checked.
    """
    present: list[str] = []
    missing: list[str] = []
    for name in declared:
        if base is None:
            missing.append(name)
            continue
        exists = ((common.file_exists(base, name) if common is not None and
                   hasattr(common, 'file_exists') else (base / name).exists()))
        (present if exists else missing).append(name)
    return present, missing


def _card_state(present, missing, linked: bool) -> str:
    """One vocabulary for unit/component state, derived from disk presence."""
    if not present and not missing:
        return 'unknown'
    if not missing:
        return 'linked' if linked else 'present'
    if present:
        return 'partial'
    return 'missing'


def card_ready(card) -> bool:
    """Whether one serialized unit card is fully in place.

    Shared by the local and the remote environment counters so a badge can never
    disagree with the cards the panel draws from the same payload.
    """
    if not isinstance(card, dict):
        return False
    if card.get('files_missing'):
        return False
    files = [entry for entry in card.get('files') or () if isinstance(entry, dict)]
    if files:
        return all(bool(entry.get('present')) for entry in files)
    return str(card.get('state') or '') in {'present', 'linked', 'downloaded'}


def _merge_missing(units, current, components=None) -> list[str]:
    """Union of the per-card missing names, ignoring stale resource-level entries.

    ``missing`` on the payload now has one source: the cards.  The library's
    resource-level list can still disagree (it treats a directory as absent), so
    it is only used when no card published a verdict at all.
    """
    cards = [card for card in list(units or ()) + list(components or ())
             if isinstance(card, dict) and 'files_missing' in card]
    if not cards:
        return [str(name) for name in current or () if str(name)]
    merged: list[str] = []
    for card in cards:
        for name in card.get('files_missing') or ():
            text = str(name)
            if text and text not in merged:
                merged.append(text)
    return merged


def _component_name(entry) -> str:
    return str(entry.get('name') or entry.get('path') or '') if isinstance(entry, dict) else ''


def _mirror_components(components, units, rsync=None, downloads=None) -> None:
    """Copy the unit verdict onto the matching component.

    The panel renders components, so every component publishes the same fields
    and both views agree: ``missing`` comes from ``files_missing`` and
    ``files[].present`` is rewritten from it.  A component without a matching
    unit still gets the fields, derived from its own manifest entries, so the
    frontend never reads an absent key.
    """
    rows = [unit for unit in units or () if isinstance(unit, dict)]
    by_name = {str(unit.get('name') or ''): unit for unit in rows}
    single = rows[0] if len(rows) == 1 and len(components or ()) == 1 else None
    sources = set()
    for entry in downloads or ():
        if isinstance(entry, dict):
            for key in ('path', 'member'):
                text = str(entry.get(key) or '')
                if text:
                    sources.add(text)
    for component in components or ():
        if not isinstance(component, dict):
            continue
        entries = [entry for entry in component.get('files') or ()
                   if isinstance(entry, dict)]
        declared = [_component_name(entry) for entry in entries]
        absent = [_component_name(entry) for entry in entries
                  if not entry.get('present')]
        present = [name for name in declared if name not in set(absent)]
        component.setdefault('downloadable',
                             [name for name in declared if name in sources])
        component.setdefault('undownloadable', [])
        component.setdefault('files_present', present)
        component.setdefault('files_missing', absent)
        component.setdefault('missing', list(component['files_missing']))
        component.setdefault('download_supported',
                             bool(component['downloadable']) or bool(rsync))
        component.setdefault('state', 'unknown' if not declared else
                             ('partial' if absent and len(absent) < len(declared)
                              else ('missing' if absent else 'present')))
        component.setdefault('source', '')
        if 'rsync' not in component:
            component['rsync'] = rsync
        unit = by_name.get(str(component.get('name') or '')) or single
        if unit is None:
            continue
        for field in ('downloadable', 'undownloadable', 'download_supported',
                      'files_present', 'files_missing', 'rsync', 'state', 'source'):
            if field in unit:
                component[field] = unit[field]
        if rsync is not None:
            component.setdefault('rsync', rsync)
        if 'files_missing' not in unit:
            continue
        missing = [str(name) for name in unit.get('files_missing') or ()]
        present = {str(name) for name in unit.get('files_present') or ()}
        component['missing'] = missing
        # A unit publishes ``<unit.path>/<file>`` once its directory is kept,
        # while the component lists bare file names; compare leaves so the two
        # views cannot disagree about one directory.
        missing_names = {name.rsplit('/', 1)[-1] for name in missing}
        present_names = {name.rsplit('/', 1)[-1] for name in present}
        files = []
        for entry in component.get('files') or ():
            if not isinstance(entry, dict):
                files.append(entry)
                continue
            copy = dict(entry)
            relative = str(copy.get('name') or copy.get('path') or '')
            leaf = relative.rsplit('/', 1)[-1]
            if leaf in missing_names:
                copy['present'] = False
            elif leaf in present_names:
                copy['present'] = True
            files.append(copy)
        component['files'] = files


def snapshot(service) -> dict:
    release = service.plugins.state().get('library_release') or {}
    try:
        root, common, _fetch, _link = _modules(service)
        resources = common.load_resources(_manifest(root))
    except ValueError as exc:
        # A server that has not imported a library yet must still answer the
        # handshake and the resources route: the panel renders the reason
        # instead of the whole call failing with a bare ValueError.
        return {'library': release,
                'library_root': str(Path(service.plugins.directory)),
                'resources': [], 'operations': [_with_percent(value) for value in list(_jobs.values())[-20:]],
                'available': False, 'error': str(exc)}
    probes = sorted({probe for resource in resources.values()
                    for probe in (resource.env, resource.id) if probe})
    used_by = _used_by_map(root, release, [probe for probe in probes if probe])
    environment_of = _environment_map(service)
    declared = _declared_environments()
    link_roots = _link_roots(common)
    items = []
    for resource in resources.values():
        item = common.check_resource(resource)
        names = _expected_files(common, resource)
        state = _link_state(common, resource)
        matched = set(used_by.get(resource.id, ()))
        if resource.env:
            matched.update(used_by.get(resource.env, ()))
        item['downloads'] = [dict(entry) for entry in resource.downloads]
        item['used_by'] = sorted(matched)
        owned = {environment_of[name] for name in item['used_by']
                 if environment_of.get(name)}
        if resource.id in declared:
            owned.add(resource.id)
        owned.update(getattr(resource, 'environments', ()) or ())
        item['environments'] = sorted(owned)
        item['components'] = [dict(entry) for entry in item.get('components') or ()]
        item['official_root'] = str(getattr(resource, 'link_root', '') or item['id'])
        item['link_roots'] = list(link_roots)
        item['expected_files'] = names
        item['linked'] = bool(item.get('linked') or state['linked'] or item.get('root_linked'))
        item['source'] = item.get('source') or state['source'] or state.get('root_target') or None
        item['mode'] = item.get('mode') or state['mode']
        item['state'] = item.get('state') or state.get('state') or (
            'linked' if item['linked'] else ('downloaded' if item.get('present') else 'missing'))
        item['link_unit'] = item.get('link_unit') or 'tree'
        item['official_root'] = str(getattr(resource, 'link_root', '') or item['id'])
        item['link_target'] = state.get('root_target') or item.get('root_target') or ''
        manifest_units = {str(unit.get('name')): dict(unit)
                          for unit in getattr(resource, 'components', ()) or ()}
        units = {unit['name']: dict(unit) for unit in state.get('units') or []}
        if len(manifest_units) == 1:
            only = next(iter(manifest_units))
            rows = item.get('units') or []
            for unit in rows:
                name = str(unit.get('name') or '')
                if name in manifest_units:
                    continue
                if name == str(item.get('link_unit') or 'tree') or len(rows) == 1:
                    unit['name'] = only
                    known = units.pop(name, None)
                    if known is not None and only not in units:
                        units[only] = known
        for unit in item.get('units') or []:
            unit.update({key: value for key, value in manifest_units.get(str(unit.get('name')), {}).items()
                         if key in {'files', 'bytes', 'mode', 'title', 'note', 'kind', 'path', 'url'}})
            known = units.get(unit.get('name')) or {}
            unit['state'] = known.get('state') or unit.get('state') or 'missing'
            unit['source'] = known.get('source') or ''
            unit['receipt'] = bool(known.get('receipt'))
        item['units'] = list(item.get('units') or [])
        for unit in item['units']:
            unit_name = str(unit.get('name') or '')
            covered, missing = unit_coverage(resource, unit_name)
            if not covered:
                # A unit and its resource may disagree on how a file is keyed
                # (tree units often store the bare name while downloads store
                # the path). Fall back to an explicit path match so a unit that
                # declares downloadable files never renders as having no source.
                declared_paths = set()
                for entry in unit.get('files') or ():
                    text = (str(entry.get('path') or '') if isinstance(entry, dict)
                            else str(entry or ''))
                    if text:
                        declared_paths.add(text)
                covered = [str(entry.get('path') or '')
                           for entry in getattr(resource, 'downloads', ()) or ()
                           if str(entry.get('path') or '') in declared_paths]
                if covered:
                    missing = [name for name in missing if name not in declared_paths]
            unit['downloadable'] = covered
            base = None
            if unit.get('state') == 'linked' and item.get('link_target'):
                base = Path(str(item['link_target']).replace('\\?\\', ''))
            elif item.get('root'):
                base = Path(str(item['root']).replace('\\?\\', ''))
            declared_files = unit_declared_files(resource, unit_name)
            prefix = str(unit.get('path') or '').strip('/')
            if prefix:
                # Units that live in their own directory publish bare names;
                # the file only exists under <root>/<unit path>/<name>.
                declared_files = [f"{prefix}/{name}" for name in declared_files]
            present_files, missing_files = _split_presence(
                base, declared_files, common)
            unit['files_present'] = present_files
            unit['files_missing'] = missing_files
            unit['state'] = _card_state(present_files, missing_files,
                                        str(unit.get('state') or '') == 'linked')
            unit['undownloadable'] = missing
            unit['rsync'] = getattr(resource, 'rsync', None)
            unit['download_supported'] = bool(covered) or bool(unit.get('rsync')) or any(
                str(entry.get('unit') or '') == unit_name
                for entry in getattr(resource, 'downloads', ()) or ())
        _mirror_components(item['components'], item['units'],
                          getattr(resource, 'rsync', None),
                          getattr(resource, 'downloads', ()))
        item['missing'] = _merge_missing(item['units'], item.get('missing'),
                                         item['components'])
        item['rsync'] = getattr(resource, 'rsync', None)
        item['size_bytes'] = _size_bytes(item.get('root'), names)
        items.append(item)
    return {
        'library': release,
        'library_root': str(Path(service.plugins.directory)),
        'resources': items,
        'operations': [_with_percent(value) for value in list(_jobs.values())[-20:]],
    }


def _writable_root(fetch, resource, root, emit) -> Path:
    """Pick a target the current user can write into.

    Some manifests declare system directories (``/usr/local/bin``) because the
    unit is normally *linked* there.  A download must never fail with EACCES:
    fall back to the per-user resource directory and record why.
    """

    declared = _target_root(fetch, resource, root)
    try:
        declared.mkdir(parents=True, exist_ok=True)
        if os.access(str(declared), os.W_OK):
            return declared
    except PermissionError:
        pass
    except OSError:
        pass
    fallback = (Path.home() / '.local' / 'share' / 'operon' / 'resources'
                / str(getattr(resource, 'id', 'resource')))
    fallback.mkdir(parents=True, exist_ok=True)
    emit(f'ROOT {declared} is not writable; downloading into {fallback}')
    return fallback


def _target_root(fetch, resource, root):
    return fetch._target_root(resource, root)


def _part_bytes(target: Path, resource) -> int:
    total = 0
    for entry in resource.downloads:
        path = target / str(entry.get('path') or '')
        part = path.with_name(path.name + '.part')
        try:
            if part.is_file():
                total += part.stat().st_size
        except OSError:
            pass
    return total


class _Cancelled(Exception):
    """Raised when the user cancels a download."""


def _sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _download(entry: dict, root: Path, *, overwrite: bool, event, job: dict, opener) -> dict:
    """Stream one file (or one archive member) with progress and integrity checks."""

    candidates = [str(item).strip() for item in entry["url"]] if isinstance(entry.get("url"), (list, tuple)) else [str(entry.get("url") or "").strip()]
    candidates = [item for item in candidates if item]
    if not candidates:
        raise ValueError("download entry has no url")
    for candidate_url in candidates:
        if not candidate_url.startswith(("https://", "http://", "ftp://")):
            raise ValueError(
                "unsupported download scheme: "
                f"{candidate_url!r}; declare https://, http://, ftp://, "
                "rsync:// or a git entry")
    relative = str(entry["path"])
    candidate = Path(relative)
    if not relative or candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"unsafe download path: {relative!r}")
    target = (root.resolve() / candidate).resolve()
    if target != root.resolve() and root.resolve() not in target.parents:
        raise ValueError(f"download path escapes the resource root: {relative!r}")
    expected_bytes = int(entry.get("bytes") or 0)
    expected_sha = str(entry.get("sha256") or "").lower()
    if target.is_file() and not overwrite:
        actual = target.stat().st_size
        size_ok = not expected_bytes or actual == expected_bytes
        digest_ok = not expected_sha or _sha256(target) == expected_sha
        if size_ok and digest_ok:
            return {"path": relative, "status": "existing", "bytes": actual}
        # A copy that no longer matches the declared payload is stale: replace
        # it instead of failing the download, so "install" can repair a tree
        # that an older upload left behind.
        target.unlink()
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".part")
    archive = str(entry.get("archive") or "").lower()
    whole_archive = archive in {"tar", "tar.gz", "tgz", "zip"} and not str(entry.get("member") or "")
    if whole_archive and target.is_dir() and any(target.iterdir()) and not overwrite:
        return {"path": relative, "status": "existing", "bytes": 0}
    failures: list[str] = []
    for url in candidates:
        hasher = hashlib.sha256()
        written = 0
        try:
            with opener(url, str(entry.get("token_env") or "")) as response, partial.open("wb") as handle:
                while True:
                    if event.is_set():
                        handle.close()
                        partial.unlink(missing_ok=True)
                        raise _Cancelled("cancelled")
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    hasher.update(chunk)
                    handle.write(chunk)
                    written += len(chunk)
                    job["bytes"] = int(job.get("completed_bytes") or 0) + written
        except _Cancelled:
            raise
        except Exception as error:
            failures.append(f"{url}: {error}")
            partial.unlink(missing_ok=True)
            continue
        break
    else:
        raise ValueError(f"download failed for {relative}: " + "; ".join(failures))
    digest = hasher.hexdigest()
    if archive in {"gz", "gzip"}:
        decompressed = target.with_name(target.name + ".extract")
        with gzip.open(partial, "rb") as source, decompressed.open("wb") as handle:
            while True:
                if event.is_set():
                    handle.close()
                    decompressed.unlink(missing_ok=True)
                    raise _Cancelled("cancelled")
                chunk = source.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
        partial.unlink(missing_ok=True)
        os.replace(decompressed, target)
        return {"path": relative, "status": "extracted", "bytes": target.stat().st_size,
                "archive_bytes": written}
    if archive == "zip":
        import zipfile

        extracted = _extract_zip(partial, target, str(entry.get("member") or ""), event, job)
        partial.unlink(missing_ok=True)
        return {"path": relative, "status": "extracted", "bytes": extracted,
                "archive_bytes": written}
    if archive in {"tar", "tar.gz", "tgz"}:
        extracted = _extract_member(partial, target, str(entry.get("member") or ""), event, job)
        partial.unlink(missing_ok=True)
        if expected_bytes and extracted != expected_bytes:
            target.unlink(missing_ok=True)
            raise ValueError(
                f"extracted size mismatch for {relative}: got {extracted}, expected {expected_bytes}"
            )
        return {"path": relative, "status": "extracted", "bytes": extracted, "archive_bytes": written}
    if expected_bytes and written != expected_bytes:
        partial.unlink(missing_ok=True)
        raise ValueError(f"download size mismatch for {relative}: got {written}, expected {expected_bytes}")
    if expected_sha and digest != expected_sha:
        partial.unlink(missing_ok=True)
        raise ValueError(f"download sha256 mismatch for {relative}: got {digest}, expected {expected_sha}")
    os.replace(partial, target)
    return {"path": relative, "status": "downloaded", "bytes": written, "sha256": digest}


def _extract_zip(bundle: Path, target: Path, member: str, event, job: dict) -> int:
    """Extract one member (or the whole archive) of a zip file to the target path."""

    import zipfile

    with zipfile.ZipFile(bundle) as archive:
        if not member:
            archive.extractall(target.parent)
            total = 0
            for name in archive.namelist():
                candidate = target.parent / name
                if candidate.is_file():
                    total += candidate.stat().st_size
            return total
        extracted = target.with_name(target.name + ".extract")
        written = 0
        with archive.open(member) as source, extracted.open("wb") as handle:
            while True:
                if event.is_set():
                    handle.close()
                    extracted.unlink(missing_ok=True)
                    raise _Cancelled("cancelled")
                chunk = source.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
                written += len(chunk)
                job["bytes"] = int(job.get("completed_bytes") or 0) + written
    os.replace(extracted, target)
    return written


def _extract_tree(bundle: Path, target: Path, event, job: dict) -> int:
    """Extract every regular file of a tar archive below ``target``."""

    import tarfile

    written = 0
    target.mkdir(parents=True, exist_ok=True)
    root = target.resolve()
    with tarfile.open(bundle, "r:*") as archive:
        for info in archive.getmembers():
            if not info.isfile():
                continue
            name = info.name
            while name.startswith("./"):
                name = name[2:]
            if not name or name.startswith("/") or ".." in pathlib.PurePosixPath(name).parts:
                raise ValueError(f"archive member escapes the target: {info.name!r}")
            destination = (root / name).resolve()
            if root not in destination.parents and destination != root:
                raise ValueError(f"archive member escapes the target: {info.name!r}")
            source = archive.extractfile(info)
            if source is None:
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            partial = destination.with_name(destination.name + ".extract")
            with source, partial.open("wb") as handle:
                while True:
                    if event.is_set():
                        handle.close()
                        partial.unlink(missing_ok=True)
                        raise _Cancelled("cancelled")
                    chunk = source.read(1024 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
                    written += len(chunk)
            os.replace(partial, destination)
            job["files"] = int(job.get("files") or 0) + 1
            job["bytes"] = int(job.get("completed_bytes") or 0) + written
    return written


def _extract_member(bundle: Path, target: Path, member: str, event, job: dict) -> int:
    """Extract one member, or the whole archive, of a tar file.

    AlphaFold publishes its reference databases as archives that stand for a
    directory tree (``bfd/*.ffdata`` and friends).  Those entries declare the
    directory as their path and leave ``member`` empty, so an empty member now
    means "unpack everything below the target directory".
    """

    import tarfile

    if not member:
        return _extract_tree(bundle, target, event, job)
    extracted = target.with_name(target.name + ".extract")
    with tarfile.open(bundle, "r:*") as archive:
        info = archive.getmember(member)
        source = archive.extractfile(info)
        if source is None:
            raise ValueError(f"archive member is not a regular file: {member!r}")
        written = 0
        with source, extracted.open("wb") as handle:
            while True:
                if event.is_set():
                    handle.close()
                    extracted.unlink(missing_ok=True)
                    raise _Cancelled("cancelled")
                chunk = source.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
                written += len(chunk)
    os.replace(extracted, target)
    return written


# Large databases and weight trees are meant to be linked from a shared cache;
# the panel disables their download button and the service refuses the request.
def _entry_covers(path: str, allowed: set[str] | None) -> bool:
    """Whether one download entry provides any file the caller asked for.

    An archive published for a whole directory (``bfd``, ``pdb70``) names that
    directory instead of each file inside it, so equality alone would drop the
    only entry able to fill those files.
    """

    if allowed is None:
        return True
    candidate = str(path or '').strip().strip('/')
    if not candidate:
        return False
    if candidate in allowed:
        return True
    prefix = candidate + '/'
    return any(name.startswith(prefix) for name in allowed)


def _selected_downloads(downloads: list[dict], allowed: set[str] | None) -> list[dict]:
    """The download entries that provide at least one of the allowed files."""

    return [entry for entry in downloads
            if _entry_covers(str(entry.get('path') or ''), allowed)]


def _prune_tree(root: Path, allowed: set[str] | None, event, emit) -> None:
    """Delete files a directory archive brought in but the unit does not declare."""

    if allowed is None or not root.is_dir():
        return
    removed = 0
    for path in sorted(root.rglob('*'), key=lambda item: len(item.parts), reverse=True):
        if event.is_set():
            return
        if path.is_file():
            relative = path.relative_to(root.parent).as_posix()
            if relative not in allowed:
                path.unlink(missing_ok=True)
                removed += 1
        elif path.is_dir() and path != root:
            try:
                path.rmdir()
            except OSError:
                pass
    if removed:
        emit(f'PRUNE {root.name}: removed {removed} undeclared file(s)')


def unit_downloads(name: str, resource, unit: str | None) -> tuple[list[dict], set[str] | None]:
    """Resolve the download entries and the allowed paths for one unit.

    A declared download list is filtered to the unit files; weights and
    databases instead publish a single URL on the unit itself, so the unit name
    becomes the download target. Very large units are refused outright.
    """
    if not unit:
        downloads = list(resource.downloads or ())
        if not downloads:
            spec = getattr(resource, 'rsync', None)
            if isinstance(spec, dict) and str(spec.get('url') or '').strip():
                return [{'path': '', 'rsync': dict(spec)}], None
            raise ValueError(f"resource '{name}' has no downloadable files")
        return downloads, None
    selected = None
    for component in getattr(resource, 'components', ()) or ():
        if str(component.get('name')) == unit:
            selected = component
            break
    if selected is None:
        raise ValueError(f"resource '{name}' has no unit named {unit!r}")
    allowed = None
    downloads = list(resource.downloads or ())
    if downloads:
        # The allowed set is the same coverage the panel counts as downloadable.
        # A unit that ships one archive is addressed by the unit name rather than
        # by the files inside it, and a unit whose manifest only lists its files
        # at resource level must not filter every entry away.
        covered = {str(entry) for entry in unit_coverage(resource, unit)[0]}
        if covered:
            for entry in downloads:
                if str(entry.get('path') or '') == unit and not str(entry.get('member') or ''):
                    covered.add(str(unit))
            if _selected_downloads(downloads, covered):
                allowed = covered
        return downloads, allowed
    spec = getattr(resource, 'rsync', None)
    if isinstance(spec, dict) and str(spec.get('url') or '').strip():
        entry = {'path': str(selected.get('name') or ''), 'rsync': dict(spec)}
        return [entry], allowed
    page = str(selected.get('url') or '').strip()
    if page:
        tail = page.rsplit('/', 1)[-1].lower()
        suffixes = ('.tar', '.tar.gz', '.tgz', '.zip', '.gz', '.pt', '.pth', '.bin',
                    '.npz', '.pdb', '.h5', '.ckpt', '.safetensors', '.fasta', '.fa', '.csv', '.json')
        if not any(tail.endswith(suffix) for suffix in suffixes):
            raise ValueError(
                f"resource '{name}' unit {unit!r} only documents a project page ({page}); "
                'link an existing directory or declare per-file download sources instead'
            )
        return [{'path': str(selected.get('name') or ''), 'url': page}], None
    raise ValueError(f"resource '{name}' has no downloadable files")


def _declared_sizes(resource, unit: str | None) -> dict[str, int]:
    """Per-file sizes the manifest publishes, keyed by relative path.

    ``units[].files`` may be plain names or mappings carrying ``bytes`` (or
    ``size_bytes``); only the latter can seed ``planned_bytes`` when a download
    entry publishes no size of its own.
    """
    units = [entry for entry in getattr(resource, 'components', ()) or ()
             if isinstance(entry, dict)]
    if unit:
        units = [entry for entry in units if str(entry.get('name') or '') == unit]
    elif len(units) > 1:
        # A resource-level file list cannot be attributed to one unit.
        units = []
    sizes: dict[str, int] = {}
    for entry in units:
        for name, size in (entry.get('file_sizes') or {}).items():
            try:
                value = int(size)
            except (TypeError, ValueError):
                continue
            if value > 0:
                sizes[str(name)] = value
        for item in entry.get('files') or ():
            if not isinstance(item, dict):
                continue
            name = str(item.get('path') or item.get('name') or '').strip()
            size = int(item.get('bytes') or item.get('size_bytes') or 0)
            if name and size > 0:
                sizes[name] = size
    return sizes


def _planned_bytes(planned: list[dict], resource=None, unit: str | None = None) -> int:
    """Total declared size, only when every planned file publishes one.

    Some manifests leave the size off the download entry and publish it on the
    unit file instead; fall back to that map so the panel can still show a
    percentage.  One unknown file keeps the total at 0 (indeterminate progress)
    rather than inventing a number.
    """
    declared = _declared_sizes(resource, unit) if resource is not None else {}
    total = 0
    for entry in planned:
        size = int(entry.get("bytes") or entry.get("size_bytes") or 0)
        if size <= 0 and declared:
            size = int(declared.get(str(entry.get("path") or "")) or 0)
        if size <= 0:
            return 0
        total += size
    return total


def start(service, name: str, root: str | None = None, overwrite: bool = False,
          unit: str | None = None) -> dict:
    _root_path, _common, fetch, _link_module, resource = _resource(service, name)
    downloads, allowed = unit_downloads(name, resource, unit)
    with _lock:
        active = _running.get(name)
        if active and _jobs.get(active, {}).get('status') == 'running':
            return operation(active)
        key = uuid.uuid4().hex
        planned = _selected_downloads(downloads, allowed)
        covered, missing = unit_coverage(resource, unit)
        job = {'id': key, 'name': name, 'kind': 'download', 'status': 'running',
               'error': None,
               'started_at': _now(), 'finished_at': None, 'bytes': 0, 'files': 0,
               'completed_bytes': 0, 'planned_bytes': _planned_bytes(planned, resource, unit),
               'phase': 'downloading', 'current': '', 'planned': len(planned),
               'unit': unit, 'downloadable': covered, 'undownloadable': missing}
        _jobs[key] = job
        _running[name] = key
        event = threading.Event()
        _cancel[key] = event
    logs = Path(service.directory) / 'resources'
    logs.mkdir(parents=True, exist_ok=True)
    log = logs / f'{name}.log'

    def emit(line: str) -> None:
        with log.open('a', encoding='utf-8') as stream:
            stream.write(str(line) + '\n')
            stream.flush()

    target = _writable_root(fetch, resource, root, emit)

    def watch() -> None:
        while job['status'] == 'running':
            try:
                job['bytes'] = int(job.get('completed_bytes') or 0) + _part_bytes(target, resource)
            except Exception:
                pass
            time.sleep(0.5)

    def run() -> None:
        try:
            target.mkdir(parents=True, exist_ok=True)
            emit(f'START {name} -> {target}')
            job['phase'] = 'downloading'
            for entry in downloads:
                if not _entry_covers(str(entry.get('path') or ''), allowed):
                    continue
                if event.is_set():
                    raise RuntimeError('cancelled')
                job['current'] = str(entry.get('path') or '')
                url_value = str(entry.get('url') or '')
                git = entry.get('git')
                if not isinstance(git, dict) and url_value.startswith(('git+', 'git://')):
                    git = {'url': url_value[4:] if url_value.startswith('git+') else url_value}
                spec = entry.get('rsync')
                if isinstance(git, dict) and str(git.get('url') or '').strip():
                    emit(f'GIT {git.get("url")} -> {target}')
                    result = _git_fetch(git, target, event=event, job=job, emit=emit)
                elif isinstance(spec, dict):
                    emit(f'RSYNC {spec.get("url")} -> {target}')
                    result = _rsync_fetch(spec, target, event=event, job=job, emit=emit)
                else:
                    emit(f'GET {entry.get("url")} -> {entry.get("path")}')
                    result = _download(entry, target, overwrite=overwrite, event=event, job=job,
                                       opener=fetch._open_url)
                job['files'] += 1
                job['completed_bytes'] = int(job.get('completed_bytes') or 0) + int(result.get('bytes') or 0)
                job['bytes'] = int(job.get('completed_bytes') or 0)
                emit(f'OK {entry.get("path")} {result.get("status")} {result.get("bytes", 0)}')
                if entry.get('archive') and allowed is not None:
                    _prune_tree(target / str(entry.get('path') or ''), allowed,
                                event, emit)
            if event.is_set():
                raise RuntimeError('cancelled')
            if job['files'] == 0:
                raise RuntimeError('no declared download source covers the missing files '
                                   'of this unit; link an existing directory instead')
            job['status'] = 'succeeded'
            job['phase'] = 'complete'
        except Exception as exc:  # noqa: BLE001 - surfaced in the job and log
            cancelled = event.is_set() or str(exc) == 'cancelled'
            job['status'] = 'cancelled' if cancelled else 'failed'
            job['phase'] = 'cancelled' if cancelled else 'failed'
            job['error'] = 'cancelled' if cancelled else str(exc)
            emit(f'{"CANCEL" if cancelled else "FAIL"} {name}: {exc}')
        finally:
            job['finished_at'] = _now()
            with _lock:
                if _running.get(name) == job['id']:
                    _running.pop(name, None)
                _cancel.pop(job['id'], None)

    threading.Thread(target=watch, name=f'resource-watch-{name}', daemon=True).start()
    threading.Thread(target=run, name=f'resource-{name}', daemon=True).start()
    return operation(key)


def _rsync_fetch(spec: dict, target: Path, *, event: threading.Event,
                 job: dict, emit) -> dict:
    """Fetch a resource directory through the rsync protocol.

    Some archives (the PDB mmCIF mirror, for instance) only publish their data
    through rsync, so there is no HTTP archive to stream.  This runs the system
    rsync client and reports its progress in the resource log.
    """
    url = str(spec.get('url') or '').strip()
    if not url:
        raise RuntimeError('rsync 源为空：清单里没有给出 rsync 地址')
    binary = os.environ.get('OPERON_RSYNC') or shutil.which('rsync')
    if not binary:
        raise RuntimeError(
            'rsync 不可用：这台机器没有找到 rsync 可执行文件。可以链接已有目录，'
            '或安装 rsync（Windows 上可用 cwRsync）后重试。')
    target.mkdir(parents=True, exist_ok=True)
    command = [binary, '--archive', '--partial', '--info=progress2', url, str(target)]
    emit('RSYNC ' + ' '.join(command))
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, bufsize=1)
    try:
        for line in process.stdout:  # type: ignore[union-attr]
            if event.is_set():
                process.terminate()
                raise RuntimeError('cancelled')
            clean = line.strip()
            if clean:
                emit(clean)
                job['current'] = clean[:120]
        code = process.wait()
    finally:
        if process.poll() is None:
            process.kill()
    if event.is_set():
        raise RuntimeError('cancelled')
    if code != 0:
        raise RuntimeError(f'rsync 失败（退出码 {code}）：{url}')
    return {'status': 'fetched', 'bytes': 0}


def _git_fetch(spec: dict, target: Path, *, event: threading.Event,
               job: dict, emit) -> dict:
    """Clone one repository (or one subdirectory of it) into the target.

    Several upstreams publish only sources: the OpenFold checkout, the
    AntiSMASH web assets, the RFdiffusion scripts.  A git entry either fills a
    directory or copies a subdirectory out of the checkout, so the resource
    keeps the same declared file layout as an archive download.
    """
    import tempfile

    url = str(spec.get('url') or '').strip()
    if url.startswith('git+'):
        url = url[4:]
    if not url:
        raise RuntimeError('git 源为空：清单里没有给出仓库地址')
    binary = os.environ.get('OPERON_GIT') or shutil.which('git')
    if not binary:
        raise RuntimeError(
            'git 不可用：这台机器没有找到 git 可执行文件。可以链接已有目录，'
            '或安装 git 后重试。')
    ref = str(spec.get('ref') or spec.get('branch') or spec.get('tag') or '').strip()
    subdir = str(spec.get('subdir') or '').strip().strip('/')
    target.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix='operon-git-'))
    checkout = scratch / 'checkout'
    command = [binary, 'clone', '--depth', '1']
    if ref:
        command += ['--branch', ref]
    command += [url, str(checkout)]
    emit('GIT ' + ' '.join(command))
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, bufsize=1)
    try:
        for line in process.stdout:  # type: ignore[union-attr]
            if event.is_set():
                process.terminate()
                raise RuntimeError('cancelled')
            clean = line.strip()
            if clean:
                emit(clean)
                job['current'] = clean[:120]
        code = process.wait()
    finally:
        if process.poll() is None:
            process.kill()
    if event.is_set():
        shutil.rmtree(scratch, ignore_errors=True)
        raise RuntimeError('cancelled')
    if code != 0:
        shutil.rmtree(scratch, ignore_errors=True)
        raise RuntimeError(f'git 失败（退出码 {code}）：{url}')
    origin = checkout / subdir if subdir else checkout
    if not origin.is_dir():
        shutil.rmtree(scratch, ignore_errors=True)
        raise RuntimeError(f'git 检出后找不到子目录 {subdir!r}：{url}')
    copied = 0
    try:
        for item in origin.rglob('*'):
            if event.is_set():
                raise RuntimeError('cancelled')
            if not item.is_file():
                continue
            relative = item.relative_to(origin)
            if '.git' in relative.parts:
                # Repository metadata is not part of the resource, and git keeps
                # its pack files read-only: copying them turned the next attempt
                # into "Permission denied" instead of a plain refresh.
                continue
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists() and not os.access(destination, os.W_OK):
                destination.chmod(0o644)
            shutil.copyfile(item, destination)
            os.chmod(destination, (item.stat().st_mode & 0o777) | 0o200)
            copied += item.stat().st_size
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    emit(f'GIT OK {url} {copied} bytes')
    return {'status': 'cloned', 'bytes': copied}


def _latest_job(name: str) -> dict | None:
    """Return the most recent job recorded for one resource name, if any."""
    for job in reversed(list(_jobs.values())):
        if str(job.get('name') or '') == name:
            return job
    return None


def cancel(service, name: str) -> dict:
    """Cancel the download running for one resource name.

    The answer always names the fields the panel reacts to: ``cancelled`` (a
    live job was signalled just now), ``completed`` (no live job remains, so
    there is nothing left to cancel) and the job ``status``.  A finished job
    keeps its other fields so an old caller still sees the same payload shape.
    """
    with _lock:
        key = _running.get(name)
        live = _jobs.get(key) if key else None
        if live is not None and str(live.get('status') or '') == 'running':
            event = _cancel.get(key)
            if event is None:
                raise KeyError(name)
            event.set()
            live['phase'] = 'cancelling'
            answer = dict(live)
            answer['cancelled'] = True
            answer['completed'] = False
            answer['status'] = str(live.get('status') or 'running')
            return answer
        finished = live if live is not None else _latest_job(name)
        if finished is None:
            raise KeyError(name)
        answer = dict(finished)
        answer['cancelled'] = False
        answer['completed'] = True
        answer['status'] = str(finished.get('status') or 'cancelled')
        return answer


def read_log(service, name: str, limit: int = 200) -> dict:
    _resource(service, name)
    log = Path(service.directory) / 'resources' / f'{name}.log'
    if not log.is_file():
        return {'name': name, 'text': ''}
    lines = log.read_text(encoding='utf-8', errors='replace').splitlines()
    limit = max(1, min(int(limit), 2000))
    return {'name': name, 'text': chr(10).join(lines[-limit:])}


def _record_link(name: str, status: str, result: dict, *, source: str = '') -> dict:
    job = {'id': uuid.uuid4().hex, 'name': name, 'kind': 'link', 'status': status,
           'error': None, 'started_at': _now(), 'finished_at': _now(),
           'bytes': 0, 'files': len(result.get('files') or []), 'completed_bytes': 0,
           'phase': 'complete', 'current': str(result.get('source') or source or ''),
           'mode': result.get('mode'), 'root': result.get('root'),
           'source': result.get('source') or source or None}
    with _lock:
        _jobs[job['id']] = job
    return job


def link(service, name: str, source: str, replace: bool = False,
         unit: str | None = None) -> dict:
    """Link one official maintenance unit into the resource root; copy no bytes."""
    _root, common, _fetch, link_module, resource = _resource(service, name)
    operation_link = getattr(link_module, 'link', None) if link_module is not None else None
    if not callable(operation_link):
        raise LinkUnsupported('The installed library does not support linking existing resources.')
    try:
        result = dict(operation_link(resource, source, replace=bool(replace),
                                     unit=unit) or {})
    except TypeError:
        if unit:
            raise LinkUnsupported(
                'The installed library cannot link a single unit; update the operator library.')
        result = dict(operation_link(resource, source, replace=bool(replace),
                                     allowed_roots=_link_roots(common)) or {})
    result.setdefault('id', result.get('name') or name)
    job = _record_link(name, 'linked', result, source=source)
    result['operation'] = job['id']
    return result


def unlink(service, name: str, unit: str | None = None) -> dict:
    """Remove one external link, keeping the source tree untouched."""
    _root, common, _fetch, link_module, resource = _resource(service, name)
    operation_unlink = getattr(link_module, 'unlink', None) if link_module is not None else None
    if not callable(operation_unlink):
        raise LinkUnsupported('The installed library does not support unlinking resources.')
    try:
        result = dict(operation_unlink(resource, unit=unit) or {})
    except TypeError:
        if unit:
            raise LinkUnsupported(
                'The installed library can only unlink a whole resource; update the operator library.')
        result = dict(operation_unlink(resource) or {})
    result.setdefault('id', result.get('name') or name)
    resolve = getattr(common, 'resolve_root', None)
    root = None
    if callable(resolve):
        try:
            resolved = resolve(resource)
        except Exception:  # noqa: BLE001 - reporting must not fail a successful unlink
            resolved = None
        if resolved:
            root = str(resolved)
    result.setdefault('root', root)
    job = _record_link(name, 'unlinked', result)
    result['operation'] = job['id']
    return result


def _drive_roots() -> list[str]:
    if os.name != 'nt':
        return ['/']
    values = []
    for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
        candidate = pathlib.Path(f'{letter}:\\')
        try:
            if candidate.exists():
                values.append(str(candidate))
        except OSError:
            continue
    return values


def browse(path: str | None = None, show_files: bool = True) -> dict:
    """List one directory so the desktop picker can walk the file system."""
    import pathlib

    raw = str(path or '').strip()
    if not raw:
        roots = _drive_roots()
        target = pathlib.Path(roots[0]) if roots else pathlib.Path.home()
    else:
        target = pathlib.Path(raw).expanduser()
    try:
        target = target.resolve()
    except OSError as exc:
        raise ValueError(f'cannot resolve {raw}: {exc}') from exc
    if not target.exists():
        raise ValueError(f'no such directory: {target}')
    if not target.is_dir():
        target = target.parent
    entries = []
    try:
        with os.scandir(target) as listing:
            for item in listing:
                if item.name.startswith('.'):
                    continue
                try:
                    directory = item.is_dir()
                    if not directory and not show_files:
                        continue
                    info = item.stat()
                    entries.append({'name': item.name, 'path': str(target / item.name),
                                    'directory': directory, 'bytes': info.st_size})
                except (PermissionError, FileNotFoundError, OSError):
                    continue
    except PermissionError as exc:
        raise ValueError(f'permission denied: {target}') from exc
    entries.sort(key=lambda entry: (not entry['directory'], entry['name'].lower()))
    parent = target.parent
    return {'path': str(target), 'parent': str(parent) if str(parent) != str(target) else '',
            'roots': _drive_roots(), 'entries': entries[:500]}


def mount_resources(app, service) -> None:
    @app.post('/api/browse')
    def browse_directory(payload: dict | None = None):
        body = payload or {}
        try:
            return browse(body.get('path'), bool(body.get('files', True)))
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get('/api/resources')
    def list_resources():
        try:
            return snapshot(service)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post('/api/resources/{name}/download')
    def download(name: str, payload: dict | None = None):
        body = payload or {}
        try:
            return start(service, name, body.get('root'), bool(body.get('overwrite', False)),
                         str(body.get('unit') or '') or None)
        except KeyError as exc:
            raise HTTPException(404, f"unknown resource: {name}") from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post('/api/resources/{name}/link')
    def link_resource(name: str, payload: dict | None = None):
        body = payload or {}
        try:
            return link(service, name, str(body.get('source') or ''),
                        bool(body.get('replace', False)),
                        str(body.get('unit') or '') or None)
        except KeyError as exc:
            raise HTTPException(404, f"unknown resource: {name}") from exc
        except LinkUnsupported as exc:
            raise HTTPException(501, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.delete('/api/resources/{name}/link')
    def unlink_resource(name: str, unit: str | None = None):
        try:
            return unlink(service, name, unit)
        except KeyError as exc:
            raise HTTPException(404, f"unknown resource: {name}") from exc
        except LinkUnsupported as exc:
            raise HTTPException(501, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post('/api/resources/{name}/cancel')
    def cancel_download(name: str):
        try:
            return cancel(service, name)
        except KeyError as exc:
            raise HTTPException(404, f"no running download: {name}") from exc

    @app.get('/api/resources/operations/{job_id}')
    def operation_status(job_id: str):
        job = operation(job_id)
        if job is None:
            raise HTTPException(404, f"unknown resource operation: {job_id}")
        return job

    @app.get('/api/resources/{name}/log')
    def log(name: str, limit: int = 200):
        try:
            return read_log(service, name, limit)
        except KeyError as exc:
            raise HTTPException(404, f"unknown resource: {name}") from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
