"""A client for the running world, for the strangers scripts (snapshot.py, replay.py).

    import sys; sys.path.insert(0, 'extras/mounts/mcp/tests/strangers'); from world import W, props
Base and node come from STRANGERS_BASE (default http://127.0.0.1:8300) and STRANGERS_NODE (0x11)."""
import importlib.util, os
_here = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location('hand_base', os.path.join(_here, '..', '..', 'hands', 'hand.py'))
_hand = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_hand)
BASE = os.environ.get('STRANGERS_BASE', 'http://127.0.0.1:8300')
NODE = os.environ.get('STRANGERS_NODE', '0x11')
W = _hand.World(BASE, NODE)
stream = _hand._stream

def props(r):
    return {k.lstrip('/'): v for k, v in (r.get('properties') or {}).items() if not k.startswith('/sys')}
