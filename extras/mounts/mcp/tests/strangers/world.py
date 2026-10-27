"""A client for the running world and its links index, for the Three Strangers checks.

    import sys; sys.path.insert(0, 'extras/mounts/mcp/tests/strangers'); from world import W, idx, props
Base and node come from STRANGERS_BASE (default http://127.0.0.1:8300), STRANGERS_NODE (0x11), LINKS_PORT (8312)."""
import importlib.util, json, os, urllib.request
_here = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location('hand_base', os.path.join(_here, '..', '..', 'hands', 'hand.py'))
_hand = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_hand)
BASE = os.environ.get('STRANGERS_BASE', 'http://127.0.0.1:8300')
NODE = os.environ.get('STRANGERS_NODE', '0x11')
LINKS = 'http://127.0.0.1:' + os.environ.get('LINKS_PORT', '8312')
W = _hand.World(BASE, NODE)
stream = _hand._stream

def idx(route):
    """One index query, e.g. idx('/unfold?at=/0x11/user/orgs/verisk&depth=3')."""
    return json.load(urllib.request.urlopen(LINKS + route, timeout=60))

def props(r):
    return {k.lstrip('/'): v for k, v in (r.get('properties') or {}).items() if not k.startswith('/sys')}
