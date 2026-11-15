"""Explicit offline environment preparation; never runs on application startup."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .service import EnvironmentStore
from .builders import LockedArchive, LockedArchiveBuilder
from .verification import confined


def prepare_recipe(store, path):
    path = Path(path).resolve()
    value = json.loads(path.read_text(encoding='utf-8'))
    if value.get('kind') == 'cpython-wheelhouse-v1':
        expected = {'kind', 'requirement', 'runtime', 'wheels', 'lock', 'executable', 'imports', 'timeout'}
        if set(value) != expected:
            raise ValueError('Invalid CPython wheelhouse recipe fields')
        from .python_builder import PythonWheelhouseBuilder, LockedWheel
        item = value['runtime']
        runtime = LockedArchive(source=confined(path.parent, item['source']), sha256=item['sha256'],
            destination=item['destination'], format=item['format'], max_unpacked_bytes=item['max_unpacked_bytes'])
        builder = PythonWheelhouseBuilder(runtime, [LockedWheel(confined(path.parent, item['source']), item['sha256'])
            for item in value['wheels']], value['lock'], executable=value['executable'],
            imports=value['imports'], timeout=value['timeout'])
        return store.prepare(value['requirement'], builder)
    if set(value) != {'requirement', 'archives', 'probes', 'fixups', 'environment', 'timeout'}:
        raise ValueError('Recipe requires exactly requirement, archives, probes, fixups, environment, timeout')
    archives = [LockedArchive(source=confined(path.parent, item['source']), sha256=item['sha256'],
                              destination=item['destination'], format=item['format'],
                              max_unpacked_bytes=item['max_unpacked_bytes']) for item in value['archives']]
    builder = LockedArchiveBuilder(archives, value['probes'], fixups=value['fixups'],
                                   environment=value['environment'], timeout=value['timeout'])
    return store.prepare(value['requirement'], builder)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--store', type=Path, required=True)
    parser.add_argument('action', choices=('prepare', 'verify', 'audit', 'package', 'materialize', 'recover', 'collect'))
    parser.add_argument('value', nargs='?')
    parser.add_argument('--destination', type=Path)
    args = parser.parse_args(argv)
    store = EnvironmentStore(args.store)
    if args.action == 'prepare':
        result = prepare_recipe(store, args.value).model_dump(mode='json')
    elif args.action in ('verify', 'audit'):
        result = store.binding(args.value, verify='deep' if args.action == 'audit' else True).model_dump(mode='json')
    elif args.action == 'package':
        from .packages import seal
        result = seal(store, args.value)
    elif args.action == 'materialize':
        if args.destination is None or args.destination.resolve() == args.store.resolve():
            parser.error('materialize requires a different --destination store; live environments are never overwritten')
        from .packages import copy_generation
        target = EnvironmentStore(args.destination)
        copy_generation(store, target, args.value)
        result = target.binding(args.value).model_dump(mode='json')
    elif args.action == 'recover':
        result = store.recover()
    else:
        result = {'collected': store.collect(args.value)}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
