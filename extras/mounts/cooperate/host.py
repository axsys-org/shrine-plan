"""Cooperation uses the existing MCP endpoint; no model process is started."""
from pathlib import Path
import runpy


def prepare(root, work, check, cleanup, context):
    return root, []


def check(base, node, timeout):
    runpy.run_path(str(Path(__file__).parent / 'tests' / 'http.py'))['check'](base, node, timeout)
