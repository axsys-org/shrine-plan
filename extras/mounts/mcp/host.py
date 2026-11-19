"""The MCP mount is opened by a session and nothing else: a caller shows one the world's custody granted."""
from pathlib import Path


def prepare(root, work, check, cleanup, context):
    if not check:
        print('MCP at /mcp of the world\'s URL (send the session as Authorization: Bearer; the first one is left in <world>/src/io/mesa/out/session); the live page at /live?views=/0x11/user/<folder>; setup in extras/mounts/mcp/SETUP.md', flush=True)
    return root, []


def check(base, node, timeout):
    import runpy
    runpy.run_path(str(Path(__file__).parent / 'tests' / 'http.py'))['check'](base, node, timeout)
