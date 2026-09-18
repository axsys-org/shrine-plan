"""Production Grove startup shared by the disposable transport harnesses."""
from tool_context import CORE, EXTRAS, BAG, fixture_repository
import json
from pathlib import Path
from html.parser import HTMLParser

import test_runner


MODES = frozenset(('journal', 'journal-eden', 'value', 'physical-large', 'physical-epoch'))
RETURNED = 'DEBUG-TRANSPORT-RETURNED'


def compiler_template(explicit, wisp):
    """Stage compiler-only state by default; explicit templates remain opt-in."""
    template = Path(explicit) if explicit else test_runner.stage(wisp, False, 900)
    for name in ('data.mdb', 'pins.pack'):
        if not (template / name).is_file():
            raise ValueError(f'Missing compiler bootstrap file: {template / name}')
    return template


def startup_source(port, mode, count=10000):
    if mode not in MODES or not 0 < port < 65536 or port in (8138, 51571):
        raise ValueError('Expected an owned ephemeral port and a known fixture mode.')
    return '\n'.join([
        '(#bind fixture (#module debug-transport-fixture))',
        f'(print ("{RETURNED}" (Try (lambda (ignored) (fixture:start {port} {json.dumps(mode)} {count})) 0)))', '',
    ])


def require_declaration(document):
    """Prove the HTTP assertions are observing the native declaration."""
    assert 'data-grove-contract="debugger/v1"' in document, 'Missing native Grove declaration'


class SlotDocument(HTMLParser):
    """Read the slot data contract, not presentation-only manifest previews."""
    def __init__(self, html):
        super().__init__()
        self.workspace = {}
        self.fields = {}
        require_declaration(html)
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if data.get('id') == 'debug-workspace':
            self.workspace = data
        if tag == 'sh-limb' and 'data-key' in data:
            self.fields[data['data-key']] = data
