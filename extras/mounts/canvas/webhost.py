"""Loopback authentication and transport only. Domain decisions execute in Foil."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie
from pathlib import Path
import hmac
import json
import os
import secrets
import threading
import urllib.error
import urllib.parse
import urllib.request

ASSETS = {'/': 'index.html', '/canvas': 'index.html', '/canvas.css': 'canvas.css',
          '/canvas-client.js': 'canvas-client.js',
          '/canvas-inspector.js': 'canvas-inspector.js', '/native-surfaces.js': 'native-surfaces.js',
          '/presentation-experiment.js': 'presentation-experiment.js',
          '/infinite-canvas.js': 'infinite-canvas.js', '/canvas-space.mjs': 'canvas-space.mjs',
          '/surface-state.mjs': 'surface-state.mjs', '/inspection-state.mjs': 'inspection-state.mjs'}
# Explicit shared assets, without enabling Explorer's development HTTP routes.
GOO_ASSETS = {'/static/goo-reference.css': 'reference.css', '/static/goo-fonts.css': 'ascii-fonts.css'}
GOO_ASSETS.update({'/static/goo-' + name + '.ttf': 'goo-' + name + '.ttf'
                   for name in ('Sans400','Sans520','Sans550','Sans620','Sans650','Sans750','Mono400','Italic400')})
MAX_BODY = 64 * 1024
SESSION_AGE = 90 * 24 * 60 * 60

def new_browser_session():
    return {'version': 1, 'id': secrets.token_hex(16),
            'bootstrap': secrets.token_hex(32), 'admin': secrets.token_hex(32)}

def browser_session(path):
    """Host-only browser identity; restarts must not revoke ordinary access.

    Each world has a different cookie name. Cookies are not scoped by TCP port,
    so a disposable world's login must never overwrite the development login.
    This file is deliberately outside the native namespace and source closure.
    """
    path = Path(path)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd) as stream:
            stat = os.fstat(stream.fileno())
            if stat.st_uid != os.getuid() or stat.st_mode & 0o077:
                raise ValueError('Canvas browser session must be private to its local owner.')
            value = json.load(stream)
    else:
        value = new_browser_session()
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream)
            stream.flush(); os.fsync(stream.fileno())
    if value.get('version') != 1 or any(
        not isinstance(value.get(key), str) or len(value[key]) != size or
        any(char not in '0123456789abcdef' for char in value[key])
        for key, size in [('id', 32), ('bootstrap', 64), ('admin', 64)]):
        raise ValueError('Canvas browser session is invalid; refusing to replace existing authority.')
    return value

class Server(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, root, backend, authority, port=0, session=None):
        super().__init__(('127.0.0.1', port), Handler)
        self.root, self.backend, self.authority = Path(root), backend, authority
        session = session or new_browser_session()
        self.cookie_name = 'grove_' + session['id']
        self.bootstrap, self.admin = session['bootstrap'], session['admin']
        self.agent = secrets.token_hex(32)
        self.origin = 'http://127.0.0.1:' + str(self.server_port)
        self.lock = threading.Lock()
    def call(self, principal, operation, expected, event, body):
        fields = dict(credential=self.authority, principal=principal, operation=operation,
                      expected=str(expected), event=event, body=json.dumps(body, separators=(',', ':')))
        data = urllib.parse.urlencode(fields).encode()
        request = urllib.request.Request(self.backend + '/canvas-native', data,
            {'Content-Type': 'application/x-www-form-urlencoded'})
        with self.lock:
            try:
                with urllib.request.urlopen(request, timeout=45) as response:
                    return response.status, response.read(MAX_BODY * 32)
            except urllib.error.HTTPError as error:
                return error.code, error.read(MAX_BODY * 32)

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Never log credentials, user content or authenticated URLs.
    def reply(self, code, body, content_type='application/json', headers=None):
        if not isinstance(body, bytes):
            body = json.dumps(body).encode()
        try:
            self.send_response(code)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src "+getattr(self,'image_sources',"'self'")+"; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            for name, value in (headers or {}).items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            # Reloading/closing a canvas can abandon an in-flight response.
            # The native outcome stands; do not retry it or send a second reply.
            self.close_connection = True
    def principal(self):
        token = self.headers.get('Authorization', '')
        if hmac.compare_digest(token, 'Bearer ' + self.server.agent):
            return 'agent'
        cookies = SimpleCookie()
        try:
            cookies.load(self.headers.get('Cookie', ''))
        except Exception:
            return None
        value = cookies.get(self.server.cookie_name)
        if value and hmac.compare_digest(value.value, self.server.admin):
            return 'administrator'
    def valid_host(self):
        return self.headers.get('Host') == '127.0.0.1:' + str(self.server.server_port)
    def do_GET(self):
        if not self.valid_host():
            return self.reply(403, {'error': 'Invalid host'})
        route = urllib.parse.urlsplit(self.path).path
        if route in ASSETS or route in GOO_ASSETS:
            path = (self.server.root / ASSETS[route]) if route in ASSETS else (self.server.root.parent / 'goo' / 'static' / GOO_ASSETS[route])
            kind = {'html':'text/html; charset=utf-8', 'css':'text/css', 'js':'text/javascript', 'mjs':'text/javascript', 'ttf':'font/ttf'}[path.suffix[1:]]
            return self.reply(200, path.read_bytes(), kind)
        if not self.principal():
            return self.reply(401, {'error': 'Open Grove Canvas from Applications to connect this browser.'})
        if route == '/source':
            code, data = self.server.call(self.principal(), 'source', '0', '', {})
            if code != 200:
                return self.reply(code, {'error':'Pinned native source is unavailable'})
            return self.reply(200, json.loads(data)['source'].encode(), 'text/plain; charset=utf-8')
        if route == '/api':
            return self.forward(self.principal(), {'operation':'read', 'expected':'0', 'body':{}})
        return self.reply(404, {'error':'Unknown route'})
    def do_POST(self):
        if not self.valid_host():
            return self.reply(403, {'error':'Invalid host'})
        if self.headers.get('Transfer-Encoding'):
            return self.reply(400, {'error':'Unsupported body encoding'})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= MAX_BODY:
                return self.reply(413, {'error':'Request too large or empty'})
            payload = json.loads(self.rfile.read(size))
            if not isinstance(payload, dict):
                raise ValueError()
        except (ValueError, UnicodeError):
            return self.reply(400, {'error':'Invalid request'})
        if self.path == '/session':
            if self.headers.get('Origin') != self.server.origin:
                return self.reply(403, {'error':'Origin required'})
            token = payload.get('token', '')
            if not isinstance(token, str) or not hmac.compare_digest(token, self.server.bootstrap):
                return self.reply(403, {'error':'Invalid session link'})
            return self.reply(200, {'connected':True}, headers={
                'Set-Cookie':f'{self.server.cookie_name}={self.server.admin}; Max-Age={SESSION_AGE}; HttpOnly; SameSite=Strict; Path=/'})
        principal = self.principal()
        if not principal:
            return self.reply(401, {'error':'Authentication required'})
        if principal == 'administrator' and self.headers.get('Origin') != self.server.origin:
            return self.reply(403, {'error':'Origin required'})
        if self.path != '/api':
            return self.reply(404, {'error':'Unknown route'})
        operation = payload.get('operation')
        allowed = {'read','present','source','context','evaluate','stage','demonstrate'} if principal == 'agent' else {
            'read','present','source','context','evaluate','stage','demonstrate','publish','discard','reserve','construct','perform'}
        if operation not in allowed:
            return self.reply(403, {'error':'Action is outside this connection’s authority'})
        return self.forward(principal, payload)
    def forward(self, principal, payload):
        try:
            expected = str(payload.get('expected', '0'))
            event = payload.get('event', '')
            body = payload.get('body', {})
            if not expected.isdecimal() or len(expected) > 40 or not isinstance(event, str) or len(event)>80 or not isinstance(body,dict):
                return self.reply(400, {'error':'Invalid native envelope'})
            code, data = self.server.call(principal, payload['operation'], expected, event, body)
            try:
                decoded = json.loads(data)
            except ValueError:
                return self.reply(502, {'error':'Native response was not a frame', 'status':code})
            return self.reply(code, decoded)
        except (OSError, TimeoutError, urllib.error.URLError):
            return self.reply(503, {'error':'Native owner is starting or unavailable. Your installed world is preserved.'})
