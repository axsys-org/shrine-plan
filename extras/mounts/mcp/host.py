"""The host side: the bearer token, and a loopback companion for the two
things a world cannot do itself yet: write a mount's source file into the
checkout, and wait a moment.

The token lives in ~/.local/share/shrine/mcp/token, owner-only.  The worker
keeps it in memory and compares it with each request's Authorization
header; it is never written to a record.
"""
import json
import os
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

STATE = Path.home() / '.local/share/shrine/mcp'
MOUNTS = Path(__file__).resolve().parent.parent


def token():
    STATE.mkdir(parents=True, exist_ok=True)
    os.chmod(STATE, 0o700)
    path = STATE / 'token'
    if not path.exists():
        path.write_text(secrets.token_urlsafe(32) + '\n')
        os.chmod(path, 0o600)
    return path.read_text().strip()


def declared(mount):
    """The files a mount's manifest names.  Only these may be written."""
    manifest = json.loads((MOUNTS / mount / 'mount.json').read_text())
    names = set(manifest.get('modules', {}).values())
    for unit in manifest.get('grove', []):
        names.update(unit.get('files', []))
    return names


class Companion(BaseHTTPRequestHandler):
    key = ''

    def log_message(self, *args):
        pass

    def answer(self, status, body):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path == '/sleep':
            ms = min(int(parse_qs(url.query).get('ms', ['250'])[0]), 5000)
            time.sleep(ms / 1000)
            return self.answer(200, {'slept': ms})
        self.answer(404, {'error': 'unknown'})

    def do_POST(self):
        if self.headers.get('X-Token') != self.key:
            return self.answer(401, {'error': 'bad token'})
        length = int(self.headers.get('Content-Length', '0'))
        try:
            body = json.loads(self.rfile.read(length))
            mount, name, text = body['mount'], body['name'], body['text']
        except (ValueError, KeyError):
            return self.answer(400, {'error': 'mount, name and text are needed'})
        if self.path != '/file' or '/' in mount or '/' in name or not (MOUNTS / mount / 'mount.json').is_file():
            return self.answer(404, {'error': 'no such mount'})
        if name not in declared(mount):
            return self.answer(409, {'error': f'{name} is not a file of {mount}; adding a file needs mount.json and a restart'})
        (MOUNTS / mount / name).write_text(text)
        self.answer(200, {'ok': True, 'bytes': len(text.encode())})


def prepare(root, work, check, cleanup, context):
    value = 'check' if check else token()
    Companion.key = secrets.token_urlsafe(24)
    server = HTTPServer(('127.0.0.1', 0), Companion)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    cleanup.callback(server.shutdown)
    if not check:
        print('MCP: claude mcp add --transport http shrine http://127.0.0.1:<port>/mcp '
              f'--header "Authorization: Bearer $(cat {STATE / "token"})"', flush=True)
    return root, ['/' + context['node'] + '/io/mcp', value,
                  f'http://127.0.0.1:{server.server_address[1]}', Companion.key]
