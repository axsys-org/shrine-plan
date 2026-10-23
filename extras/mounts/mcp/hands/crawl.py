"""The crawl hand: curiosity, in the background, never in a chat.

It walks the person's things for stubs (a record that is little more than a name) and thin records, and writes a
research ask for each into the one web queue, at low priority (a chat's asks always go first). When the web hand fills
one, the crawler integrates it with one model call: the facts the rows state go onto the record with a source
reference to the page region; every name the rows mention is resolved against the world's own name index, so it
becomes a reference to the record that already exists (this is where unrelated digging finds that someone is one hop
from something already known) or a new stub one hop further out, which the next pass researches in its turn.

Bounded: at most OPEN asks open at once, at most MAX_HOP hops from what a person or a chat put in the world, and a
stub that came back empty is not asked about again.

    /agent/crawl/asks/<kind>_<slug>          {asked, scope, shape, about: ref, hop, priority}
    /agent/crawl/asks/<id>/integrated        {state: done | empty, writes, when}

    python3 crawl.py <base> [--node 0x11] [--once] [--model anthropic/claude-haiku-5.5]
"""
import importlib.util
import json
import os
import re
import time

_here = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location('agent_hand', os.path.join(_here, 'agent.py'))
_agent = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_agent)
_hand = _agent._hand
Hand, World, segment_of, case_of = _hand.Hand, _hand.World, _hand.segment_of, _hand.case_of
call_model, parse_json, render = _agent.call_model, _agent.parse_json, _agent.render

DEFAULT_MODEL = 'anthropic/claude-haiku-5.5'
ENDPOINT = _agent.DEFAULT_ENDPOINT
OPEN = 4
MAX_HOP = 3
SKIP = {'web', 'recipes', 'views', 'sources', 'eng', 'game', 'legal'}
META = {'name', 'source', 'hop', 'kind', 'researched', 'page', 'quote', 'digest'}

SHAPES = {
    'people': 'born: YYYYMMDD, nationality: text, role: text (current title), org: text (current organisation, a name), '
              'known_for: text (a work or project, a name), education: text (an institution, a name), site: text (a url)',
    'orgs': 'kind: text, founded: YYYY, hq: text (city, country), website: text, leader: text (a person, a name), '
            'parent: text (an organisation, a name), employees: number, as_of: YYYY',
    'languages': 'creator: text (a person or organisation, a name), first_appeared: YYYY, paradigm: text, typing: text, website: text',
    'publications': 'publisher: text (an organisation, a name), founded: YYYY, website: text, issn: text, editor: text (a person, a name)',
    'products': 'maker: text (an organisation, a name), creator: text (a person, a name), launched: YYYY, kind: text, website: text',
    'licenses': 'spdx: text, kind: text (permissive or copyleft), osi_approved: true or false, published: YYYY',
    'places': 'country: text (a name), kind: text, population: number, as_of: YYYY',
}
DEFAULT_SHAPE = 'kind: text, website: text, maker_or_owner: text (an organisation or person, a name), founded: YYYY'

INTEGRATE = """You integrate web research into a world of records. You are given one record that was researched (its path,
its slots, its hop), the rows the web returned for it (each with a source reference to the page region it came from and
the quote that states it), and for each name mentioned in the rows, the records in the world that might be that thing.

Reply with one JSON object: {"writes": [ {"path": ..., "action": "poke" | "make", "slots": {...}} ]}, at most 25 writes.
- Poke the researched record with the facts the rows state: numbers as numbers, days as YYYYMMDD numbers, flags as
  true/false, text only for a code or a quotation; and a source slot set to {"type": "reference", "path": <the
  row's source path>, "care": "x", "case": 0} (the region, never the ask).
- A fact that names another thing (a person, organisation, place, product, language, publication) is a reference, never
  the name as text: {"type": "reference", "path": <path>, "care": "x", "case": 0}. Use an existing record when one of
  the candidates is plainly the same thing (same name and kind, consistent with the rows). Otherwise make a stub at
  /0x11/user/<kinds>/<slug> (people, orgs, places, products, languages, publications, licenses; slug lowercase
  letters, digits, underscores) with {"name": <the name>, "hop": <the researched record's hop + 1>} and reference it.
- Never invent a fact the rows do not state, never make a second record for a thing that has one, no summaries, no
  descriptions, no status slots.
- A fact that will change on its own (employees, followers, stars, a price, a latest version) also gets a recipe:
  {"path": "/0x11/user/recipes/<slug>", "action": "make", "slots": {"record": <reference to the record>, "slot": <name>,
  "url": <the page url it came from>, "kind": "css", "parse": "number" or "day" or "text", "every": 86400}}.
"""


def ref(path, care='x'):
    return {'type': 'reference', 'path': path, 'care': care, 'case': 0}


def norm(name):
    return re.sub(r'[^a-z0-9]+', ' ', str(name).lower()).strip()


class CrawlHand(Hand):
    name = 'crawl'
    every = 60.0

    def __init__(self, world, log=print, **overrides):
        super().__init__(world, log=log, **overrides)
        self.model = self.setting('model') or DEFAULT_MODEL
        self.folder = '/' + world.node + '/agent/crawl'
        self.user = '/' + world.node + '/user'
        self.backoff = {}               # record -> when a failed search may be tried again

    def quiet(self, item):
        """A fill under one of my asks wakes me, though the web hand wrote it."""
        if any(t.startswith(self.folder + '/asks/') and ('/found/' in t or t.endswith('/status')) for t in (item.get('touched') or [])):
            return False
        return super().quiet(item)

    # ---- the world's things, by kind
    def kinds(self):
        top = self.w.read(self.user, 'y', limit=200)
        return [c['path'] for c in top.get('children', []) if c['path'].rsplit('/', 1)[1] not in SKIP]

    def records(self, kind_path):
        page = self.w.read(kind_path, 'y', limit=500)
        return [(c['path'], {k.lstrip('/'): v for k, v in (c.get('properties') or {}).items() if not k.startswith('/sys')})
                for c in page.get('children', []) if c.get('exists')]

    def name_index(self):
        """name (normalised) -> [(path, kind)], over every kind folder: how a name in a row finds the record it is."""
        idx = {}
        for kp in self.kinds():
            kind = kp.rsplit('/', 1)[1]
            for path, props in self.records(kp):
                for n in {props.get('name'), path.rsplit('/', 1)[1].replace('_', ' ')}:
                    if n:
                        idx.setdefault(norm(n), []).append((path, kind))
        return idx

    def public(self, path, props):
        """A person the crawler may research: one with a public role already recorded (a title, an organisation, a
        work), or one the crawl itself reached from an organisation's or a product's research (hop above 0)."""
        if int(float(props.get('hop') or 0)) > 0:
            return True
        return any(k in props for k in ('role', 'title', 'org', 'known_for', 'leader_of', 'founded', 'position'))

    # ---- seeding: stubs become asks
    def open_asks(self):
        page = self.w.read(self.folder + '/asks', 'y', limit=500)
        out = {}
        for c in page.get('children', []):
            if not c.get('exists'):
                continue
            kids = {k['path'].rsplit('/', 1)[1] for k in (self.w.read(c['path'], 'y', limit=20).get('children') or []) if k.get('exists')}
            out[c['path'].rsplit('/', 1)[1]] = 'integrated' in kids
        return out

    def seed(self):
        asks = self.open_asks()
        room = OPEN - sum(1 for done in asks.values() if not done)
        if room <= 0:
            return 0
        candidates = []
        for kp in self.kinds():
            kind = kp.rsplit('/', 1)[1]
            for path, props in self.records(kp):
                aid = segment_of(f'{kind}_{path.rsplit("/", 1)[1]}')
                if aid in asks or self.backoff.get(path, 0) > time.time():
                    continue                  # the ask is the memory: one per record, whatever came of it
                hop = int(float(props.get('hop') or 0))
                facts = [k for k in props if k not in META]
                if hop > MAX_HOP or len(facts) > 2:
                    continue
                if kind == 'people' and not self.public(path, props):
                    continue                  # a private person named in a document is not researched by curiosity
                candidates.append((hop, len(facts), kind, path, props, aid))
        candidates.sort(key=lambda c: (c[0], c[1]))
        recs = []
        for hop, _, kind, path, props, aid in candidates[:room]:
            name = props.get('name') or path.rsplit('/', 1)[1].replace('_', ' ')
            singular = kind[:-1] if kind.endswith('s') else kind
            recs.append({'path': f'{self.folder}/asks/{aid}', 'slots': {
                'asked': f'What is known about {name} (a {singular})?', 'scope': '', 'shape': SHAPES.get(kind, DEFAULT_SHAPE),
                'entity': name, 'kind': singular, 'about': ref(path), 'hop': hop, 'priority': hop + 1}})
        if recs:
            self.w.tool('write', records=[{'path': self.folder, 'slots': {'name': 'crawl'}}, {'path': self.folder + '/asks', 'slots': {}}] + recs, who=self.name)
            self.log(f'crawl: seeded {len(recs)} asks: ' + ', '.join(r['path'].rsplit('/', 1)[1] for r in recs))
        return len(recs)

    # ---- integration: a filled ask becomes facts and links
    def integrate(self, ask):
        props = {k.lstrip('/'): v for k, v in (self.w.read(ask, 'x').get('properties') or {}).items() if not k.startswith('/sys')}
        about = re.sub(r'^/h/[xyz]/\d+/\d+', '', str(props.get('about') or ''))
        hop = int(float(props.get('hop') or 0))
        rows = [c for c in (self.w.read(ask + '/found', 'y', limit=100).get('children') or []) if c.get('exists')]
        status = {k.lstrip('/'): v for k, v in (self.w.read(ask + '/status', 'x').get('properties') or {}).items()}
        if not rows:
            if status.get('state') == 'failed':
                # the search never answered: the ask goes, the record waits half an hour, then it is asked again
                self.w.tool('write', records=[{'path': ask, 'action': 'cull'}], who=self.name)
                self.backoff[about] = time.time() + 1800
                self.log(f'crawl {ask.rsplit("/", 1)[1]}: search failed ({status.get("reason")}); will ask again later')
            elif status.get('state') == 'empty':
                self.w.tool('write', records=[{'path': ask + '/integrated', 'slots': {'state': 'empty', 'when': int(time.time())}},
                                              {'path': about, 'action': 'poke', 'slots': {'researched': int(time.time())}}], who=self.name)
            return 0
        record = self.w.read(about, 'x')
        idx = self.name_index()
        names = set()
        for r in rows:
            for k, v in (r.get('properties') or {}).items():
                if isinstance(v, str) and not v.startswith('/h/') and 1 < len(v) < 80 and re.match(r'[A-Z0-9]', v.strip()):
                    names.add(v.strip())
        candidates = {}
        for n in names:
            key = norm(n)
            hits = idx.get(key, [])
            if not hits:                                          # Google LLC finds Google; Google finds Google LLC
                hits = [p for k2, ps in idx.items() if k2 and (k2 in key or key in k2) and min(len(k2), len(key)) > 3 for p in ps]
            if hits:
                candidates[n] = [p for p, _ in hits[:4]]
        lines = [f'RESEARCHED RECORD: {about}  (hop {hop})', '\n'.join(render(record)), '', 'ROWS:']
        for r in rows:
            lines.append('  ' + r['path'].rsplit('/', 1)[1] + '  ' + ', '.join(f'{k.lstrip("/")}: {str(v)[:200]}' for k, v in sorted((r.get('properties') or {}).items())))
        lines += ['', 'CANDIDATES (a name in the rows -> records that might be it):'] + ([f'  {n} -> {", ".join(ps)}' for n, ps in sorted(candidates.items())] or ['  (none)'])
        try:
            text = call_model(ENDPOINT, self.model, [{'role': 'system', 'content': INTEGRATE}, {'role': 'user', 'content': '\n'.join(lines)}])
            if os.environ.get('CRAWL_RAW_LOG'):
                with open(os.environ['CRAWL_RAW_LOG'], 'a') as f:
                    f.write('\n===== ' + ask + '\n--- asked:\n' + '\n'.join(lines)[-3000:] + '\n--- replied:\n' + text + '\n')
            reply = parse_json(text)
            if 'writes' not in reply:
                start = text.find('{')
                reply = json.JSONDecoder().raw_decode(text[start:])[0] if start >= 0 else {}
        except Exception as e:
            self.log(f'crawl {ask}: model failed: {str(e)[:120]}')
            return 0
        asked_writes = [w for w in (reply.get('writes') or []) if isinstance(w, dict)]
        writes = [w for w in asked_writes if str(w.get('path', '')).startswith(self.user + '/')][:25]
        if len(writes) < len(asked_writes):
            self.log(f'crawl {ask}: {len(asked_writes) - len(writes)} writes outside /user dropped')
        for w in writes:
            if w.get('action') == 'make' and self.w.read(w['path'], 'x').get('exists'):
                w['action'] = 'poke'                              # never replace a record that already exists
        landed = 0
        for w in writes:
            try:
                r = self.w.tool('write', records=[w], who=self.name)
                if r.get('refused'):
                    self.log(f'crawl {ask}: refused {w.get("path")}: {r.get("reason")}')
                landed += 0 if r.get('refused') else 1
            except Exception as e:
                self.log(f'crawl {ask}: refused {w.get("path")}: {str(e)[:80]}')
        self.w.tool('write', records=[{'path': ask + '/integrated', 'slots': {'state': 'done', 'writes': landed, 'when': int(time.time())}},
                                      {'path': about, 'action': 'poke', 'slots': {'researched': int(time.time())}}], who=self.name)
        linked = sum(1 for w in writes if any(isinstance(v, dict) and v.get('type') == 'reference' and v.get('path', '').startswith(self.user) and v.get('path') != about for v in (w.get('slots') or {}).values()))
        self.log(f'crawl {ask.rsplit("/", 1)[1]}: {landed} writes, {linked} with links, {len(candidates)} names resolved to existing records')
        return landed

    def integrate_ready(self):
        n = 0
        for aid, done in self.open_asks().items():
            if not done:
                n += self.integrate(f'{self.folder}/asks/{aid}')
        return n

    def line(self, line):
        if any(t.startswith(self.folder + '/asks/') for t in (line.get('touched') or [])):
            return self.integrate_ready()
        return 0

    def tick(self, now):
        return self.integrate_ready() + self.seed()


if __name__ == '__main__':
    _hand.run(CrawlHand, settings=('model',))
