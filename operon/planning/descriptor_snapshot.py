"""Executable descriptor projection, separate from defaults and audit text."""
from copy import deepcopy


IDENTITY_FIELDS = ('version', 'package', 'sha256', 'code_sha', 'execution_sha', 'resource_digest', 'sdk_abi')
PRESENTATION_FIELDS = frozenset(('title', 'description', 'documentation', 'localization',
    'category', 'icon', 'icon_image', 'preview', 'title_aliases', 'title_parameter',
    'parameters', 'runtime_defaults', 'ui_defaults', 'supported_systems', 'systems_status',
    'declaration_sha'))


def execution_schema(schema):
    """Remove schema annotations while preserving data-valued const/enum keys."""
    if not isinstance(schema, dict):
        return deepcopy(schema)
    result = deepcopy(schema)
    for key in ('default', 'title', 'description', 'examples', '$comment'):
        result.pop(key, None)
    for key in ('properties', 'patternProperties', '$defs', 'definitions', 'dependentSchemas'):
        if isinstance(result.get(key), dict):
            result[key] = {name: execution_schema(value) for name, value in result[key].items()}
    for key in ('items', 'contains', 'not', 'if', 'then', 'else', 'additionalProperties',
                'unevaluatedProperties', 'propertyNames', 'contentSchema'):
        if key in result:
            result[key] = execution_schema(result[key])
    for key in ('allOf', 'anyOf', 'oneOf', 'prefixItems'):
        if isinstance(result.get(key), (list, tuple)):
            result[key] = [execution_schema(value) for value in result[key]]
    return result


def execution_descriptor(descriptor):
    result = {key: deepcopy(value) for key, value in descriptor.items() if key not in PRESENTATION_FIELDS}
    if 'parameters_schema' in result:
        result['parameters_schema'] = execution_schema(result['parameters_schema'])
    if 'implementation' in result:
        result['implementation'] = {key: value for key, value in result['implementation'].items() if key in IDENTITY_FIELDS}
    return result
