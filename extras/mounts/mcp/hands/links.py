"""The links hand: the index. Every reference, every name, every mention, in memory, current with the stream.

Three things, answered in milliseconds over HTTP and never by walking the world:

  references   who points at a record, and on which slot (explicit references in slots)
  aliases      every spelling of every thing: its name, its slug, its aliases slot, its domain, its handle
  mentions     which things a text refers to, found by scanning the text against the aliases: no model

At write time, every new text (a turn's said, a found row, a page region, a document paragraph, a note) is scanned,
and the things it names are written beside it as <text>/mentions {slug: reference, ...}, signed links. A record's
"pointing here" then includes "mentioned" as well as explicit slots: the tree under a thing grows from writes made
elsewhere by people who only named it. Names that match nothing are kept as candidates, by source and by count,
for a person or an agent to accept as a new starter place (one record, its subtree to come) or ignore.

    GET /links?to=<path>         [{path, slot, cell, hole}]           everything pointing at a record
    GET /by?to=<path>            {slot: [{path, ...}]}                the same, grouped by slot ("mentioned" for mentions)
    GET /resolve?text=...        [{path, name, span}]                 what a text refers to
    GET /candidates?in=<path>    [{name, count, sources}]             unresolved names in one text, or everywhere

    python3 links.py <base> [--node 0x11] [--port 8312]
"""
import hashlib
import importlib.util
import json
import os
import re
import threading
import time
import urllib.parse
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_spec = importlib.util.spec_from_file_location('hand_base', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hand.py'))
_hand = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_hand)
Hand, World, segment_of = _hand.Hand, _hand.World, _hand.segment_of

CHAT = re.compile(r'[a-z]\d*$')
TALK_TURN = re.compile(r'^(/0x[0-9a-f]+/(?:user|agent)(?:/.+)?/talk)/turns/t(\d+)$')
REF = re.compile(r'^/h/([xyz])/(\d+)/\d+(/.*)$')
TEXT_SLOTS = ('/said', '/text', '/quote', '/note', '/notes', '/title', '/heading', '/asked', '/description', '/summary', '/body')
# a thing's record lives at /user/<kind>/<slug>; what hangs under it (holes, repos, articles, views) is not a thing
THING = re.compile(r'^/0x[0-9a-f]+/user/(?!web/|views/|sources/)[a-z_]+/[a-z][a-z0-9_]*$')
# words that are somebody's name but also a word; a single-word alias must be capitalised in the text to count
COMMON = set('''the a an and or of to in on at by for with from as is are was were be been it its this that these those he
she they we you i his her their our your who what when where why how all any some no not but if then than so very can
will may might must should would could do does did done has have had make made new old one two first last next
january february march april may june july august september october november december monday tuesday wednesday
thursday friday saturday sunday mr mrs ms dr jr sr inc llc ltd corp co vs etc'''.split())
NOISE = re.compile(r'^(U\.?S\.?A?|UK|EU|UN|ID|OK|AM|PM|[A-Z]\.?)$')


def norm_name(n):
    return re.sub(r'[^a-z0-9]+', ' ', re.sub(r"['’]s\b", '', str(n).lower())).strip()


def target_of(value):
    """The record a slot value points at: a reference /h/<care>/<case>/<len>/<path>, a cell's /x or /c/x path folded
    onto the cell, or a bare /0x.. path; else None."""
    if not isinstance(value, str):
        return None
    s = value.strip()
    m = REF.match(s)
    path = m.group(3) if m else (s if re.match(r'^/0x[0-9a-f]+/', s) else None)
    if not path:
        return None
    for prefix in ('/c/x/', '/x/'):
        if path.startswith(prefix):
            path = '/' + path[len(prefix):]
    return path.rstrip('/')


def norm_words(text):
    """(word, capitalised?) pairs, lowercased, so matching ignores case and punctuation but remembers capitals."""
    out = []
    for w in re.findall(r"[A-Za-z0-9][A-Za-z0-9'’.\-]*", str(text)):
        w = re.sub(r"['’]s$", '', w).rstrip(".'’-")          # Yarvin’s is Yarvin
        if w:
            out.append((w.lower(), w[0].isupper()))
    return out


def alias_keys(record):
    """Every spelling of a thing, as word tuples: name, slug, aliases, domain, handle."""
    out = set()
    path, props = record['path'], record.get('properties') or {}
    slug = path.rsplit('/', 1)[1]
    names = [slug.replace('_', ' '), props.get('/name')] + [a.strip() for a in str(props.get('/aliases') or '').split(',')]
    for n in names:
        if not n:
            continue
        n = str(n)
        inner = re.search(r'\(([^)]+)\)', n)          # "Axiomatic Systems (AxSys)" is two names
        if inner:
            names.append(inner.group(1)); n = n[:inner.start()].strip()
        words = tuple(w for w, _ in norm_words(n))
        if words and (len(words) > 1 or (len(words[0]) >= 3 and words[0] not in COMMON)):
            out.add(words)
        if '/people/' in path and len(words) > 1 and len(words[-1]) >= 4 and words[-1] not in COMMON:
            out.add((words[-1],))                    # a person by surname alone, when the text capitalises it
    for k in ('/website', '/url', '/site', '/domain', '/handle', '/github', '/twitter'):
        v = str(props.get(k) or '').strip().lower()
        if not v:
            continue
        host = re.sub(r'^https?://(www\.)?', '', v).split('/')[0]
        if host and '.' in host:
            out.add((host,))
        if v.startswith('@') or k in ('/handle', '/twitter'):
            out.add((v.lstrip('@'),))
    return out


class Index:
    def __init__(self):
        self.lock = threading.Lock()
        self.into = {}          # target -> {(source, slot): (cell, hole)}
        self.out = {}           # source -> [(target, slot)]
        self.alias = {}         # words tuple -> set(record path)
        self.aliases_of = {}    # record -> set(words tuple)
        self.names = {}         # record -> display name
        self.longest = 1
        self.candidates = {}    # source -> [name, ...]
        self.by_name = {}       # normalised name -> set(source): which texts name an unknown thing
        self.dismissed = set()  # names the agent decided are not things
        self.queued = set()     # names handed to the agent and not yet settled
        self.talks = {}         # talk folder -> {n, who}: the latest turn of every talk at a record, so none is lost
        self.ready = False

    # ---- references
    def put_refs(self, source, props):
        cell = bool(props) and '/sys/weft' in props
        hole = False
        refs = []
        for k, v in (props or {}).items():
            if k == '/sys/weft':
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

    # ---- aliases
    def put_thing(self, record):
        path, props = record['path'], record.get('properties')
        keys = alias_keys(record) if props is not None else set()
        with self.lock:
            for k in self.aliases_of.pop(path, set()):
                s = self.alias.get(k)
                if s:
                    s.discard(path)
                    if not s:
                        del self.alias[k]
            if keys:
                self.aliases_of[path] = keys
                self.names[path] = str((props or {}).get('/name') or path.rsplit('/', 1)[1].replace('_', ' '))
                for k in keys:
                    self.alias.setdefault(k, set()).add(path)
                    self.longest = max(self.longest, len(k))
            else:
                self.names.pop(path, None)

    def resolve(self, text):
        """Longest match of the aliases over the text; a single-word alias needs a capital or a dot in the text."""
        words = norm_words(text)
        found, i = [], 0
        with self.lock:
            while i < len(words):
                hit = None
                for n in range(min(self.longest, len(words) - i), 0, -1):
                    key = tuple(w for w, _ in words[i:i + n])
                    paths = self.alias.get(key)
                    if paths and (n > 1 or words[i][1] or '.' in key[0] or any(ch.isdigit() for ch in key[0])):
                        hit = (key, paths, n); break
                if hit:
                    key, paths, n = hit
                    best = max(paths, key=lambda p: (len(self.out.get(p, [])), -len(p)))   # the richer record, else the shorter path
                    found.append({'path': best, 'name': self.names.get(best, ' '.join(key)), 'span': ' '.join(key), 'ambiguous': len(paths) > 1})
                    i += n
                else:
                    i += 1
        return found

    def unresolved(self, text, resolved):
        """Capitalised runs that matched nothing: two words or more anywhere, or one word not opening its sentence.
        A resolved name breaks a run, so the words around it are not glued to it."""
        taken = {r['span'].lower() for r in resolved}
        out = []
        for sentence in re.split(r'[.!?]\s+|\n|[,;:()\[\]"“”]', str(text)):
            toks = [re.sub(r"['’]s$", '', t).rstrip(".'’-") for t in re.findall(r"[A-Za-z0-9][A-Za-z0-9'’.\-]*", sentence)]
            toks = [t for t in toks if t]
            low = [t.lower() for t in toks]
            # mark every word that belongs to a resolved span
            inside = [False] * len(toks)
            for span in taken:
                ws = span.split()
                for i in range(len(toks) - len(ws) + 1):
                    if low[i:i + len(ws)] == ws:
                        for j in range(i, i + len(ws)):
                            inside[j] = True
            run = []
            for i, t in enumerate(toks + ['']):
                if t and not inside[i] and t[0].isupper() and not NOISE.match(t) and (t.lower() not in COMMON or (i > 0 and i + 1 < len(toks) and toks[i + 1][:1].isupper() and not inside[i + 1])):
                    run.append((i, t)); continue
                if run:
                    # a run right after a resolved name is the rest of a longer name: Urbit Foundation, Tlon Messenger
                    j = run[0][0] - 1
                    lead = []
                    while j >= 0 and inside[j] and toks[j][0].isupper():
                        lead.insert(0, toks[j]); j -= 1
                    name = ' '.join(lead + [w for _, w in run])
                    if (len(run) + len(lead) > 1 or run[0][0] > 0) and name.lower() not in taken and len(name) >= 3 and not name.replace('.', '').isdigit():
                        out.append(name)
                run = []
        return list(dict.fromkeys(out))

    # ---- kept on disk between runs, so a restart loads in a second and catches up from the stream
    def dump(self):
        with self.lock:
            return {'dismissed': sorted(self.dismissed), 'queued': sorted(self.queued), 'talks': self.talks,'into': [[t, [[s_, slot, c, h] for (s_, slot), (c, h) in d.items()]] for t, d in self.into.items()],
                    'out': {s_: [[t, slot] for t, slot in refs] for s_, refs in self.out.items()},
                    'alias': [[list(k), sorted(v)] for k, v in self.alias.items()],
                    'aliases_of': {p_: [list(k) for k in ks] for p_, ks in self.aliases_of.items()},
                    'names': self.names, 'longest': self.longest, 'candidates': self.candidates}

    def load(self, d):
        with self.lock:
            self.into = {t: {(s_, slot): (c, h) for s_, slot, c, h in rows} for t, rows in d['into']}
            self.out = {s_: [(t, slot) for t, slot in refs] for s_, refs in d['out'].items()}
            self.alias = {tuple(k): set(v) for k, v in d['alias']}
            self.aliases_of = {p_: {tuple(k) for k in ks} for p_, ks in d['aliases_of'].items()}
            self.names, self.longest, self.candidates = d['names'], d['longest'], d['candidates']
            self.dismissed, self.queued = set(d.get('dismissed') or []), set(d.get('queued') or [])
            self.talks = d.get('talks') or {}
            self.by_name = {}
            for src, names in self.candidates.items():
                for n in names:
                    self.by_name.setdefault(norm_name(n), set()).add(src)

    def links(self, to):
        to = to.rstrip('/')
        with self.lock:
            hits = list(self.into.get(to, {}).items())
        return [{'path': s, 'slot': slot, 'cell': c, 'hole': h} for (s, slot), (c, h) in sorted(hits) if s != to and not s.startswith(to + '/')]

    def by(self, to):
        out = {}
        for m in self.links(to):
            slot = 'mentioned' if m['path'].endswith('/mentions') else m['slot']
            path = m['path'][:-len('/mentions')] if m['path'].endswith('/mentions') else m['path']
            out.setdefault(slot, []).append(dict(m, path=path))
        return out

    # ---- the hierarchy, computed: containment is the in slot; the tree is read from the references, never from paths
    IN_SLOTS = ('in', 'within', 'part_of', 'parent')

    def contents(self, at, depth=3, seen=None):
        """The things inside a thing: every record whose in points at it (older spellings too), and the physical
        children that are things of their own; nested to depth."""
        at = at.rstrip('/')
        seen = seen if seen is not None else set()
        out = []
        with self.lock:
            members = sorted({s_ for (s_, slot), _ in self.into.get(at, {}).items() if slot in self.IN_SLOTS and not s_.endswith('/mentions')})
            kids = sorted(p for p in self.names if p.startswith(at + '/') and p.count('/') == at.count('/') + 1)
        for m in members + [k for k in kids if k not in members]:
            if m in seen or m == at:
                continue
            seen.add(m)
            node = {'path': m, 'name': self.names.get(m, m.rsplit('/', 1)[1].replace('_', ' ')), 'kind': m.split('/user/')[1].split('/')[0] if '/user/' in m else ''}
            if depth > 1:
                node['children'] = self.contents(m, depth - 1, seen)
            out.append(node)
        return out

    def chain(self, at):
        """Upward: what a thing is in, then what that is in, to the top; a cycle stops it."""
        out, cur, seen = [], at.rstrip('/'), set()
        while cur and cur not in seen:
            seen.add(cur)
            nxt = None
            with self.lock:
                for t, slot in self.out.get(cur, []):
                    if slot in self.IN_SLOTS:
                        nxt = t; break
            if not nxt:
                break
            out.append({'path': nxt, 'name': self.names.get(nxt, nxt.rsplit('/', 1)[1].replace('_', ' '))}); cur = nxt
        return out

    def shape(self):
        """The world's shape in a few lines: each kind, how many things, how many are top-level (in nothing)."""
        kinds = {}
        with self.lock:
            for p in self.names:
                if '/user/' not in p:
                    continue
                kind = p.split('/user/')[1].split('/')[0]
                k = kinds.setdefault(kind, {'things': 0, 'roots': 0})
                k['things'] += 1
                if not any(slot in self.IN_SLOTS for _, slot in self.out.get(p, [])):
                    k['roots'] += 1
        return kinds

    def top_candidates(self, limit=60):
        c = Counter()
        srcs = {}
        with self.lock:
            for s, names in self.candidates.items():
                for n in names:
                    c[n] += 1; srcs.setdefault(n, []).append(s)
        return [{'name': n, 'count': k, 'sources': srcs[n][:6]} for n, k in c.most_common(limit)]


INDEX = Index()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        to = q.get('to', '')
        if to and not to.startswith('/'):
            to = '/' + to
        if u.path == '/links':
            body = {'to': to, 'matches': INDEX.links(to) if to else [], 'ready': INDEX.ready}
        elif u.path == '/by':
            body = {'to': to, 'by': INDEX.by(to) if to else {}, 'ready': INDEX.ready}
        elif u.path == '/resolve':
            body = {'matches': INDEX.resolve(q.get('text', '')), 'ready': INDEX.ready}
        elif u.path == '/tree':
            body = {'at': to, 'in': INDEX.chain(to) if to else [], 'contents': INDEX.contents(to, int(q.get('depth') or 3)) if to else [], 'ready': INDEX.ready}
        elif u.path == '/shape':
            body = {'kinds': INDEX.shape(), 'ready': INDEX.ready}
        elif u.path == '/talks':
            body = {'talks': [{'folder': f, **v} for f, v in sorted(INDEX.talks.items())], 'ready': INDEX.ready}
        elif u.path == '/candidates':
            src = q.get('in', '')
            src = ('/' + src.lstrip('/')) if src else ''
            body = {'candidates': ([{'name': n, 'count': 1, 'sources': [src]} for n in INDEX.candidates.get(src, [])] if src else INDEX.top_candidates()), 'ready': INDEX.ready}
        else:
            self.send_response(404); self.end_headers(); return
        data = json.dumps(body).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json'); self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(data))); self.end_headers()
        self.wfile.write(data)


class LinksHand(Hand):
    name = 'links'
    every = 30.0

    def __init__(self, world, log=print, **overrides):
        super().__init__(world, log=log, **overrides)
        self.node = '/' + world.node
        marks = [int(float((self.w.read(f'{self.node}/agent/hands/{h}/seen', 'x').get('properties') or {}).get('/epoch') or 0)) for h in _hand.HANDS]
        self.seen = self.marked = max([self.seen] + marks)
        self.pending = []           # mention records to write, batched
        try:                                                     # the world's identity: its first event, so two worlds on one port never share a cache
            first = (self.w.tool('history', after=0, limit=1).get('events') or [{}])[0]
            wid = hashlib.sha1(json.dumps({k: first.get(k) for k in ('epoch', 'who', 'touched')}, sort_keys=True).encode()).hexdigest()[:10]
        except Exception:
            wid = 'unknown'
        self.cache = os.path.expanduser(os.environ.get('LINKS_INDEX') or f'~/.cache/shrine/links-{world.node}-{wid}.json')
        self.dirty, self.saved_at = False, 0.0
        try:
            with open(self.cache) as f:
                d = json.load(f)
            INDEX.load(d['index'])
            self.seen = self.marked = int(d['epoch'])     # the stream from here brings the index up to date
            INDEX.ready = True
            self.log(f'links: index loaded from {self.cache} at epoch {self.seen}: {len(INDEX.aliases_of)} things, {len(INDEX.into)} pointed at')
        except Exception:
            pass
        port = int(self.setting('port') or 8312)
        server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.log(f'links: answering on http://127.0.0.1:{port}')

    # ---- what is scanned
    def roots(self):
        out = [c['path'] for c in self.w.read(self.node + '/user', 'y', limit=2000).get('children') or []]
        out += [c['path'] for c in self.w.read(self.node + '/agent', 'y', limit=2000).get('children') or [] if CHAT.fullmatch(c['path'].rsplit('/', 1)[1])]
        return out

    def scanned(self, path):
        rel = path[len(self.node):]
        if rel.startswith('/user/'):
            return True
        if rel.startswith('/agent/'):
            seg = rel.split('/')[2]
            return bool(CHAT.fullmatch(seg)) or (seg == 'weave' and '/names/' not in rel)
        return False

    def text_of(self, props):
        return ' . '.join(str(props[k]) for k in TEXT_SLOTS if isinstance(props.get(k), str) and len(props[k]) > 2)

    def absorb(self, record, write=True):
        """One record into the index: its references, its names if it is a thing, its mentions if it holds text."""
        path, props = record['path'], record.get('properties') if record.get('exists', True) else None
        INDEX.put_refs(path, props)
        if THING.match(path):
            INDEX.put_thing({'path': path, 'properties': props})
            if props is not None and INDEX.ready and write:
                self.reread_named(path)
        m = TALK_TURN.match(path)
        if m and props is not None:
            n = int(m.group(2))
            with INDEX.lock:
                cur = INDEX.talks.get(m.group(1))
                if not cur or n >= int(cur.get('n') or 0):
                    INDEX.talks[m.group(1)] = {'n': n, 'who': str(props.get('/who') or '')}
        if props is None or path.endswith('/mentions'):
            return
        text = self.text_of(props)
        if not text:
            return
        found = INDEX.resolve(text)
        cands = INDEX.unresolved(text, found) if INDEX.ready or not write else []
        with INDEX.lock:
            for n in INDEX.candidates.get(path, []):
                s_ = INDEX.by_name.get(norm_name(n))
                if s_:
                    s_.discard(path)
            INDEX.candidates[path] = cands
            for n in cands:
                INDEX.by_name.setdefault(norm_name(n), set()).add(path)
        if write and INDEX.ready:
            self.offer(path, cands, bool(found))
        if found and write:
            slots, seen = {}, set()
            for f in found:
                if f['path'] == path or path.startswith(f['path'] + '/') or f['path'] in seen:
                    continue
                seen.add(f['path'])
                slots[segment_of(f['path'].rsplit('/', 1)[1])] = {'type': 'reference', 'path': f['path'], 'care': 'x', 'case': 0}
            if slots:
                have = {k.lstrip('/'): target_of(v) for k, v in (self.w.read(path + '/mentions', 'x').get('properties') or {}).items()}
                if {k: v['path'] for k, v in slots.items()} != have:
                    self.pending.append({'path': path + '/mentions', 'slots': slots})

    def save(self):
        if not INDEX.ready:
            return
        os.makedirs(os.path.dirname(self.cache), exist_ok=True)
        tmp = self.cache + '.tmp'
        with open(tmp, 'w') as f:
            json.dump({'epoch': self.seen, 'index': INDEX.dump()}, f)
        os.replace(tmp, self.cache)
        self.dirty, self.saved_at = False, time.time()

    def offer(self, source, cands, with_known):
        """A name worth the agent's attention: one that appears beside a known thing, or in more than one text, or in
        something a person wrote. It becomes /agent/weave/names/<slug> {name, count, sources}; the agent answers it."""
        node = self.node
        for n in cands:
            key = norm_name(n)
            if not key or key in INDEX.dismissed or key in INDEX.queued or key in INDEX.alias:
                continue
            srcs = sorted(INDEX.by_name.get(key, ()))
            slug = re.sub(r'[^a-z0-9]+', '_', key).strip('_')
            if not slug or not slug[0].isalpha():
                slug = 'n_' + slug
            INDEX.queued.add(key)
            if not getattr(self, 'weave_made', False):
                self.pending.append({'path': f'{node}/agent/weave', 'slots': {'name': 'weave', 'description': 'where the agent places names the index could not resolve, and tidies the world a folder at a time'}})
                self.weave_made = True
            self.pending.append({'path': f'{node}/agent/weave/names/{slug}', 'slots': {'name': n, 'count': len(srcs), **{f'source_{i}': {'type': 'reference', 'path': s_, 'care': 'x', 'case': 0} for i, s_ in enumerate(srcs[:3], 1)}}})
            self.dirty = True

    def settle_name(self, path, exists, props):
        """The agent culled a name record (placed or dismissed) or the person wrote one; keep the index's memory straight."""
        key = norm_name((props or {}).get('/name') or path.rsplit('/', 1)[1].replace('_', ' '))
        with INDEX.lock:
            if not exists:
                INDEX.queued.discard(key)
                if key not in INDEX.alias:
                    INDEX.dismissed.add(key)              # gone without a record for it: not a thing
        self.dirty = True

    def reread_named(self, thing):
        """A thing just appeared: every text that named it without a record gets its mentions now."""
        keys = {k for k in INDEX.aliases_of.get(thing, ()) if k}
        srcs = set()
        with INDEX.lock:
            for k in keys:
                key = ' '.join(k)
                srcs |= INDEX.by_name.get(key, set())
                INDEX.queued.discard(key); INDEX.dismissed.discard(key)
        for src in sorted(srcs)[:200]:
            rec = self.w.read(src, 'x')
            if rec.get('exists'):
                self.absorb({'path': src, 'exists': True, 'properties': rec.get('properties') or {}})

    def flush(self):
        n = 0
        while self.pending:
            batch, self.pending = self.pending[:40], self.pending[40:]
            try:
                self.w.tool('write', records=batch, who=self.name); n += len(batch)
            except Exception as e:
                self.log(f'links: mentions refused: {str(e)[:100]}')
        return n

    def build(self):
        """Two passes over the world: the things first, so every alias is known before any text is scanned."""
        t0, pages, texts = time.time(), [], []
        for root in self.roots():
            nxt = None
            for _ in range(2000):
                page = self.w.read(root, 'z', limit=500, **({'next': nxt} if nxt else {}))
                time.sleep(0.05)                                   # the world keeps answering everyone else meanwhile
                stack = [page]
                while stack:
                    node = stack.pop()
                    if not isinstance(node, dict) or not node.get('path'):
                        continue                                   # a refused or empty page carries no record
                    if node.get('exists'):
                        pages.append(node)
                    stack.extend(node.get('children') or [])
                nxt = page.get('next')
                if not nxt:
                    break
        for rec in pages:
            INDEX.put_refs(rec['path'], rec.get('properties') or {})
            if THING.match(rec['path']):
                INDEX.put_thing(rec)
        for rec in pages:
            self.absorb({**rec, 'properties': rec.get('properties') or {}}, write=True)
        INDEX.ready = True
        for rec in pages:                                          # candidates need the full alias set, so once more, no writes
            props = rec.get('properties') or {}
            if not rec['path'].endswith('/mentions') and self.text_of(props):
                INDEX.candidates[rec['path']] = INDEX.unresolved(self.text_of(props), INDEX.resolve(self.text_of(props)))
        written = self.flush()
        self.save()
        self.log(f'links: {len(pages)} records, {len(INDEX.aliases_of)} things with {len(INDEX.alias)} names, {len(INDEX.into)} pointed at, {written} mention records written, {time.time() - t0:.1f}s')

    def quiet(self, item):
        return not any(self.scanned(t) for t in (item.get('touched') or []))

    def mark_seen(self):
        pass

    def line(self, line):
        if not INDEX.ready:
            return 0
        for t in line.get('touched') or []:
            if t.startswith(self.node + '/agent/weave/names/') and (line.get('who') or '') != self.name:
                rec = self.w.read(t, 'x')
                self.settle_name(t, bool(rec.get('exists')), rec.get('properties') or {})
            if self.scanned(t):
                rec = self.w.read(t, 'x')
                self.absorb({'path': t, 'exists': bool(rec.get('exists')), 'properties': rec.get('properties') or {}})
                self.dirty = True
        return self.flush()

    def tick(self, now):
        if not INDEX.ready:
            try:
                self.build()
            except Exception as e:
                self.log(f'links: build failed ({str(e)[:120]}); again next tick')
        elif self.dirty and now - self.saved_at > 30:
            try:
                self.save()
            except Exception as e:
                self.log(f'links: could not save the index: {str(e)[:80]}')
        return 0


if __name__ == '__main__':
    _hand.run(LinksHand, settings=('port',))
