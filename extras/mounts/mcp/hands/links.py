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
# a thing is any record under /user, at any depth, except the hands' own folders and a thing's own parts
PARTS = {'talk', 'turns', 'mentions', 'asks', 'found', 'status', 'taken', 'context', 'views', 'integrated'}
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
            if props and '/user/' in source and not source.endswith('/mentions') and '/talk/' not in source and '/web/' not in source:
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
            slot = 'mentioned' if m['path'].endswith('/mentions') else m['slot']
            path = m['path'][:-len('/mentions')] if m['path'].endswith('/mentions') else m['path']
            out.setdefault(slot, []).append(dict(m, path=path))
        return out

    # ---- vantages: the graph read from a name; nothing here knows what any label means
    def _name(self, p_):
        return self.names.get(p_) or (p_.rsplit('/', 1)[-1].replace('_', ' ') if p_ else '')

    def _edges_out(self, p_, labels=None):
        return [(t, slot) for t, slot in self.out.get(p_, []) if (labels is None or slot in labels) and not slot.startswith('sys/')]

    def _edges_in(self, p_, labels=None):
        return [(s_, slot) for (s_, slot) in self.into.get(p_, {}) if (labels is None or slot in labels) and not slot.startswith('sys/')
                and not s_.endswith('/mentions') and '/talk/' not in s_ and not s_.endswith('/context') and '/user/views/' not in s_]

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
        """The records in any world that a same slot joins to this one, either direction, transitively."""
        seen, todo = {real}, [real]
        while todo:
            p_ = todo.pop()
            with self.lock:
                nxt = [t for t, slot in self.out.get(p_, []) if slot == 'same'] + [s_ for (s_, slot) in self.into.get(p_, {}) if slot == 'same']
            for q in nxt:
                if q not in seen:
                    seen.add(q); todo.append(q)
        return seen

    def relations(self, real):
        """The relations of a thing as one union over every world that describes it (joined by same links), each tagged
        with the world that asserts it."""
        out, seen = [], set()
        for rec in sorted(self.same_as(real)):
            for r in self._relations_one(rec):
                if r['label'] == 'same' or r['other'] in self.same_as(real):
                    continue
                k = (r['way'], r['label'], r['other'])
                if k in seen:
                    continue
                seen.add(k)
                out.append(dict(r, world=world_of(r['via'] if r['way'] == 'out' else r['other']), about=rec))
        return out

    def _relations_one(self, real):
        """Every relation a thing is in, read from slots alone, labels uninterpreted:
        - out: a slot of this record names another thing (founder: forbes), or a child record of it does (founders/x: name);
        - in: a slot of another record names this thing, or a child record of another thing does."""
        out = []
        with self.lock:
            for t, slot in self._edges_out(real):
                if '/user/web/' not in t:
                    out.append({'way': 'out', 'label': slot, 'other': t, 'name': self._name(t), 'via': real, 'note': {}})
            for s_, slot in self._edges_in(real):
                holder, label = s_, slot
                parts = s_.split('/user/', 1)[1].split('/') if '/user/' in s_ else []
                # a child record that holds the relation (a qualified or many-valued one) reads as its parent's
                if len(parts) >= 4 and s_ not in self.names_top():
                    holder, label = '/'.join(s_.split('/')[:-2]), s_.split('/')[-2]
                if '/user/web/' in holder or holder == real or slot == 'moved_to' or s_ in self.forwards:
                    continue
                out.append({'way': 'in', 'label': label, 'other': holder, 'name': self._name(holder), 'via': s_,
                            'note': self.literal_of.get(s_, {}) if holder != s_ else {}})
            for c in self.children(real):
                if c in self.overlay_of or c in self.forwards:
                    continue
                for g in [c] + self.children(c):
                    for t, slot in self._edges_out(g):
                        if g != real and '/user/web/' not in t:
                            label = c.rsplit('/', 1)[1] if g != c else c.rsplit('/', 1)[1]
                            out.append({'way': 'out', 'label': label, 'other': t, 'name': self._name(t), 'via': g, 'note': self.literal_of.get(g, {})})
        seen, uniq = set(), []
        for r in out:
            k = (r['way'], r['label'], r['other'])
            if k not in seen:
                seen.add(k); uniq.append(r)
        return uniq

    def unfold(self, at, depth=2, ways=('out', 'in'), skip=('source', 'sources', 'mentioned'), cap=24):
        """A record as a world: its relations as virtual folders (a label, or a label and 'of' for the other direction),
        each holding the related things, unfolded again beneath them to a depth. Computed, never stored; the same
        facts unfold differently from every vantage."""
        at = self.real(at.rstrip('/'))
        def walk(p_, d, trail):
            if d <= 0:
                return []
            folders = {}
            for r in self.relations(p_):
                if r['way'] not in ways or r['label'] in skip or self.same_as(r['other']) & trail:
                    continue                                  # one thing, whatever world names it, appears once on a branch
                key = r['label'] if r['way'] == 'out' else r['label'] + ' of'
                folders.setdefault(key, []).append(r)
            # the parts each world files under the thing (its products, its sections), by their folder, as part of the union
            for rec in sorted(self.same_as(p_)):
                for c in self.children(rec):
                    seg = c.rsplit('/', 1)[1]
                    if seg in PARTS or seg in skip or c in self.names or c in self.forwards:
                        continue
                    for g in self.children(c):
                        if g in self.names and not (self.same_as(g) & trail):
                            folders.setdefault(seg, []).append({'way': 'part', 'label': seg, 'other': g, 'name': self._name(g), 'world': world_of(g), 'note': {}})
            for key in list(folders):                         # the same thing named from two worlds is one item in a folder
                merged, seen_sets = [], []
                for r in folders[key]:
                    ss = self.same_as(r['other'])
                    if any(ss & x for x in seen_sets):
                        continue
                    seen_sets.append(ss); merged.append(r)
                folders[key] = merged
            out = []
            for key, rs in sorted(folders.items()):
                items = []
                for r in rs[:cap]:
                    node = {'path': r['other'], 'name': r['name'], 'world': world_of(r['other']), 'by': r.get('world'), 'note': {k: v for k, v in (r.get('note') or {}).items() if not str(v).startswith('/')}}
                    kids = walk(r['other'], d - 1, trail | self.same_as(r['other']))
                    if kids:
                        node['folders'] = kids
                    items.append(node)
                out.append({'label': key, 'items': items})
            return out
        return {'at': at, 'name': self._name(at), 'world': world_of(at), 'same': sorted(x for x in self.same_as(at) if x != at), 'folders': walk(at, depth, set(self.same_as(at)))}

    def names_top(self):
        """Things filed directly in a top folder (/user/<folder>/<slug>): their slots are their own relations."""
        return {p_ for p_ in self.names if p_.count('/') == 4}

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
                if '/user/' not in src or src.endswith('/mentions') or '/talk/' in src:
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
            out['undecomposed'] = sorted((p_ for p_, v in self.texts.items() if not v.get('digested') and len(self.out.get(p_.rsplit('/', 1)[0], [])) <= 1 and v.get('size', 0) > 400))[:limit]
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
            body = {**INDEX.unfold(to, int(q.get('depth') or 2), ways), 'ready': INDEX.ready}
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
        for c in self.w.read(self.node, 'y', limit=200).get('children') or []:          # simulated peers: /<node>/<peer>/user
            if re.fullmatch(r'0x[0-9a-f]+', c['path'].rsplit('/', 1)[1]):
                out += [k['path'] for k in self.w.read(c['path'] + '/user', 'y', limit=2000).get('children') or []]
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
        if path.startswith(self.node + '/user/') and '/talk/' not in path and len(text) > 120:
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
    _hand.run(LinksHand, settings=('port',))
