"""Catalog refresh is generation-atomic for concurrent validation readers."""
from concurrent.futures import ThreadPoolExecutor
import threading

from src.web.operator_catalog import catalog_from_descriptors
from src.web.service import JobService, Settings

ROOT = __import__('pathlib').Path(__file__).resolve().parents[1]


def test_catalog_replacement_is_never_a_mixture(tmp_path):
    service = JobService(Settings(tmp_path, tmp_path / '.studio', tmp_path / 'ui',
                                  testing=True, code_root=ROOT), catalog_from_descriptors())
    try:
        service._catalog_stamp = None
        counter = {'value': 0}
        lock = threading.Lock()

        def stamp():
            with lock:
                counter['value'] += 1
                return f'generation-{counter["value"]}'

        def state():
            with lock:
                generation = counter['value']
            return {'generation': generation, 'packages': {},
                    'entries': {}, 'descriptors': []}

        def catalog_for_state(value, base):
            return {'plugin_generation': value['generation'],
                    'operators': [{'id': f'operator-{value["generation"]}',
                                   'origin': 'bundled'}]}

        service.plugins.catalog_stamp = stamp
        service.plugins.state = state
        service.plugins._catalog = catalog_for_state
        service.dependencies.sync = lambda value: None
        service.refresh_catalog()
        observed = []

        def reader():
            for _ in range(200):
                catalog = service.catalog
                generation = catalog['plugin_generation']
                ids = {item['id'] for item in catalog['operators']}
                observed.append((generation, ids))

        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = [pool.submit(reader) for _ in range(4)]
            for _ in range(40):
                service.refresh_catalog()
            for future in futures:
                future.result()
        assert observed
        for generation, ids in observed:
            assert ids == {f'operator-{generation}'}, (generation, ids)
        assert service.catalog_version > 0
    finally:
        service.shutdown()
