"""The host side: the bearer token, and a loopback companion for the two
things a world cannot do itself yet: write a mount's source file into the
checkout, and wait a moment.

The token lives in ~/.local/share/shrine/mcp/token, owner-only.  The worker
keeps it in memory and compares it with each request's Authorization
header; it is never written to a record.
"""
import json
import os
import re
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

STATE = Path.home() / '.local/share/shrine/mcp'
MOUNTS = Path(__file__).resolve().parent.parent
ARCHIVES = Path.home() / '.local/share/shrine/source-archives'


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


NAME = re.compile(r'^[a-z][a-z0-9-]{0,63}$')


def new_mount(name, manifest=None, files=None):
    """A fresh mount folder in the checkout. With no manifest: one empty Foil
    module, no Grove, no dependencies, for the agent to fill with insert-file.
    With a manifest: that mount.json and the files given; a module or Grove
    file the manifest names but the files leave out gets a stub."""
    folder = MOUNTS / name
    if folder.exists():
        raise FileExistsError(name)
    module = name.replace('-', '_')
    if manifest is None:
        data = {"version": 1, "name": name, "dependencies": [],
                "modules": {module: "main.foil"}, "roots": [["lib", module]]}
    else:
        data = json.loads(manifest)
        if data.get('name') != name:
            raise ValueError('the manifest names a different mount')
        if data.get('dependencies'):
            raise ValueError('a mount made after boot cannot declare dependencies')
        if data.get('host'):
            raise ValueError('a mount made after boot cannot bring a host hook')
    files = dict(files or {})
    for leaf in data.get('modules', {}).values():
        files.setdefault(leaf, f"'  {name}: made by mcp/new-mount. Replace with insert-file.\n"
                               f"+ {module}\n  + ready\n    \\ ignored=nat\n    ^ nat\n    1\n")
    for unit in data.get('grove', []):
        for leaf in unit.get('files', []):
            files.setdefault(leaf, '')
    for leaf in files:
        if '/' in leaf or leaf.startswith('.'):
            raise ValueError(f'bad file name {leaf}')
    folder.mkdir()
    (folder / 'mount.json').write_text(json.dumps(data, indent=2) + '\n')
    for leaf, text in files.items():
        (folder / leaf).write_text(text)
    return folder


def archive_mount(name):
    """Move a mount's folder out of the checkout into the source archive."""
    folder = MOUNTS / name
    if not folder.is_dir():
        return None
    ARCHIVES.mkdir(parents=True, exist_ok=True)
    target = ARCHIVES / f"{name}-{time.strftime('%Y%m%d-%H%M%S')}"
    folder.rename(target)
    return str(target)


class Companion(BaseHTTPRequestHandler):
    key = ''
    context = {}

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
        if self.path == '/mount':
            return self.mount(length)
        if self.path == '/unmount':
            return self.unmount(length)
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


    def mount(self, length):
        """Create a mount folder and stage it with Eden's file bridge; the world
        is then asked to load it (the worker sends the mount card)."""
        try:
            body = json.loads(self.rfile.read(length))
            name = body['name']
        except (ValueError, KeyError):
            return self.answer(400, {'error': 'name is needed'})
        if not NAME.match(name):
            return self.answer(400, {'error': 'a mount name is lowercase letters, digits and hyphens'})
        scanner = self.context.get('scanner')
        if scanner is None:
            return self.answer(503, {'error': 'no file bridge; the world was started without mounts'})
        manifest = body.get('manifest') or None
        files = body.get('files') if isinstance(body.get('files'), dict) else None
        try:
            new_mount(name, manifest, files)
        except FileExistsError:
            return self.answer(409, {'error': f'{name} already exists in the checkout'})
        except ValueError as error:
            return self.answer(400, {'error': str(error)})
        try:
            from eden_mounts import catalog
            mount = catalog(self.context['extras'])[name]
            spec = scanner.add(mount, self.context['work'], self.context['cleanup'], self.context)
        except (ValueError, KeyError, OSError) as error:
            return self.answer(500, {'error': str(error)})
        self.answer(200, {'name': name, 'spec': spec})

    def unmount(self, length):
        """Forget a mount on the host: the bridge stops serving it and its
        folder moves to the source archive."""
        try:
            name = json.loads(self.rfile.read(length))['name']
        except (ValueError, KeyError):
            return self.answer(400, {'error': 'name is needed'})
        if not NAME.match(name) or name == 'mcp':
            return self.answer(400, {'error': 'not a mount that can be unloaded'})
        scanner = self.context.get('scanner')
        try:
            if scanner is not None:
                scanner.remove(name)
        except ValueError as error:
            return self.answer(404, {'error': str(error)})
        archived = archive_mount(name)
        self.answer(200, {'name': name, 'archived': archived})


def prepare(root, work, check, cleanup, context):
    value = 'check' if check else token()
    Companion.key = secrets.token_urlsafe(24)
    Companion.context = context
    server = HTTPServer(('127.0.0.1', 0), Companion)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    cleanup.callback(server.shutdown)
    if not check:
        print('MCP: claude mcp add --transport http shrine http://127.0.0.1:<port>/mcp '
              f'--header "Authorization: Bearer $(cat {STATE / "token"})"', flush=True)
    return root, ['/' + context['node'] + '/io/mcp', value,
                  f'http://127.0.0.1:{server.server_address[1]}', Companion.key]
