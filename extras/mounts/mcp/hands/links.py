"""The links hand: the index. Every reference, every name, every mention, in memory, current with the stream.

Three things, answered in milliseconds over HTTP and never by walking the world:

  references   who points at a record, and on which slot (explicit references in slots)
  aliases      every spelling of every thing: its name, its slug, its aliases slot, its domain, its handle
  names        which things a text refers to, found by scanning the text against the aliases, for the fallback index

At write time, every new text (a turn's said, a found row, a page region, a document paragraph, a note) is scanned,
and the things it names are kept for the fallback index; a reference in prose is written by whoever reads the text, as a path in brackets. A record's
"pointing here" then includes "mentioned" as well as explicit slots: the tree under a thing grows from writes made
elsewhere by people who only named it. Names that match nothing are kept as candidates, by source and by count,
for a person or an agent to accept as a new starter place (one record, its subtree to come) or ignore.

    GET /links?to=<path>         [{path, slot, cell, hole}]           everything pointing at a record
    GET /by?to=<path>            {slot: [{path, ...}]}                the same, grouped by slot (prose slots for entions)
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
# a thing is any record under /user, at any depth, except the hands' own folders and a thing's own parts
PARTS = {'talk', 'turns', 'asks', 'found', 'status', 'taken', 'context', 'views', 'integrated', 'syncs', 'runs', 'repairs', 'identities'}
THING_ROOT = re.compile(r'^/0x[0-9a-f]+(/0x[0-9a-f]+)?/user/(?!web/|views/|sources/)[a-z][a-z0-9_]*(/[a-z][a-z0-9_]*)*$')
WORLD = re.compile(r'^/(0x[0-9a-f]+)(?:/(0x[0-9a-f]+))?/user(/|$)')


def world_of(path):
    """The world a name belongs to: its node, or the simulated peer under it (/0x11/0x12/user/... is 0x12's)."""
    m = WORLD.match(path or '')
    return (m.group(2) or m.group(1)) if m else ''


class _Thing:
    def match(self, path):
        return bool(THING_ROOT.match(path)) and not (set(path.split('/user/', 1)[1].split('/')) & PARTS)


THING = _Thing()
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
        self.lock = threading.RLock()            # re-entrant: a reading method may call another
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
        self.overlay_of = {}    # overlay path -> the real record it places
        self.forwards = set()   # paths poked to moved_to: kept for peers that hold them, never shown as placed
        self.placed = {}        # real record -> set(overlay paths)
        self.notes = {}         # overlay path -> {slot: value}: what the placement says about itself
        self.literals = {}      # label -> {n, values: {value: set(holders)}, from: {folder: n}}: literal profiles
        self.literal_of = {}    # record -> {label: value}: what each record contributed, so a rewrite can be undone
        self.labels_of = {}     # record -> set(labels): its shape
        self.name_text = set()  # (record, label, value, name): a literal that equals an existing name
        self.texts = {}         # text record -> {known, unknown, digested, size}: what is waiting to be decomposed
        self.ready = False

    # ---- references
    def put_refs(self, source, props):
        self._same_cache = None
        cell = bool(props) and '/sys/weft' in props
        with self.lock:
            old = self.overlay_of.pop(source, None)
            if old and old in self.placed:
                self.placed[old].discard(source)
            self.notes.pop(source, None)
            self.forwards.discard(source)
            if props and props.get('/moved_to'):
                self.forwards.add(source)
            if cell and props.get('/sys/tack') and not props.get('/moved_to') and source.startswith('/' + source.split('/')[1] + '/user/') and '/user/views/' not in source:   # a forward or a view is not a placement
                real = target_of(props['/sys/tack'])
                if real and '/x/' not in str(props['/sys/tack']).split('/0x')[0]:
                    self.overlay_of[source] = real
                    self.placed.setdefault(real, set()).add(source)
                    self.notes[source] = {k.lstrip('/'): str(v)[:200] for k, v in props.items() if not k.startswith('/sys') and not target_of(v)}
        hole = False
        refs = []
        for k, v in (props or {}).items():
            if k == '/sys/weft':
                continue
            t = target_of(v)
            if t and t != source:
                refs.append((t, k.lstrip('/')))
        with self.lock:
            for slot, v in self.literal_of.pop(source, {}).items():
                lit = self.literals.get(slot)
                if lit:
                    lit['n'] -= 1
                    h = lit['values'].get(v)
                    if h:
                        h.discard(source)
                        if not h:
                            del lit['values'][v]
            self.labels_of.pop(source, None)
            self.name_text = {x for x in self.name_text if x[0] != source}
            if props and '/user/' in source and '/talk/' not in source and '/web/' not in source:
                mine = {}
                for k, v in props.items():
                    if k.startswith('/sys') or target_of(v) or not isinstance(v, (str, int, float)) or k in ('/name', '/description', '/text', '/said', '/quote'):
                        continue
                    val = str(v)[:120]
                    lit = self.literals.setdefault(k.lstrip('/'), {'n': 0, 'values': {}, 'from': {}})
                    lit['n'] += 1; lit['values'].setdefault(val, set()).add(source)
                    fk = source.split('/user/')[1].split('/')[0]; lit['from'][fk] = lit['from'].get(fk, 0) + 1
                    mine[k.lstrip('/')] = val
                    key = tuple(w for w, _ in norm_words(val))
                    if key in self.alias and k not in ('/aliases',):
                        for tgt in self.alias[key]:
                            if tgt != source:
                                self.name_text.add((source, k.lstrip('/'), val, tgt))
                self.literal_of[source] = mine
                self.labels_of[source] = {k.lstrip('/') for k in props if not k.startswith('/sys')}
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
        if props and ('/sys/tack' in props or '/moved_to' in props or not props.get('/name')):
            props = None                                      # a thing carries a name; an overlay, a forward or a relation record is not a second name
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

    def resolve(self, text, world=None):
        """Longest match of the aliases over the text; a single-word alias needs a capital or a dot in the text. With a
        world, only that world's names count, chosen before any tie is broken, so another world's record never hides one."""
        words = norm_words(text)
        found, i = [], 0
        with self.lock:
            while i < len(words):
                hit = None
                for n in range(min(self.longest, len(words) - i), 0, -1):
                    key = tuple(w for w, _ in words[i:i + n])
                    paths = self.alias.get(key)
                    if paths and world:
                        paths = {p_ for p_ in paths if world_of(p_) == world}
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
        for sentence in re.split(r'[.!?]\s+|\n|\s[-•*–]\s|[,;:()\[\]"“”]', str(text)):        # a list item starts fresh, like a sentence
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
                if run and t in ('and', 'of', '&', 'de', 'for', 'the') and i + 1 < len(toks) and toks[i + 1][:1].isupper() and not inside[i + 1]:
                    run.append((i, t)); continue                       # Verisk Catastrophe and Risk Solutions, Bank of America
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
            return {'version': 3, 'overlay_of': self.overlay_of, 'notes': self.notes, 'labels_of': {k: sorted(v) for k, v in self.labels_of.items()},
                    'literal_of': self.literal_of, 'name_text': sorted(self.name_text),
                    'dismissed': sorted(self.dismissed), 'queued': sorted(self.queued), 'talks': self.talks, 'texts': self.texts,'into': [[t, [[s_, slot, c, h] for (s_, slot), (c, h) in d.items()]] for t, d in self.into.items()],
                    'out': {s_: [[t, slot] for t, slot in refs] for s_, refs in self.out.items()},
                    'alias': [[list(k), sorted(v)] for k, v in self.alias.items()],
                    'aliases_of': {p_: [list(k) for k in ks] for p_, ks in self.aliases_of.items()},
                    'names': self.names, 'longest': self.longest, 'candidates': self.candidates}

    def load(self, d):
        self._same_cache = None
        with self.lock:
            self.into = {t: {(s_, slot): (c, h) for s_, slot, c, h in rows} for t, rows in d['into']}
            self.out = {s_: [(t, slot) for t, slot in refs] for s_, refs in d['out'].items()}
            self.alias = {tuple(k): set(v) for k, v in d['alias']}
            self.aliases_of = {p_: {tuple(k) for k in ks} for p_, ks in d['aliases_of'].items()}
            self.names, self.longest, self.candidates = d['names'], d['longest'], d['candidates']
            self.dismissed, self.queued = set(d.get('dismissed') or []), set(d.get('queued') or [])
            self.talks = d.get('talks') or {}
            self.texts = d.get('texts') or {}
            if d.get('version') != 3:
                raise ValueError('an older index: rebuild')
            self.overlay_of, self.notes = d['overlay_of'], d['notes']
            self.placed = {}
            for o, r in self.overlay_of.items():
                self.placed.setdefault(r, set()).add(o)
            self.labels_of = {k: set(v) for k, v in d['labels_of'].items()}
            self.literal_of = d['literal_of']; self.name_text = {tuple(x) for x in d['name_text']}
            self.literals = {}
            for src, mine in self.literal_of.items():
                fk = src.split('/user/')[1].split('/')[0] if '/user/' in src else ''
                for slot, val in mine.items():
                    lit = self.literals.setdefault(slot, {'n': 0, 'values': {}, 'from': {}})
                    lit['n'] += 1; lit['values'].setdefault(val, set()).add(src); lit['from'][fk] = lit['from'].get(fk, 0) + 1
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
            slot = m['slot']
            path = m['path']
            out.setdefault(slot, []).append(dict(m, path=path))
        return out

    # ---- vantages: the graph read from a name; nothing here knows what any label means
    def _name(self, p_):
        return self.names.get(p_) or (p_.rsplit('/', 1)[-1].replace('_', ' ') if p_ else '')

    def _edges_out(self, p_, labels=None):
        return [(t, slot) for t, slot in self.out.get(p_, []) if (labels is None or slot in labels) and not slot.startswith('sys/')]

    def _edges_in(self, p_, labels=None):
        return [(s_, slot) for (s_, slot) in self.into.get(p_, {}) if (labels is None or slot in labels) and not slot.startswith('sys/') and '/talk/' not in s_ and not s_.endswith('/context') and '/user/views/' not in s_]

    def real(self, p_):
        seen = set()
        while p_ in self.overlay_of and p_ not in seen:
            seen.add(p_); p_ = self.overlay_of[p_]
        return p_

    def _parents(self, p_):
        """The path parents of a name that are records (or folders) under /user, nearest first."""
        out, parts = [], p_.split('/')
        for i in range(len(parts) - 1, 3, -1):
            q = '/'.join(parts[:i])
            out.append({'path': q, 'name': self._name(q)})
        return out

    def children(self, p_):
        with self.lock:
            prefix = p_ + '/'
            kids = {q.split('/')[p_.count('/') + 1] for q in list(self.names) + list(self.labels_of) + list(self.overlay_of) if q.startswith(prefix) and q not in self.forwards}
        return sorted(prefix + k for k in kids if k not in PARTS)

    def around(self, at, depth=2, labels=None, cap=40):
        if not at or at.count('/') < 3:
            return {'at': at, 'real': at, 'name': '', 'ancestors': [], 'descendants': [], 'refs_out': [], 'refs_in': [], 'parts': []}
        """Ancestors (path parents of the real record, and of every overlay that places it), descendants (children and
        overlays, resolved to their real records, recursively), and the references in and out. No label means anything."""
        at = at.rstrip('/')
        real = self.real(at)
        ancestors = [{'via': real, 'chain': self._parents(real)}]
        for o in sorted(self.placed.get(real, ())):
            ancestors.append({'via': o, 'note': self.notes.get(o) or {}, 'chain': self._parents(o)})
        def down(p_, d, seen):
            if d <= 0:
                return []
            out = []
            for c in self.children(p_)[:cap]:
                r = self.real(c)
                if r in seen:
                    continue
                seen.add(r)
                node = {'path': c, 'name': self._name(r), 'real': r if r != c else None, 'note': self.notes.get(c) or None}
                kids = down(r, d - 1, seen)
                if kids:
                    node['next'] = kids
                out.append(node)
            return out
        with self.lock:
            refs_out = [{'path': t, 'name': self._name(t), 'label': slot} for t, slot in self._edges_out(real, labels)][:cap]
            refs_in = [{'path': s_, 'name': self._name(s_), 'label': slot} for s_, slot in self._edges_in(real, labels)][:cap]
        return {'at': at, 'real': real, 'name': self._name(real), 'ancestors': ancestors, 'descendants': down(real, depth, {real}), 'relations': self.relations(real),
                'refs_out': refs_out, 'refs_in': refs_in, 'parts': sorted(q for q in self.names if q.startswith(real + '/') and set(q[len(real) + 1:].split('/')) & PARTS)[:cap]}

    def same_as(self, real):
        """The records in any world that a same slot joins to this one, either direction, transitively. A same may sit on
        the record itself or on a relation record beneath it (same/<slug> {same: <name>, why: ...})."""
        links = self._same_links()
        seen, todo = {real}, [real]
        while todo:
            p_ = todo.pop()
            for q in links.get(p_, ()):
                if q not in seen:
                    seen.add(q); todo.append(q)
        return seen

    def _same_links(self):
        cache = getattr(self, '_same_cache', None)
        if cache is not None:
            return cache
        links = {}
        with self.lock:
            for s_, refs in list(self.out.items()):
                for t, slot in refs:
                    if slot == 'same':
                        a = self.judged_about(s_, refs)
                        links.setdefault(a, set()).add(t); links.setdefault(t, set()).add(a)
        self._same_cache = links
        return links

    def relations(self, real):
        """The relations of a thing as one union over every world that describes it (joined by same links), each tagged
        with the world that asserts it."""
        out, seen = [], set()
        for rec in sorted(self.same_as(real)):
            for r in self._relations_one(rec):
                if r['label'] in ('same', 'different', 'why') or r['other'] in self.same_as(real):
                    continue
                k = (r['way'], r['label'], r['other'])
                if k in seen:
                    continue
                seen.add(k)
                out.append(dict(r, world=world_of(r['via'] if r['way'] == 'out' else r['other']), about=rec))
        return out

    # ---- what holds a relation: a thing holds its own slots; a relation record is its nearest thing's
    def is_thing(self, p_):
        """A thing: a record filed straight under a top folder (/user/orgs/verisk), named or not; deeper, a named record
        that says something of its own, holds no children, or holds things (a country holding its cities). A named record
        holding only relation records and overlays is a grouping folder (verisk/acquisitions). Forwards and overlays are
        not things. Nothing here knows what any name means."""
        if p_ in self.forwards or p_ in self.overlay_of or '/user/' not in p_:
            return False
        rel = p_.split('/user/', 1)[1]
        segs = rel.split('/')
        if len(segs) < 2 or segs[0] in PARTS or set(segs[2:]) & PARTS:
            return False                                      # a top folder (/user/books), or the machinery under a record
        if rel.count('/') == 1:
            return bool(self.labels_of.get(p_)) or p_ in self.names or bool(self.children(p_))
        if p_ not in self.names:
            return False
        if self.labels_of.get(p_, set()) - {'name', 'description', 'source', 'sources'}:
            return True
        kids = self.children(p_)
        return not kids or any(k in self.names and k not in self.overlay_of for k in kids)

    def forward_of(self, p_):
        return next((t for t, slot in self.out.get(p_, []) if slot == 'moved_to'), None)

    def holder_of(self, p_):
        """The thing a record speaks for, and the folder it speaks under: a thing speaks for itself; a relation record
        (books/walkaway/authors/cory_doctorow) for the nearest thing above it, under the folder just beneath that thing
        ('authors'). Beneath a record that moved, it speaks for where the record went. None when no thing is above it."""
        if self.is_thing(p_):
            return p_, None
        parts = p_.split('/')
        for i in range(len(parts) - 1, 3, -1):
            q = '/'.join(parts[:i])
            if q in self.forwards:
                t, seen = q, set()
                while t in self.forwards and t not in seen:
                    seen.add(t); t = self.forward_of(t) or t
                return (t, self._label_under(parts, i)) if t != q else (None, None)
            if self.is_thing(q):
                return q, self._label_under(parts, i)
        return None, None

    @staticmethod
    def _label_under(parts, i):
        """The label of a relation record beneath a thing: its own name when it sits right under the thing
        (walkaway/authors), else the folder it sits in (walkaway/authors/cory_doctorow, urbit/ids/urbit_ids/analysts/x)."""
        return parts[i] if len(parts) == i + 1 else parts[-2]

    def _refs(self, rec):
        return [(t, slot) for t, slot in self._edges_out(rec) if '/user/web/' not in t and slot not in ('source', 'sources', 'moved_to')]

    def primary(self, rec, folder):
        """Which reference of a relation record is the related thing, the others being its qualifiers: the only one; or
        the one whose name the record is named after; or the one whose slot names the folder (author in authors).
        None when the record does not say."""
        refs = self._refs(rec)
        if len(refs) == 1:
            return refs[0][1]
        slug = rec.rsplit('/', 1)[1]
        by_slug = [s for t, s in refs if t.rsplit('/', 1)[1] == slug]
        if len(by_slug) == 1:
            return by_slug[0]
        f = (folder or '').rstrip('s')
        by_folder = [s for t, s in refs if f and (s == folder or s.rstrip('s') == f)]
        return by_folder[0] if len(by_folder) == 1 else None

    def _qualifiers(self, rec, keep):
        """A relation record's own literals and its other references (by name): what it says about the relation."""
        note = dict(self.literal_of.get(rec, {}))
        for t, s in self._refs(rec):
            if s != keep:
                note[s] = self._name(t)
        return note

    def _relations_one(self, real):
        """Every relation a thing is in, read from slots alone, labels uninterpreted:
        - out: a slot of this thing names another thing, or a relation record beneath it does (its folder is the label,
          its primary reference the other thing, its other slots the relation's qualifiers);
        - in: the same, read from the other side. A thing filed beneath another holds its own slots, never its parent's."""
        out = []
        with self.lock:
            for t, slot in self._edges_out(real):
                if '/user/web/' not in t and slot != 'moved_to':
                    out.append({'way': 'out', 'label': slot, 'other': t, 'name': self._name(t), 'via': real, 'note': {}})
            for s_, slot in self._edges_in(real):
                if '/user/web/' in s_ or slot == 'moved_to' or s_ in self.forwards or '/claims/' in s_:
                    continue
                holder, folder = self.holder_of(s_)
                if not holder or holder == real:
                    continue
                if folder is None or slot in ('source', 'sources'):
                    out.append({'way': 'in', 'label': slot, 'other': holder, 'name': self._name(holder), 'via': s_, 'note': {}})
                    continue
                main = self.primary(s_, folder)
                if main == slot or main is None and len(self._refs(s_)) == 1:
                    out.append({'way': 'in', 'label': folder, 'other': holder, 'name': self._name(holder), 'via': s_, 'note': self._qualifiers(s_, slot)})
                else:                                         # named as a qualifier of another thing's relation
                    out.append({'way': 'in', 'label': slot, 'other': holder, 'name': self._name(holder), 'via': s_,
                                'note': dict(self._qualifiers(s_, slot), within=folder)})
            for rec in self._relation_records(real):
                rel = rec[len(real) + 1:].split('/')
                folder = rel[0] if len(rel) == 1 else rel[-2]
                main = self.primary(rec, folder)
                for t, slot in self._refs(rec):
                    if main is not None and slot != main:
                        continue                              # a qualifier, carried in the note
                    label = folder if main is not None or len(self._refs(rec)) == 1 else folder + ' ' + slot
                    out.append({'way': 'out', 'label': label, 'other': t, 'name': self._name(t), 'via': rec, 'note': self._qualifiers(rec, slot)})
        seen, uniq = set(), []
        for r in out:
            k = (r['way'], r['label'], r['other'])
            if k not in seen:
                seen.add(k); uniq.append(r)
        return uniq

    def _relation_records(self, real):
        """The records beneath a thing that speak for it: not things of their own, not claims, not overlays or parts."""
        out, todo = [], [c for c in self.children(real)]
        while todo:
            c = todo.pop(0)
            seg = c.rsplit('/', 1)[1]
            if c in self.overlay_of or c in self.forwards or seg in PARTS or seg == 'claims' or self.is_thing(c):
                continue
            out.append(c)
            if c.count('/') - real.count('/') < 3:
                todo.extend(self.children(c))
        return out

    def unfold(self, at, depth=2, ways=('out', 'in'), skip=('source', 'sources', 'mentioned', 'claims'), cap=24, open_=()):
        """A record as a world: its relations as virtual folders (a label, or a label and 'of' for the other direction),
        each holding the related things. Computed, never stored; the same facts unfold differently from every vantage.

        A reading, not a crawl:
        - one thing, one entry: a thing several folders or several worlds name (McKenzie as 0x11's acquisition, 0x13's
          acquired_by and 0x12's MIS) is one item, in the first folder that names it, carrying every label it has;
        - unfolded once: a thing opens beneath its first appearance on the page, breadth first, so the shallowest place
          wins; later it is listed, marked seen, and not opened again;
        - beneath the subject, a thing shows only what it asserts itself and its parts, a few of each, and every folder
          pointing at it is a count to open on demand (open_ names the things to open, or the reader unfolds that thing)."""
        at = self.real(at.rstrip('/'))
        open_ = {self.real(p_) for p_ in open_}
        key = lambda p_: min(self.same_as(p_))
        root = {}
        opened = {key(at)}
        queue = [(root, at, depth, frozenset(self.same_as(at)), True)]
        while queue:
            holder, p_, d, trail, whole = queue.pop(0)
            if d <= 0:
                continue
            fs = self._folders(p_, trail, whole, ways, skip, cap)
            for f in fs:
                for it in f['items']:
                    k = key(it['path'])
                    if k in opened:
                        it['seen'] = True                     # already open higher up (or earlier) on the page
                        continue
                    opened.add(k)
                    sub = self.same_as(it['path'])
                    queue.append((it, it['path'], d - 1, trail | sub, bool(sub & open_)))
            if fs:
                holder['folders'] = fs
        return {'at': at, 'name': self._name(at), 'world': world_of(at), 'same': sorted(x for x in self.same_as(at) if x != at),
                'folders': root.get('folders', [])}

    def _folders(self, p_, trail, whole, ways, skip, cap):
        """One thing's folders, unopened: its relations by label and its parts, union over every world that describes it,
        each related thing once (in its first folder: what it asserts, then its parts, then what points at it)."""
        folders, closed = {}, {}
        for r in self.relations(p_):
            if r['way'] not in ways or r['label'] in skip or self.same_as(r['other']) & trail:
                continue                                      # one thing, whatever world names it, appears once on a branch
            label = r['label'] if r['way'] == 'out' else r['label'] + ' of'
            if r['way'] == 'in' and not whole:
                closed.setdefault(label, set()).add(frozenset(self.same_as(r['other'])))
                continue
            folders.setdefault(label, []).append(r)
        for rec in sorted(self.same_as(p_)):                  # the parts each world files under the thing
            for c in self.children(rec):
                seg = c.rsplit('/', 1)[1]
                if seg in PARTS or seg in skip or c in self.forwards or c in self.overlay_of:
                    continue
                kids = [g for g in self.children(c) if self.is_thing(g)] if not self.is_thing(c) else [c]
                for g in kids:
                    if not (self.same_as(g) & trail):
                        label = seg if g != c else 'parts'
                        folders.setdefault(label, []).append({'way': 'part', 'label': label, 'other': g, 'name': self._name(g), 'world': world_of(g), 'note': {}})
        rank = lambda label: (2 if label.endswith(' of') else 1 if all(r['way'] == 'part' for r in folders[label]) else 0, label)
        placed, order = {}, []                                # thing -> its item; folders keep their first-named things
        for label in sorted(folders, key=rank):
            for r in folders[label]:
                k = min(self.same_as(r['other']))
                if k in placed:
                    item = placed[k]
                    item['also'].append(r)
                    if label not in item['labels']:
                        item['labels'].append(label)
                    continue
                placed[k] = item = dict(r, labels=[label], also=[], folder=label)
                order.append(item)
        by_folder = {}
        for item in order:
            by_folder.setdefault(item['folder'], []).append(item)
        limit = cap if whole else max(3, cap // 4)
        out = []
        for label in sorted(by_folder, key=rank):
            rs = by_folder[label]
            items = []
            for r in rs[:limit]:
                worlds = sorted({x.get('world') or world_of(x['other']) for x in [r] + r['also']})
                note = {}
                for x in [r] + r['also']:
                    note.update({k: v for k, v in (x.get('note') or {}).items() if not str(v).startswith('/')})
                node = {'path': r['other'], 'name': r['name'], 'world': world_of(r['other']), 'by': r.get('world'), 'worlds': worlds, 'note': note}
                if len(r['labels']) > 1:
                    node['labels'] = r['labels']
                items.append(node)
            f = {'label': label, 'items': items}
            if len(rs) > limit:
                f['more'] = len(rs) - limit
            out.append(f)
        for label, others in sorted(closed.items()):
            out.append({'label': label, 'items': [], 'more': len(others), 'closed': True})
        return out

    def _is_group(self, p_):
        """A grouping folder: a path whose children are mostly overlays or things, and which holds no facts of its own
        beyond a name and a description."""
        labels = self.labels_of.get(p_, set())
        return not (labels - {'name', 'description'}) and any(c in self.overlay_of for c in self.children(p_))

    def placements(self, of):
        real = self.real(of.rstrip('/'))
        return [{'path': o, 'note': self.notes.get(o) or {}, 'chain': self._parents(o)} for o in sorted(self.placed.get(real, ()))]

    def between(self, a, b, limit=6):
        """The shortest path of edges joining two names, either direction per step."""
        a, b = a.rstrip('/'), b.rstrip('/')
        if a == b:
            return []
        prev, frontier = {a: None}, [a]
        for _ in range(limit):
            nxt = []
            for p_ in frontier:
                with self.lock:
                    steps = [(t, slot, 'out') for t, slot in self._edges_out(p_)] + [(s_, slot, 'in') for s_, slot in self._edges_in(p_)]
                for t, slot, way in steps:
                    if t in prev:
                        continue
                    prev[t] = (p_, slot, way)
                    if t == b:
                        path, cur = [], b
                        while prev[cur]:
                            frm, slot_, way_ = prev[cur]
                            path.insert(0, {'from': frm, 'label': slot_, 'to': cur, 'held_by': frm if way_ == 'out' else cur})
                            cur = frm
                        return path
                    nxt.append(t)
            frontier = nxt
        return None

    def profile(self):
        """Per label: uses, holders, references or literals, cardinality, and the folders it leads from and to."""
        prof = {}
        with self.lock:
            for src, refs in self.out.items():
                if '/user/' not in src or '/talk/' in src:
                    continue
                per = {}
                for t, slot in refs:
                    if slot.startswith('sys/'):
                        continue
                    per[slot] = per.get(slot, 0) + 1
                    pr = prof.setdefault(slot, {'refs': 0, 'holders': 0, 'many': 0, 'from': {}, 'to': {}})
                    pr['refs'] += 1
                    fk = '/'.join(src.split('/user/')[1].split('/')[:1]); tk = '/'.join(t.split('/user/')[1].split('/')[:1]) if '/user/' in t else t.split('/')[2] if t.count('/') > 2 else t
                    pr['from'][fk] = pr['from'].get(fk, 0) + 1; pr['to'][tk] = pr['to'].get(tk, 0) + 1
                for slot, n in per.items():
                    prof[slot]['holders'] += 1; prof[slot]['many'] += 1 if n > 1 else 0
        for slot, lit in self.literals.items():
            pr = prof.setdefault(slot, {'refs': 0, 'holders': 0, 'many': 0, 'from': {}, 'to': {}})
            pr['literals'] = lit['n']; pr['distinct'] = len(lit['values']); pr['literal_from'] = lit['from']
        return prof

    def shapes(self, limit=30):
        """Records grouped by their exact set of labels: the de facto kinds, whatever they are called."""
        groups = {}
        with self.lock:
            for p_, labels in self.labels_of.items():
                key = ' '.join(sorted(labels))
                g = groups.setdefault(key, {'labels': sorted(labels), 'count': 0, 'examples': []})
                g['count'] += 1
                if len(g['examples']) < 3:
                    g['examples'].append(p_)
        return sorted(groups.values(), key=lambda g: -g['count'])[:limit]

    def signals(self, limit=20):
        """Structural facts worth a look; none says what anything means."""
        out = {}
        with self.lock:
            names_known = set(self.names)
            out['dangling'] = sorted({(s_, slot, t) for s_, refs in self.out.items() for t, slot in refs if '/user/' in t and t not in names_known
                                      and not t.startswith(s_) and not any(n.startswith(t + '/') for n in ())} )[:limit]
            linked = set(self.out) | set(self.into) | set(self.placed)
            out['orphans'] = sorted(p_ for p_ in self.names if p_ not in linked and p_.count('/') <= 4)[:limit]
            out['dangling_overlays'] = sorted((o, r) for o, r in self.overlay_of.items() if r not in self.names)[:limit]
            fam = {}
            for slot in set(self.literals) | {sl for refs in self.out.values() for _, sl in refs}:
                m = re.fullmatch(r'(.+?)_?(\d+)', slot)
                if m:
                    fam.setdefault(m.group(1), set()).add(slot)
            out['numbered_labels'] = sorted((k, sorted(v)) for k, v in fam.items() if len(v) > 1)[:limit]
            out['name_as_text'] = sorted(self.name_text)[:limit]
            shared = []
            for slot, lit in self.literals.items():
                if lit['n'] >= 3 and len(lit['values']) >= 0.8 * lit['n']:          # a label whose values are nearly all distinct
                    for v, holders in lit['values'].items():
                        if len(holders) > 1 and len(str(v)) > 3:
                            shared.append((slot, v, sorted(holders)[:4]))
            out['shared_literal'] = shared[:limit]
            # one name, records in more than one world, not yet joined by same: candidates for the model's judgement
            cross = []
            for key, paths in self.alias.items():
                worlds = {world_of(p_) for p_ in paths}
                if len(worlds) > 1 and len(key) > 1 or (len(worlds) > 1 and len(key[0]) > 4):
                    ps = sorted(paths)
                    if not any(q in self.same_as(ps[0]) for q in ps[1:]):
                        cross.append((' '.join(key), ps[:4]))
            out['same_name_across_worlds'] = sorted(cross)[:limit]
            # one slot, claims with different values: a disagreement for the model to weigh, never to erase
            dis = {}
            for p_, mine in self.literal_of.items():
                if '/claims/' in p_ and 'slot' in mine and 'value' in mine and 'retracted' not in mine:
                    rec = p_.split('/claims/')[0]
                    dis.setdefault((rec, mine['slot']), set()).add(re.sub(r'\s+', ' ', str(mine['value']).strip().lower()))
            out['disagreements'] = sorted((r, sl, sorted(v)) for (r, sl), v in dis.items() if len(v) > 1)[:limit]
            out['undecomposed'] = sorted((p_ for p_, v in self.texts.items() if not v.get('digested') and len(self.out.get(p_.rsplit('/', 1)[0], [])) <= 1 and v.get('size', 0) > 400))[:limit]
        return out

    # ---- intersection, then union: which records in different worlds describe one thing, and what each world knows
    @staticmethod
    def id_keys(value):
        """What a literal value can identify, by its shape alone (no slot name means anything): a web host, a code
        (letters with digits, or a short capitalised token), or a phrase. Numbers and days identify nothing alone."""
        s = str(value).strip()
        if not s or len(s) > 120:
            return []
        low = s.lower()
        m = re.match(r'^(?:https?://)?(?:www\.)?((?:[a-z0-9-]+\.)+[a-z]{2,})(?:[/:?#].*)?$', low)
        if m:
            return [(('host', m.group(1)), 3.0)]
        if re.fullmatch(r'[@#]?[A-Za-z0-9_.-]+', s) and not re.fullmatch(r'[\d.,-]+', s):
            strong = bool(re.search(r'\d', s) and re.search(r'[A-Za-z]', s)) or (s.isupper() and 2 <= len(s) <= 6)
            return [(('code', low.lstrip('@#')), 2.0 if strong else 0.6)] if len(s) >= 2 and low not in COMMON else []
        if re.fullmatch(r'[\d\s.,:/-]+', s):
            return [(('number', low), 0.15)]
        words = tuple(w for w, _ in norm_words(s) if w not in COMMON)
        return [(('phrase', words), 0.8)] if words else []

    def judged_about(self, s_, refs=None):
        """What a judgement (a same or different slot) is about: the subject it names when it holds one (a judgement
        about two other worlds' records, kept in the judge's own world), else the thing it sits on or beneath."""
        refs = self.out.get(s_, []) if refs is None else refs
        subject = next((t for t, slot in refs if slot == 'subject'), None)
        if subject:
            return subject
        return s_ if s_ in self.names or s_.split('/user/', 1)[-1].count('/') == 1 else (self.holder_of(s_)[0] or s_)

    def judged_different(self, a, b):
        """A different slot, on either record or on a relation record beneath it (different/<slug> {different: <name>,
        why}), in any world, names the other: a judgement that they are not one thing."""
        sa, sb = self.same_as(a), self.same_as(b)
        with self.lock:
            for s_, refs in list(self.out.items()):
                for t, slot in refs:
                    if slot != 'different':
                        continue
                    holder = self.judged_about(s_, refs)
                    if (holder in sa and t in sb) or (holder in sb and t in sa):
                        return True
        return False

    def identity_candidates(self, at=None, limit=40):
        """Pairs of things in different worlds that may describe one thing, each with the evidence for it: values they
        share (a host, a code, a phrase), things they both point at (the same announcement, the same founder, joined
        across worlds by same), and names they share. Evidence is weighed by how rare it is. Pairs already joined by
        same, or judged different, are left out; a pair resting on a name alone is marked so (a name is a candidate,
        never proof). The agent decides; the index remembers what it decided through the same and different slots."""
        ev = {}
        def add(a, b, kind, detail, w):
            if world_of(a) == world_of(b) or a == b:
                return
            k = tuple(sorted((a, b)))
            ev.setdefault(k, []).append({'kind': kind, 'detail': detail, 'weight': round(w, 2)})
        with self.lock:
            byval = {}
            def alt_name(holder, val):
                """A literal that is plausibly its holder's own other name: it shares a word with the holder's name, or
                the name is its initials (MIS, McKenzie Intelligence Services). A city in a based_in slot is not."""
                nm = [w for w, _ in norm_words(self.names.get(holder) or holder.rsplit('/', 1)[1].replace('_', ' '))]
                ws = [w for w, _ in norm_words(val)]
                return bool(set(nm) & set(ws) - COMMON) or (len(nm) == 1 and len(ws) > 1 and nm[0] == ''.join(w[0] for w in ws if w not in COMMON))
            for rec, mine in self.literal_of.items():
                if '/claims/' in rec or '/user/web/' in rec:
                    continue
                holder, _ = self.holder_of(rec)
                if not holder:
                    continue
                for label, val in mine.items():
                    for key, w in self.id_keys(val):
                        if key[0] == 'phrase':
                            w = 1.0 if alt_name(holder, val) else 0.3
                        byval.setdefault(key, {}).setdefault(holder, (label, val, w))
            for p_, nm in self.names.items():                   # a name is an identifying phrase too (two words or more)
                if self.is_thing(p_) and len(norm_words(nm)) > 1:
                    for key, w in self.id_keys(nm):
                        byval.setdefault(key, {}).setdefault(p_, ('name', nm, 1.0))
            for key, hs in byval.items():
                groups = {frozenset(self.same_as(h)) for h in hs}  # rarity counts things, not the records one thing has
                if not (2 <= len(groups) <= 4):
                    continue
                items = sorted(hs.items())
                for i, (a, (la, va, wa)) in enumerate(items):
                    for b, (lb, vb, wb) in items[i + 1:]:
                        add(a, b, 'shared ' + key[0], f'{la}: {va} / {lb}: {vb}', min(wa, wb) / (len(groups) - 1))
            # pointing at one thing is evidence only through one relation (both name it as founder) or one source (both
            # cite the same announcement); a founder and an acquirer both point at a company and are two things
            pointed = {}
            for t, d in self.into.items():
                web = '/user/web/' in t
                group = t if web else min(self.same_as(t))
                for (s_, slot) in d:
                    if slot in ('same', 'different', 'moved_to') or '/claims/' in s_:
                        continue
                    holder, folder = self.holder_of(s_)
                    if not holder or holder == t:
                        continue
                    label = 'source' if web or slot in ('source', 'sources') else (folder or slot)
                    pointed.setdefault((group, label.rstrip('s')), {}).setdefault(holder, label)
            for (group, label), hs in pointed.items():
                if not (2 <= len(hs) <= 4):
                    continue
                items = sorted(hs)
                for i, a in enumerate(items):
                    for b in items[i + 1:]:
                        if group in self.same_as(a) | self.same_as(b):
                            continue
                        if label == 'source':
                            add(a, b, 'cite one source', self._name(group) if group in self.names else group.split('/user/')[-1], 1.0 / (len(hs) - 1))
                        else:
                            add(a, b, 'same relation to one thing', f'{label}: {self._name(group)}', 1.2 / (len(hs) - 1))
            for key, paths in self.alias.items():
                ps = sorted(p_ for p_ in paths if self.is_thing(p_))
                if 2 <= len(ps) <= 4:
                    for i, a in enumerate(ps):
                        for b in ps[i + 1:]:
                            add(a, b, 'shared name', ' '.join(key), 0.5)
        # relationship traversal: a thing already joined across worlds; the records each world relates to it, directly
        # or through a record that holds the relation (a deal holding buyer and target), may be one thing too. The labels
        # are shown, never interpreted: an acquirer and a founder both relate to a company, and the agent judges the roles
        for group in self.shared():
            relators = {}
            for m in group['records']:
                for r in self._relations_one(m):
                    if r['label'] in ('same', 'different', 'why', 'source', 'sources', 'moved_to') or '/user/web/' in r['other']:
                        continue
                    x, label = r['other'], r['label'] + (' of' if r['way'] == 'in' else '')
                    if not self.is_thing(x):
                        continue
                    if x not in self.names and r['way'] == 'in':        # a record holding the relation: its other ends relate
                        for t, slot in self._refs(x):
                            if t not in group['records'] and self.is_thing(t):
                                relators.setdefault(t, set()).add(f"{slot}, beside {r['label']}, in {x.split('/user/')[-1]}")
                    relators.setdefault(x, set()).add(label)
            items = sorted(relators.items())
            if len(items) > 12:
                continue
            for i, (a, la) in enumerate(items):
                for b, lb in items[i + 1:]:
                    add(a, b, 'related to one joined thing', f"{' / '.join(sorted(la))} | {' / '.join(sorted(lb))}: {group['name']}", 0.6)
        out = []
        for (a, b), es in ev.items():
            if at and not ({a, b} & self.same_as(at)):
                continue
            if b in self.same_as(a) or self.judged_different(a, b):
                continue
            kinds = {e['kind'] for e in es}
            score = round(sum(e['weight'] for e in es), 2)
            out.append({'a': a, 'b': b, 'a_name': self._name(a), 'b_name': self._name(b), 'worlds': [world_of(a), world_of(b)],
                        'score': score, 'name_only': kinds == {'shared name'}, 'evidence': sorted(es, key=lambda e: -e['weight'])[:6]})
        # a lone shared year is noise, and relating to one joined thing is a lead to follow from a record, not a pairing
        # to propose across the world (a founder and an acquirer both relate to a company): both only when asked about one
        out = [c for c in out if at or (c['score'] >= 0.4 and {e['kind'] for e in c['evidence']} != {'related to one joined thing'})]
        out.sort(key=lambda c: (c['name_only'], -c['score']))
        return out[:limit]

    def similar_names_differ(self, limit=20):
        """One name, several things, each world's record kept apart: joined by no same link, or judged different. Their
        attributes are never shared; this lists them so a reader sees the name is ambiguous."""
        out = []
        with self.lock:
            items = list(self.alias.items())
        for key, paths in items:
            ps = sorted(p_ for p_ in paths if self.is_thing(p_))
            if len(ps) < 2:
                continue
            groups = []
            for p_ in ps:
                if not any(p_ in g for g in groups):
                    groups.append(self.same_as(p_))
            if len(groups) > 1:
                out.append({'name': ' '.join(key), 'things': [sorted(g) for g in groups]})
        return out[:limit]

    def union(self, at):
        """A thing as every world describes it: the records joined by same, and for each fact (a literal or a relation),
        the worlds asserting it. Values are grouped by value, whatever slot each world files them under; a slot one world
        fills with two values, or two worlds fill differently, is a disagreement, kept with each world's value."""
        at = self.real(at.rstrip('/'))
        members = sorted(self.same_as(at))
        worlds = sorted({world_of(m) for m in members})
        facts, by_slot = {}, {}
        with self.lock:
            for m in members:
                w = world_of(m)
                for label, val in self.literal_of.get(m, {}).items():
                    key = re.sub(r'\s+', ' ', str(val).strip().lower())
                    f = facts.setdefault(('value', key), {'kind': 'value', 'value': val, 'labels': set(), 'worlds': set(), 'records': set()})
                    f['labels'].add(label); f['worlds'].add(w); f['records'].add(m)
                    by_slot.setdefault(label, {}).setdefault(key, set()).add(w)
                for p_, mine in self.literal_of.items():          # claims under any member: values asserted with their origin
                    if p_.startswith(m + '/claims/') and 'slot' in mine and 'value' in mine and 'retracted' not in mine:
                        key = re.sub(r'\s+', ' ', str(mine['value']).strip().lower())
                        by_slot.setdefault(mine['slot'], {}).setdefault(key, set()).add(w + ' (claim by ' + str(mine.get('by', '?')) + ')')
        for r in self.relations(at):
            group = min(self.same_as(r['other']))
            f = facts.setdefault(('rel', r['way'], group), {'kind': 'relation', 'way': r['way'], 'other': r['other'], 'name': r['name'],
                                                            'labels': set(), 'worlds': set(), 'records': set()})
            f['labels'].add(r['label'] + (' of' if r['way'] == 'in' else '')); f['worlds'].add(r['world']); f['records'].add(r['about'])
        rows = []
        for f in facts.values():
            rows.append({**f, 'labels': sorted(f['labels']), 'worlds': sorted(f['worlds']), 'records': sorted(f['records']),
                         'all': set(f['worlds']) >= set(worlds)})
        rows.sort(key=lambda r: (r['kind'], -len(r['worlds']), str(r.get('name') or r.get('value'))))
        disagree = [{'slot': s, 'values': {v: sorted(ws) for v, ws in vals.items()}} for s, vals in sorted(by_slot.items()) if len(vals) > 1]
        return {'at': at, 'name': self._name(at), 'records': [{'path': m, 'world': world_of(m), 'name': self._name(m)} for m in members],
                'worlds': worlds, 'facts': rows, 'disagreements': disagree}

    def knows(self, at, world, not_world):
        """What one world asserts about a thing (or, with no thing, about every thing both describe) that another does not."""
        ats = [at] if at else [m['records'][0] for m in self.shared() if world in m['worlds'] and not_world in m['worlds']]
        out = []
        for a in ats:
            u = self.union(a)
            only = [f for f in u['facts'] if world in f['worlds'] and not_world not in f['worlds']]
            if only:
                out.append({'at': u['at'], 'name': u['name'], 'facts': only})
        return out

    def shared(self, min_worlds=2):
        """Things described by several worlds: each same-joined group spanning at least min_worlds worlds."""
        seen, out = set(), []
        with self.lock:
            things = [p_ for p_ in self.names if self.is_thing(p_)]
        for p_ in sorted(things):
            if p_ in seen:
                continue
            g = self.same_as(p_)
            seen |= g
            ws = sorted({world_of(x) for x in g})
            if len(ws) >= min_worlds:
                out.append({'name': self._name(p_), 'worlds': ws, 'records': sorted(g)})
        return out

    def reach(self, worlds, limit=12):
        """Connections that exist only when every one of these worlds takes part: pairs of things joined in the graph of
        all their assertions (relations and same links, each owned by the world that asserts it) that no smaller set of
        these worlds joins. Each comes with one path, every hop tagged with the world asserting it."""
        worlds = sorted(set(worlds))
        edges = []
        with self.lock:
            for s_, refs in self.out.items():
                if '/user/web/' in s_ or '/claims/' in s_ or '/talk/' in s_:
                    continue
                holder, label = self.holder_of(s_)
                if not holder or world_of(holder) not in worlds:
                    continue
                for t, slot in refs:
                    if slot in ('source', 'sources', 'moved_to', 'different') or '/user/web/' in t or not self.is_thing(t):
                        continue
                    edges.append((holder, t, label or slot, world_of(s_)))
        def components(ws):
            parent = {}
            def find(x):
                parent.setdefault(x, x)
                while parent[x] != x:
                    parent[x] = parent[parent[x]]; x = parent[x]
                return x
            for a, b, _, w in edges:
                if w in ws:
                    parent[find(a)] = find(b)
            return find, parent
        full_find, full_parent = components(set(worlds))
        smaller = [components(set(worlds) - {w}) for w in worlds] if len(worlds) > 1 else []
        adj = {}
        for a, b, label, w in edges:
            adj.setdefault(a, []).append((b, label, w)); adj.setdefault(b, []).append((a, label + ' of', w))
        nodes = sorted(full_parent)
        out, seen_pairs = [], set()
        for a in nodes:
            if world_of(a) not in worlds:
                continue
            # breadth first from a; report targets in other worlds that only the full set connects
            prev, q = {a: None}, [a]
            while q and len(out) < limit:
                x = q.pop(0)
                for y, label, w in adj.get(x, []):
                    if y in prev:
                        continue
                    prev[y] = (x, label, w)
                    q.append(y)
                    if world_of(y) == world_of(a) or (y, a) in seen_pairs:
                        continue
                    if all(f(a) != f(y) if a in p and y in p else True for f, p in smaller):
                        hops, z = [], y
                        while prev[z]:
                            px, lb, ww = prev[z]; hops.append({'from': px, 'label': lb, 'to': z, 'asserted_by': ww}); z = px
                        hops.reverse()
                        if len({h['asserted_by'] for h in hops}) == len(worlds):
                            seen_pairs.add((a, y))
                            out.append({'from': a, 'to': y, 'from_name': self._name(a), 'to_name': self._name(y),
                                        'path': [dict(h, from_name=self._name(h['from']), to_name=self._name(h['to'])) for h in hops]})
            if len(out) >= limit:
                break
        return out

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
        to = q.get('to') or q.get('at') or q.get('of') or ''
        if to and not to.startswith('/'):
            to = '/' + to
        if u.path == '/links':
            body = {'to': to, 'matches': INDEX.links(to) if to else [], 'ready': INDEX.ready}
        elif u.path == '/by':
            body = {'to': to, 'by': INDEX.by(to) if to else {}, 'ready': INDEX.ready}
        elif u.path == '/resolve':
            body = {'matches': INDEX.resolve(q.get('text', '')), 'ready': INDEX.ready}
        elif u.path == '/around':
            labels = set(q['labels'].split(',')) if q.get('labels') else None
            body = {**INDEX.around(to, int(q.get('depth') or 2), labels), 'ready': INDEX.ready}
        elif u.path == '/unfold':
            ways = tuple(q.get('ways', 'out,in').split(','))
            body = {**INDEX.unfold(to, int(q.get('depth') or 2), ways, open_=[x for x in (q.get('open') or '').split(',') if x]), 'ready': INDEX.ready}
        elif u.path == '/placements':
            body = {'of': to, 'placements': INDEX.placements(to or '/' + q.get('of', '').lstrip('/')), 'ready': INDEX.ready}
        elif u.path == '/between':
            a = q.get('a', ''); b = q.get('b', '')
            body = {'path': INDEX.between('/' + a.lstrip('/'), '/' + b.lstrip('/')), 'ready': INDEX.ready}
        elif u.path == '/profile':
            body = {'labels': INDEX.profile(), 'ready': INDEX.ready}
        elif u.path == '/shapes':
            body = {'shapes': INDEX.shapes(int(q.get('limit') or 30)), 'ready': INDEX.ready}
        elif u.path == '/signals':
            body = {'signals': INDEX.signals(int(q.get('limit') or 20)), 'ready': INDEX.ready}
        elif u.path == '/undigested':
            with INDEX.lock:
                waiting = [(p_, v) for p_, v in INDEX.texts.items() if not v.get('digested') and (v.get('known') or v.get('unknown'))]
            cited = lambda p_: sum(1 for (s_, slot) in INDEX.into.get(p_, {}) if slot == 'source')
            waiting.sort(key=lambda pv: (-(pv[1].get('fresh') or 0) if time.time() - (pv[1].get('fresh') or 0) < 3600 else 0, -(3 * cited(pv[0]) + 2 * pv[1]['known'] + pv[1]['unknown'])))
            body = {'texts': [{'path': p_, **v, 'cited': cited(p_)} for p_, v in waiting[:int(q.get('limit') or 5)]], 'waiting': len(waiting), 'ready': INDEX.ready}
        elif u.path == '/talks':
            body = {'talks': [{'folder': f, **v} for f, v in sorted(INDEX.talks.items())], 'ready': INDEX.ready}
        elif u.path == '/worlds':
            with INDEX.lock:
                seen = {m.group(0).rstrip('/') for p_ in list(INDEX.labels_of) + list(INDEX.names) for m in [WORLD.match(p_)] if m}
            body = {'worlds': sorted(seen), 'ready': INDEX.ready}
        elif u.path == '/identities':
            body = {'candidates': INDEX.identity_candidates(to or None, int(q.get('limit') or 40)), 'ready': INDEX.ready}
        elif u.path == '/union':
            body = {**INDEX.union(to), 'ready': INDEX.ready}
        elif u.path == '/knows':
            body = {'world': q.get('world'), 'not': q.get('not'), 'things': INDEX.knows(to or None, q.get('world', ''), q.get('not', '')), 'ready': INDEX.ready}
        elif u.path == '/shared':
            body = {'things': INDEX.shared(int(q.get('min') or 2)), 'similar_names': INDEX.similar_names_differ(), 'ready': INDEX.ready}
        elif u.path == '/reach':
            body = {'worlds': (q.get('worlds') or '').split(','), 'only_with_all': INDEX.reach([w for w in (q.get('worlds') or '').split(',') if w], int(q.get('limit') or 12)), 'ready': INDEX.ready}
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
        self.related_sig = {}       # real record -> the slots its relation view was last written with
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
        # simulated peers, /<node>/<peer>/user: the node's own listing pages through its whole tree before it reaches
        # them, so they come from the peers setting and from the worlds the index has already seen on the stream
        with INDEX.lock:
            known = {m.group(2) for p_ in list(INDEX.labels_of) for m in [WORLD.match(p_)] if m and m.group(2)}
        for peer in sorted(known | {x.strip() for x in str(self.setting('peers') or '').split(',') if x.strip()}):
            out += [k['path'] for k in self.w.read(f'{self.node}/{peer}/user', 'y', limit=2000).get('children') or []]
        out += [c['path'] for c in self.w.read(self.node + '/agent', 'y', limit=2000).get('children') or [] if CHAT.fullmatch(c['path'].rsplit('/', 1)[1])]
        return out

    def scanned(self, path):
        rel = path[len(self.node):]
        if rel.startswith('/user/') or re.match(r'^/0x[0-9a-f]+/user/', rel):     # this world, and simulated peer worlds beneath it
            return True
        if rel.startswith('/agent/'):
            seg = rel.split('/')[2]
            return bool(CHAT.fullmatch(seg)) or (seg == 'weave' and '/names/' not in rel)
        return False

    def text_of(self, props):
        return ' . '.join(str(props[k]) for k in TEXT_SLOTS if isinstance(props.get(k), str) and len(props[k]) > 2)

    def absorb(self, record, write=True):
        """One record into the index: its references, its names if it is a thing, the names it uses if it holds text."""
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
        if props is None:
            return
        text = self.text_of(props)
        if not text:
            return
        here = world_of(path)
        # a text knows the names of its own world only: another world's records are reached through same links on
        # evidence, never because a word matched; so each world's texts are decomposed as that world alone knows them
        found = INDEX.resolve(text, world=here or None)
        cands = INDEX.unresolved(text, found) if INDEX.ready or not write else []
        if WORLD.match(path) and path.startswith(self.node + '/') and '/talk/' not in path and len(text) > 120:
            with INDEX.lock:                                          # a text in the world, waiting to be decomposed until it says digested
                prev = INDEX.texts.get(path) or {}
                INDEX.texts[path] = {'known': len({f['path'] for f in found}), 'unknown': len(cands), 'size': len(text),
                                     'digested': bool(props.get('/digested')), 'fresh': prev.get('fresh') or (time.time() if INDEX.ready else 0)}
        with INDEX.lock:
            for n in INDEX.candidates.get(path, []):
                s_ = INDEX.by_name.get(norm_name(n))
                if s_:
                    s_.discard(path)
            INDEX.candidates[path] = cands
            for n in cands:
                INDEX.by_name.setdefault(norm_name(n), set()).add(path)
        if write and INDEX.ready and here == self.node.lstrip('/'):
            self.offer(path, cands, bool(found))
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
        """A thing just appeared: every text that named it without a record is re-read now."""
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

    # ---- relation views: a gather cell per thing at /user/views/related/<its path>, whose secondary inputs are the
    # placements it is in; the kernel computes its relational slots live (leaders, acquisitions_of ...), nothing stored
    def related_slots(self, real):
        rels = INDEX.relations(real)
        if not rels:
            return None
        ref = lambda p_, care: {'type': 'reference', 'path': p_, 'care': care, 'case': 0}
        slots, of_count = {}, {}
        for r in rels:
            if r['way'] == 'of':
                key = (r['label'] or 'placed') + '_of'
                of_count[key] = of_count.get(key, 0) + 1
        for r in rels:
            if r['way'] == 'has':
                folder = r['via'].rsplit('/', 1)[0] if r['label'] else r['via']
                slots[segment_of(r['label'] or r['via'].rsplit('/', 1)[1])] = ref(folder, 'y' if r['label'] else 'x')
            else:
                key = (r['label'] or 'placed') + '_of'
                name = key if of_count[key] == 1 else key + '_' + r['other'].rsplit('/', 1)[1]
                slots[segment_of(name)] = ref(r['other'], 'x')
        return slots

    def write_related(self, reals):
        gather = getattr(self, '_gather', None)
        if gather is None:
            stdlib = self.w.read(self.node + '/weft/stdlib', 'y', limit=100).get('children') or []
            gather = self._gather = next((c['reference'] for c in stdlib if c['path'].endswith('/gather')), None)
        if not gather:
            return
        for real in sorted(set(reals)):
            if '/user/' not in real or real.startswith(self.node + '/user/views/'):
                continue
            view = self.node + '/user/views/related/' + real.split('/user/', 1)[1]
            slots = self.related_slots(real)
            sig = json.dumps(slots, sort_keys=True)
            if self.related_sig.get(real) == sig:
                continue
            self.related_sig[real] = sig
            if slots is None:
                if self.w.read(view, 'x').get('exists'):
                    self.pending.append({'path': view, 'action': 'cull'})
                continue
            self.pending.append({'path': view, 'slots': dict(slots, **{'sys/weft': {'type': 'reference', 'value': gather},
                                                                     'sys/tack': {'type': 'reference', 'path': real, 'care': 'x', 'case': 0}})})

    def affected(self, path):
        """The real records whose relations a touched path can change: an overlay's target and its container, a folder's container."""
        out = set()
        r = INDEX.overlay_of.get(path)
        if r:
            out.add(r)
        parts = path.split('/')
        for i in range(len(parts) - 1, 4, -1):
            out.add('/'.join(parts[:i]))
        return {x for x in out if x in INDEX.names}

    def flush(self):
        n = 0
        while self.pending:
            batch, self.pending = self.pending[:40], self.pending[40:]
            try:
                self.w.tool('write', records=batch, who=self.name); n += len(batch)
            except Exception as e:
                self.log(f'links: write refused: {str(e)[:100]}')
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
            if self.text_of(props):
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
        touched_reals = set()
        for t in line.get('touched') or []:
            if t.startswith(self.node + '/user/') and not t.startswith(self.node + '/user/views/'):
                touched_reals |= self.affected(t)
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
    _hand.run(LinksHand, settings=('port', 'peers'))
