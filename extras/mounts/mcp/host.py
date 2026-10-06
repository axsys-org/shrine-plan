"""Issue the bearer token and hand it, with the node, to the worker.

The token lives in ~/.local/share/shrine/mcp/token, owner-only.  The worker
keeps it in memory and compares it with each request's Authorization
header; it is never written to a record.
"""
import os
import secrets
from pathlib import Path

STATE = Path.home() / '.local/share/shrine/mcp'


def token():
    STATE.mkdir(parents=True, exist_ok=True)
    os.chmod(STATE, 0o700)
    path = STATE / 'token'
    if not path.exists():
        path.write_text(secrets.token_urlsafe(32) + '\n')
        os.chmod(path, 0o600)
    return path.read_text().strip()


def prepare(root, work, check, cleanup, context):
    value = 'check' if check else token()
    if not check:
        print('MCP: claude mcp add --transport http shrine http://127.0.0.1:<port>/mcp '
              f'--header "Authorization: Bearer $(cat {STATE / "token"})"', flush=True)
    return root, ['/' + context['node'] + '/io/mcp', value]
