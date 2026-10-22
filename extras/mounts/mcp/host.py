"""The MCP mount is local only: it listens with the world on 127.0.0.1 and has no credential."""
from pathlib import Path


def prepare(root, work, check, cleanup, context):
    if not check:
        print('MCP at /mcp of the world\'s URL (local, no credential); the live page at /live?views=/0x11/user/<folder>; setup in extras/mounts/mcp/SETUP.md', flush=True)
    return root, []


def check(base, node, timeout):
    import runpy
    runpy.run_path(str(Path(__file__).parent / 'tests' / 'http.py'))['check'](base, node, timeout)
