"""The links hand: what points at a record, answered from memory instead of by walking the world.

The kernel's `referencing` read walks the whole world on every call (about 700 ms each, eighteen calls for one record
with scraped pages in the world). This hand reads each folder once at start, keeps every reference it finds as
target -> [(source, slot)], and follows the stream: a touched record is read again and its references replaced. It
writes nothing to the world; it answers over HTTP:

    GET http://127.0.0.1:8312/links?to=/0x11/user/orgs/a16z
    -> {"to": ..., "matches": [{"path": ..., "slot": ..., "cell": bool, "hole": bool}], "ready": true}

Scanned: every folder under /user except web (scraped pages and their regions hold no references to things), and every
chat under /agent (contexts, asks, found rows). Research trails and hand bookkeeping are left out.

    python3 links.py <base> [--node 0x11] [--port 8312]
"""
import importlib.util
import json
import os
import re
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_spec = importlib.util.spec_from_file_location('hand_base', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hand.py'))
_hand = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_hand)
Hand, World = _hand.Hand, _hand.World

SKIP_USER = {'web'}
CHAT = re.compile(r'[a-z]\d*$')
REF = re.compile(r'^/h/([xyz])/(\d+)/\d+(/.*)$')


def target_of(value):
    """The record a slot value points at, or None: a reference spelled /h/<care>/<case>/<len>/<path>, a cell's /x/...
    or /c/x/... path folded onto the cell itself, or a bare /0x.. path."""
    if not isinstance(value, str):
        return None
    m = REF.match(value.strip())
    path = m.group(3) if m else (value.strip() if re.match(r'^/0x[0-9a-f]+/', value.strip()) else None)
    if not path:
        return None
    for prefix in ('/c/x/', '/x/'):
        if path.startswith(prefix):
            path = '/' + path[len(prefix):]
    return path.rstrip('/')


class Index:
    def __init__(self):
        self.lock = threading.Lock()
        self.into = {}          # target -> {(source, slot): (cell, hole)}
        self.out = {}           # source -> [(target, slot)]
        self.ready = False

    def put(self, source, props):
        """Replace everything this source points at with what props hold now (props None: the record is gone)."""
        cell = bool(props) and '/sys/weft' in props
        hole = '/holes/' in source
        refs = []
        for k, v in (props or {}).items():
            if k in ('/sys/weft',):
                continue
            t = target_of(v)
            if t and t != source:
                refs.append((t, k.lstrip('/')))
        with self.lock:
            for t, slot in self.out.pop(source, []):
                d = self.into.get(t)
                if d:
                    d.pop((source, slot), None)
                    if not d:
                        del self.into[t]
            if refs:
                self.out[source] = refs
                for t, slot in refs:
                    self.into.setdefault(t, {})[(source, slot)] = (cell, hole)

    def links(self, to):
        to = to.rstrip('/')
        with self.lock:
            hits = list(self.into.get(to, {}).items())
        return [{'path': s, 'slot': slot, 'cell': c, 'hole': h} for (s, slot), (c, h) in sorted(hits)
                if s != to and not s.startswith(to + '/')]


INDEX = Index()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path != '/links':
            self.send_response(404); self.end_headers(); return
        to = (urllib.parse.parse_qs(u.query).get('to') or [''])[0]
        if to and not to.startswith('/'):
            to = '/' + to
        body = json.dumps({'to': to, 'matches': INDEX.links(to) if to else [], 'ready': INDEX.ready}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json'); self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(body))); self.end_headers()
        self.wfile.write(body)


class LinksHand(Hand):
    name = 'links'
    every = 3600.0

    def __init__(self, world, log=print, **overrides):
        super().__init__(world, log=log, **overrides)
        self.node = '/' + world.node
        # start from where the other hands are: the index is rebuilt from the world itself, not replayed from history
        marks = [int(float((self.w.read(f'{self.node}/agent/hands/{h}/seen', 'x').get('properties') or {}).get('/epoch') or 0))
                 for h in _hand.HANDS]
        self.seen = self.marked = max([self.seen] + marks)
        port = int(self.setting('port') or 8312)
        server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.log(f'links: answering on http://127.0.0.1:{port}/links?to=<path>')

    def roots(self):
        out = []
        for c in self.w.read(self.node + '/user', 'y', limit=2000).get('children') or []:
            if c['path'].rsplit('/', 1)[1] not in SKIP_USER:
                out.append(c['path'])
        for c in self.w.read(self.node + '/agent', 'y', limit=2000).get('children') or []:
            if CHAT.fullmatch(c['path'].rsplit('/', 1)[1]):
                out.append(c['path'])
        return out

    def scanned(self, path):
        rel = path[len(self.node):]
        if rel.startswith('/user/'):
            return rel.split('/')[2] not in SKIP_USER
        if rel.startswith('/agent/'):
            return bool(CHAT.fullmatch(rel.split('/')[2]))
        return False

    def build(self):
        t0, n = time.time(), 0
        for root in self.roots():
            nxt = None
            for _ in range(200):
                page = self.w.read(root, 'z', limit=2000, **({'next': nxt} if nxt else {}))
                stack = [page]
                while stack:
                    node = stack.pop()
                    if node.get('exists'):
                        INDEX.put(node['path'], node.get('properties') or {}); n += 1
                    stack.extend(node.get('children') or [])
                nxt = page.get('next')
                if not nxt:
                    break
        INDEX.ready = True
        self.log(f'links: {n} records read, {len(INDEX.into)} records pointed at, in {time.time() - t0:.1f}s')

    # writes nothing, so every line is worth reading, a hand's or a person's
    def quiet(self, item):
        touched = item.get('touched') or []
        return not any(self.scanned(t) for t in touched)

    def mark_seen(self):
        pass

    def line(self, line):
        if not INDEX.ready:
            return 0
        for t in line.get('touched') or []:
            if not self.scanned(t):
                continue
            rec = self.w.read(t, 'x')
            INDEX.put(t, (rec.get('properties') or {}) if rec.get('exists') else None)
        return 0

    def tick(self, now):
        if not INDEX.ready:
            self.build()
        return 0


if __name__ == '__main__':
    _hand.run(LinksHand, settings=('port',))
