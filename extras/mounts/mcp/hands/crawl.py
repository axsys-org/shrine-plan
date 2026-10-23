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
        self.scanned = False            # the holes beneath the person's things, found once, then followed on the stream

    def quiet(self, item):
        """A fill under one of my asks wakes me, though the web hand wrote it."""
        touched = item.get('touched') or []
        if any(t.startswith(self.folder + '/asks/') and ('/found/' in t or t.endswith('/status')) for t in touched):
            return False
        if any(t.startswith(self.user) and re.search(r'/holes/[^/]+$', t) for t in touched):
            return False                                      # a hole written by any hand is mine to schedule
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

    # ---- holes: a question that stays attached to its thing, looked at again on its schedule
    def today(self):
        d = (self.w.read('/' + self.w.node + '/clock', 'x').get('properties') or {}).get('/day') or time.strftime('%Y-%m-%d')
        return int(re.sub(r'\D', '', str(d))[:8] or 0)

    def hole_id(self, hole):
        return segment_of(hole.replace(self.user + '/', '').replace('/holes/', '/').replace('/', '_'))

    def scan_holes(self):
        n = 0
        for kp in self.kinds():
            stack = list(self.w.read(kp, 'z', limit=3000).get('children') or [])
            while stack:
                c = stack.pop()
                if re.search(r'/holes/[^/]+$', c['path']):
                    n += self.register(c['path']) if c.get('exists') else 0
                else:
                    stack.extend(c.get('children') or [])
        self.scanned = True
        if n:
            self.log(f'crawl: {n} holes registered')
        return n

    def register(self, hole):
        """The index entry the queue page reads: /agent/crawl/holes/<id> mirrors the hole's schedule."""
        rec = self.w.read(hole, 'x')
        idx = f'{self.folder}/holes/{self.hole_id(hole)}'
        if not rec.get('exists'):
            if self.w.read(idx, 'x').get('exists'):
                self.w.tool('write', records=[{'path': idx, 'action': 'cull'}], who=self.name)
            return 0
        p = {k.lstrip('/'): v for k, v in (rec.get('properties') or {}).items() if not k.startswith('/sys')}
        record = hole.rsplit('/holes/', 1)[0]
        self.w.tool('write', records=[{'path': self.folder, 'slots': {'name': 'crawl'}}, {'path': self.folder + '/holes', 'slots': {}},
            {'path': idx, 'slots': {'hole': ref(hole), 'record': ref(record), 'slot': str(p.get('slot') or hole.rsplit('/', 1)[1]),
                                    'kind': str(p.get('kind') or 'unknown'), 'next': int(float(p.get('next') or 0)), 'due': int(float(p.get('due') or 0)),
                                    'tries': int(float(p.get('tries') or 0)), 'asked': str(p.get('asked') or '')[:300], 'reason': str(p.get('reason') or '')[:160]}}], who=self.name)
        return 1

    def hole_index(self):
        page = self.w.read(self.folder + '/holes', 'y', limit=500)
        return [(c['path'], {k.lstrip('/'): v for k, v in (c.get('properties') or {}).items() if not k.startswith('/sys')})
                for c in page.get('children', []) if c.get('exists')]

    def schedule_holes(self, now):
        """Every hole whose time has come becomes an ask in the web queue: watch and until ahead of unknown."""
        page = self.w.read(self.folder + '/asks', 'y', limit=500)
        open_for = set()
        done = self.open_asks()
        for c in page.get('children', []):
            h = (c.get('properties') or {}).get('/hole')
            if c.get('exists') and h and not done.get(c['path'].rsplit('/', 1)[1]):
                open_for.add(re.sub(r'^/h/[xyz]/\d+/\d+', '', str(h)))
        day, n = None, 0
        for idx, e in self.hole_index():
            hole = re.sub(r'^/h/[xyz]/\d+/\d+', '', str(e.get('hole') or ''))
            record = re.sub(r'^/h/[xyz]/\d+/\d+', '', str(e.get('record') or ''))
            if not hole or hole in open_for or float(e.get('next') or 0) > now:
                continue
            if e.get('kind') == 'until' and int(float(e.get('due') or 0)) > 0:
                day = day or self.today()
                if int(float(e['due'])) > day:
                    continue                                  # its date of expectation has not come
            rec = self.w.read(hole, 'x')
            if not rec.get('exists'):
                self.w.tool('write', records=[{'path': idx, 'action': 'cull'}], who=self.name); continue
            p = {k.lstrip('/'): v for k, v in (rec.get('properties') or {}).items() if not k.startswith('/sys')}
            slot = str(p.get('slot') or hole.rsplit('/', 1)[1])
            name = (self.w.read(record, 'x').get('properties') or {}).get('/name') or record.rsplit('/', 1)[1].replace('_', ' ')
            slots = {'asked': str(p.get('asked') or f'What is the {slot.replace("_", " ")} of {name}?'), 'shape': str(p.get('shape') or f'{slot}: text, as_of: YYYYMMDD'),
                     'about': ref(record), 'hole': ref(hole), 'slot': slot, 'priority': 1 if p.get('kind') in ('watch', 'until') else 2}
            if p.get('query'):
                slots['query'] = str(p['query'])
            aid = f'hole_{idx.rsplit("/", 1)[1]}_{int(now)}'
            self.w.tool('write', records=[{'path': f'{self.folder}/asks/{aid}', 'slots': slots},
                                          {'path': hole, 'action': 'poke', 'slots': {'last_tried': int(now)}}], who=self.name)
            n += 1
        if n:
            self.log(f'crawl: {n} holes sent to the web queue')
        return n

    def settle_hole(self, ask, props, landed, found, failed=False):
        """After a hole's ask: resolved (gone), refreshed (a watch, looked at again after every), or looked at again later."""
        hole = re.sub(r'^/h/[xyz]/\d+/\d+', '', str(props['hole']))
        idx = f'{self.folder}/holes/{self.hole_id(hole)}'
        hp = {k.lstrip('/'): v for k, v in (self.w.read(hole, 'x').get('properties') or {}).items() if not k.startswith('/sys')}
        kind, every, tries, now = str(hp.get('kind') or 'unknown'), float(hp.get('every') or 86400), int(float(hp.get('tries') or 0)), time.time()
        recs = [{'path': ask, 'action': 'cull'}]
        if landed and kind != 'watch':
            recs += [{'path': hole, 'action': 'cull'}, {'path': idx, 'action': 'cull'}]; outcome = 'resolved'
        else:
            if failed:
                nxt, outcome = now + 1800, 'search failed; soon again'
            elif landed:
                tries, nxt, outcome = 0, now + every, 'refreshed'
            else:
                tries += 1
                nxt = now + (every if kind in ('watch', 'until') else min(86400 * 2 ** min(tries - 1, 5), 30 * 86400))
                outcome = f'nothing found ({tries} tries)' if not found else f'rows came back but {props.get("slot")} did not land ({tries} tries)'
            change = {'next': int(nxt), 'tries': tries, 'last_tried': int(now), 'reason': outcome}
            recs += [{'path': hole, 'action': 'poke', 'slots': change}, {'path': idx, 'action': 'poke', 'slots': {k: v for k, v in change.items() if k != 'last_tried'}}]
        self.w.tool('write', records=recs, who=self.name)
        self.log(f'crawl hole {hole.replace(self.user + "/", "")}: {outcome}')

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
            singular = {'people': 'person'}.get(kind) or (kind[:-1] if kind.endswith('s') else kind)
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
        is_hole = bool(props.get('hole'))
        if not rows:
            if is_hole:
                if status.get('state') in ('failed', 'empty'):
                    self.settle_hole(ask, props, landed=False, found=0, failed=status.get('state') == 'failed')
                return 0
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
        before = {k.lstrip('/'): v for k, v in (record.get('properties') or {}).items()}
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
        if is_hole:
            lines.insert(1, f'THE HOLE: the slot {props.get("slot")} on this record. When the rows answer it, poke that slot (and as_of: the day the rows state, YYYYMMDD) with its source; otherwise write nothing for it.')
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
        if is_hole:
            after = {k.lstrip('/'): v for k, v in (self.w.read(about, 'x').get('properties') or {}).items()}
            slot = str(props.get('slot') or '')
            hit = slot in after and (str(after[slot]) != str(before.get(slot)) or self.w.read(re.sub(r'^/h/[xyz]/\d+/\d+', '', str(props['hole'])), 'x').get('properties', {}).get('/kind') == 'watch')
            self.settle_hole(ask, props, landed=hit, found=len(rows))
            return landed
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
        touched = line.get('touched') or []
        n = 0
        if (line.get('who') or '') != self.name:
            for t in touched:
                if t.startswith(self.user) and re.search(r'/holes/[^/]+$', t):
                    n += self.register(t)
            if n:
                n += self.schedule_holes(time.time())
        if any(t.startswith(self.folder + '/asks/') for t in touched):
            n += self.integrate_ready()
        return n

    def tick(self, now):
        if not self.scanned:
            self.scan_holes()
        return self.integrate_ready() + self.schedule_holes(now) + self.seed()


if __name__ == '__main__':
    _hand.run(CrawlHand, settings=('model',))
