#!/usr/bin/env python3
"""Serve the experiment viewer and proxy its calls to the local Shrine world."""
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
EXPLORER = ROOT.parents[1] / 'mounts' / 'explorer'
UPSTREAM = 'http://127.0.0.1:8148/mcp'


class Handler(BaseHTTPRequestHandler):
    def respond(self, status, body, content_type):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlsplit(self.path).path
        files = {'/': ROOT / 'viewer.html', '/live': EXPLORER / 'goo-live.html',
                 '/static/goo-live.js': EXPLORER / 'goo-live.js',
                 '/static/goo-live.css': EXPLORER / 'goo-live.css'}
        if path == '/static/goo-profile.css':
            return self.respond(200, b'', 'text/css')
        if path not in files:
            return self.respond(404, b'Not found', 'text/plain')
        file = files[path]
        self.respond(200, file.read_bytes(), mimetypes.guess_type(str(file))[0] or 'text/plain')

    def do_POST(self):
        if self.path != '/mcp':
            return self.respond(404, b'Not found', 'text/plain')
        body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
        try:
            with urlopen(Request(UPSTREAM, body, {'Content-Type': 'application/json'}), timeout=180) as r:
                self.respond(r.status, r.read(), r.headers.get('Content-Type', 'application/json'))
        except HTTPError as e:
            self.respond(e.code, e.read(), 'application/json')
        except URLError as e:
            self.respond(503, json.dumps({'error': {'message': str(e)}}).encode(), 'application/json')


if __name__ == '__main__':
    print('Branchmap viewer: http://127.0.0.1:8149', flush=True)
    ThreadingHTTPServer(('127.0.0.1', 8149), Handler).serve_forever()
