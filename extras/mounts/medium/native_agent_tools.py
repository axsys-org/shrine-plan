"""Typed transport descriptions. Native Shrine remains the evaluator/checker."""

TEXT = {'type': 'string'}
FIELD = {'type': 'object', 'properties': {
    'slot': TEXT, 'kind': {'type': 'string', 'enum': ['text', 'natural', 'reference', 'boolean', 'points']},
    'value': {'type': ['string', 'boolean', 'array']}},
    'required': ['slot', 'kind', 'value'], 'additionalProperties': False}


def tool(name, description, properties, required):
    return {'type': 'function', 'function': {'name': name, 'description': description,
        'parameters': {'type': 'object', 'properties': properties,
                       'required': required, 'additionalProperties': False}}}


TOOLS = [
    tool('inspect_material', 'Read a bounded native namespace page. Follow references; names alone do not establish identity.',
         {'subject': TEXT, 'cursor': TEXT, 'slot_cursor': TEXT, 'epoch': TEXT}, ['subject']),
    tool('read_definition', 'Read retained Grove source and its exact revision. Reuse existing definitions before writing code.',
         {'subject': TEXT}, ['subject']),
    tool('read_surface', 'Evaluate a native presentation. present selects a working result without moving the user to another page.',
         {'subject': TEXT, 'viewport': {'type': 'array', 'items': FIELD}, 'present': {'type': 'boolean'}}, ['subject']),
    tool('inspect_element', 'Resolve an exact displayed occurrence on its captured basis.',
         {'subject': TEXT, 'viewport': {'type': 'array', 'items': FIELD}, 'basis': {'type': 'object'},
          'key': TEXT, 'parameters': {'type': 'array', 'items': FIELD}}, ['subject', 'basis', 'key']),
    tool('prepare_construction',
         'Compile one small Grove unit and construct/evaluate it speculatively. Nothing is installed. The user sees actual native structure and a read-only UI preview before applying. Compilation failure returns a local diagnostic without an approval screen. Reuse field editors and native behavior; author only the missing bounded piece. A source unit contains a template for target and may contain local typed behavior. All reads/writes belong in native bindings. surface is an exact presentation beneath target, or empty for structure-only work.',
         {'subject': {'type':'string','description':'Definition location under the supplied new_definition_root (/gov/...), never the material /app/ location.'},
          'source': {'type': 'string', 'maxLength': 12000},
          'target': {'type':'string','description':'Material location under the supplied new_material_root (/app/...).'}, 'surface': TEXT},
         ['subject', 'source', 'target', 'surface']),
    tool('prepare_template',
         'Prepare an existing pinned Grove template over a fresh target. Reuse native refs in the template; do not copy existing domain subjects. Shows actual structure and evaluated UI before approval.',
         {'subject': TEXT, 'version': TEXT, 'target': TEXT, 'surface': TEXT},
         ['subject', 'version', 'target', 'surface']),
    tool('prepare_action', 'Preview a correction using an existing native action and its exact current basis. Runs the installed checks and dependencies speculatively; shows actual current/proposed records and UI before user approval. Reuse this to evolve existing material instead of creating replacements.',
         {'subject': TEXT, 'viewport': {'type': 'array', 'items': FIELD}, 'basis': {'type': 'object'},
          'key': TEXT, 'parameters': {'type': 'array', 'items': FIELD}, 'arguments': {'type': 'array', 'items': FIELD}},
         ['subject', 'basis', 'key', 'arguments']),
    tool('propose_action', 'Invoke only an explicitly granted native proposal action. Never approve or commit your own changes.',
         {'subject': TEXT, 'viewport': {'type': 'array', 'items': FIELD}, 'basis': {'type': 'object'},
          'key': TEXT, 'parameters': {'type': 'array', 'items': FIELD}, 'arguments': {'type': 'array', 'items': FIELD}},
         ['subject', 'basis', 'key', 'arguments']),
]

OPERATIONS = {
    'inspect_material': 'native/discover', 'read_definition': 'native/source',
    'read_surface': 'native/frame', 'inspect_element': 'native/inspect',
    'prepare_construction': 'native/prepare', 'prepare_template': 'native/prepare',
    'propose_action': 'native/act', 'prepare_action': 'native/prepare',
}


def decode(name, arguments):
    """Validate envelope shape; no native type/coercion or semantic matching."""
    schema = next((t['function']['parameters'] for t in TOOLS if t['function']['name'] == name), None)
    if schema is None:
        raise ValueError('Unknown capability. Use the named native tools provided here.')
    if not isinstance(arguments, dict) or set(arguments) - set(schema['properties']):
        raise ValueError('Unexpected tool fields. Use this tool’s declared arguments.')
    if not set(schema['required']).issubset(arguments):
        raise ValueError('Required tool arguments are missing.')
    body = dict(arguments)
    present = body.pop('present', False)
    if name in ('read_surface', 'inspect_element', 'propose_action', 'prepare_action'):
        body.setdefault('viewport', [])
    if name in ('inspect_element', 'propose_action', 'prepare_action'):
        body.setdefault('parameters', [])
    if name == 'prepare_template':
        body['source'] = ''
    if name == 'prepare_action':
        body['kind'] = 'action'
    return OPERATIONS[name], body, present
