"""Regenerate backend API and YAML authoring schemas without loading operators."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from operon.contracts.schemas import write_schemas
    from operon.planning.authoring_v2 import AuthoringDocument
    directory = ROOT / 'operon' / 'contracts' / 'schemas'
    paths = write_schemas(directory)
    path = directory / 'workflow-authoring-v2.json'
    path.write_text(json.dumps(AuthoringDocument.model_json_schema(), indent=2,
                              sort_keys=True, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'schemas': [p.name for p in [*paths, path]]}))


if __name__ == '__main__':
    main()
