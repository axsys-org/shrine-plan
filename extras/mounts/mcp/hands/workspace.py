"""The workspace hand: the main agent of every workspace. It observes what the workspace holds, reads every source
the person put in, turns what the sources state into the world's things and statements, researches only what is
asked and not already answered, and composes the reading.

The rule: sources are evidence, not ontology. The domain namespace (/user/<kind>/<slug>) holds things of meaning at
shared names, with their statements beneath them and a source reference on each; the text and bytes of a source live
in the agent's archive, outside the domain, one click from any statement. Nothing else enters the world: no page
regions, no excerpts, no name without a statement.

    /user/workspaces/<ws>                    {name}                                 (the page)
    /user/workspaces/<ws>/inputs/i<n>        {name, text | url | image} as dropped; this hand adds title, summary, archive
    /user/workspaces/<ws>/inputs/i<n>/pages/<slug>   {pages: ref(page), note, source}   pages found for a request
    /user/workspaces/<ws>/asks/t<n>          {task, who, state, detail, found, about}   one record per piece of work, kept
    /user/workspaces/<ws>/status             {status, busy}
    /user/workspaces/<ws>/views/reading/v<n> the composed reading, one version per round
    /user/<kind>/<slug>                      a thing: {name}; the kind is the model's own plural word (people, companies, places...)
    /user/<kind>/<slug>/<relation>/<slug>    a statement beneath its subject: {<relation>: ref(object) | value, note, source}
    /user/web/pages/<host>/<slug>            a page's identity: {name, url, title, summary, archive}
    /agent/hands/workspace/archive/<slug>    the evidence: {text | image, url}, outside the domain

Per line on the stream:
    an input           observed with the rest of the workspace. A file (image) is transcribed by the vision model; a
                       url is read; a pasted record's own slots are read as statements; a text is judged: a source is
                       read like a page, a request is planned against what the workspace already holds, after every
                       other input has been read.
    reading a source   the names the source uses are matched against what the namespace already holds (a name already
                       known, in any kind, is that thing, and the model is told so); one model call per source (long
                       ones in chunks) yields the things it names, each with its kind, and the statements it makes:
                       subject, relation, object or value, the sentence as the note; concepts and the things that
                       instance them are tied by "is a". Statements land beneath the subject, idempotent; a second
                       source for the same statement lands as evidence beneath it. A thing with no statement never lands.
    a request          planned against the workspace: sub-questions only for what the inputs do not already answer, none
                       into a private person's own records; each is searched with the page text returned in the hit,
                       each hit judged against the question and read in one call; only a page that answered lands (its
                       identity, its statements, its text archived), referenced beneath the request; one follow-up
                       round on the gaps; then the reading.
"""
import importlib.util
import json
import os
import re
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

_here = os.path.dirname(os.path.abspath(__file__))
def _load(name):
    spec = importlib.util.spec_from_file_location('hand_' + name, os.path.join(_here, name + '.py'))
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod
_hand = _load('hand')
World, Hand, segment_of = _hand.World, _hand.Hand, _hand.segment_of
_web = _load('web')

ENDPOINT = 'https://openrouter.ai/api/v1/chat/completions'
DEFAULT_MODEL = os.environ.get('WORKSPACE_MODEL') or 'google/gemini-2.5-flash'
WORKERS = 8                 # jobs (an input, a request) at once, across workspaces
SEARCH_LIMIT = 5            # hits per sub-question, each with its page text
SUBQUESTIONS = 4            # sub-questions a request is split into, at most
ROUNDS = 2                  # search rounds per request: the plan, then one follow-up on the gaps
CHUNK = 9000                # characters of a source read in one model call: a reply must fit the model's answer
TEXT_CAP = 120000           # characters of a source archived
NOTE = 220
KNOWN_CAP = 80              # known things shown to the model with a source
BIG = 400                   # a kind with more records than this is a registry bucket, not consulted whole
LEGAL = re.compile(r"\b(incorporated|inc|corporation|corp|company|co|llc|l\.l\.c|ltd|limited|plc|lp|llp|gmbh|s\.?p\.?a|s\.?a)\b\.?", re.I)
GENERIC = {'company', 'companies', 'organization', 'organizations', 'product', 'products', 'material', 'materials', 'thing', 'things',
           'item', 'items', 'people', 'person', 'place', 'places', 'document', 'documents', 'record', 'records', 'page', 'pages',
           'system', 'systems', 'service', 'services', 'solution', 'solutions', 'equipment', 'technology', 'technologies',
           'information', 'data', 'website', 'web site', 'contact', 'contacts', 'other', 'others', 'various', 'none', 'unknown', 'it', 'they'}
RESERVED = {'name', 'note', 'source', 'sources', 'sys', 'same', 'status', 'state', 'about', 'pages', 'inputs', 'asks', 'views',
            'world', 'title', 'summary', 'text', 'url', 'image', 'fetched', 'value', 'evidence', 'archive'}
NOT_KINDS = {'workspaces', 'web', 'registries'}


def same_name(name):
    """The spelling under which two names are one: lowercase, no punctuation, no legal suffix, one space."""
    t = LEGAL.sub(' ', str(name or '').lower())
    t = re.sub(r"[^a-z0-9 ]+", ' ', t)
    return re.sub(r'\s+', ' ', t).strip()


PLURALS = {'people', 'children', 'men', 'women', 'media', 'data', 'series', 'species', 'staff', 'personnel', 'aircraft'}   # plurals the rule below cannot spell


def kind_of(word, known=()):
    """The model's kind word as a folder: lowercase, plural, one segment. A singular is spelled plural the way a kind
    already in the namespace spells it, else by the ordinary English rule; a word is never invented."""
    w = segment_of(str(word or '').strip().lower().replace('_', ' ')) or 'things'
    if w in known or w in PLURALS or (w.endswith('s') and not w.endswith('ss')):
        return w
    for cand in (w + 's', w + 'es', (w[:-1] + 'ies') if w.endswith('y') else ''):
        if cand and cand in known:
            return cand
    if w.endswith('y') and len(w) > 2 and w[-2] not in 'aeiou':
        return w[:-1] + 'ies'
    if w.endswith(('s', 'x', 'z', 'ch', 'sh')):
        return w + 'es'
    return w + 's'


def ref(path, care='x'):
    return {'type': 'reference', 'value': '/h/%s/0/%d%s' % (care, len(path.split('/')) - 1, path)}


PART = 8000                 # a value longer than this is kept as parts <slot>/<n>: a read shows a value over 8 KB only by size


def whole(rec, key):
    """A value that may be kept as parts: the slot itself when it is a string, else its parts in order."""
    v = rec.get(key)
    if isinstance(v, str):
        return v
    parts = sorted(((int(k.rsplit('/', 1)[-1]), rec[k]) for k in rec if k.startswith(key + '/') and k.rsplit('/', 1)[-1].isdigit() and isinstance(rec[k], str)), key=lambda x: x[0])
    return ''.join(p for _, p in parts)


def parted(key, value):
    """The slots a value is written as: the slot itself when short, else parts."""
    value = str(value or '')
    if len(value) <= PART:
        return {key: value} if value else {}
    return {key + '/' + str(i): value[j:j + PART] for i, j in enumerate(range(0, len(value), PART))}


def call_model(model, system, user, image=None, timeout=150, max_tokens=16000):
    """One JSON answer from the model; `image` is a data URL shown with the text."""
    key = os.environ.get('OPENROUTER_API_KEY') or ''
    headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key}
    content = user if not image else [{'type': 'text', 'text': user}, {'type': 'image_url', 'image_url': {'url': image}}]
    body = json.dumps({'model': model, 'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': content}],
                       'temperature': 0, 'max_tokens': max_tokens, 'response_format': {'type': 'json_object'}}).encode()
    reply = json.load(urllib.request.urlopen(urllib.request.Request(ENDPOINT, body, headers), timeout=timeout))
    text = (reply.get('choices') or [{}])[0].get('message', {}).get('content') or '{}'
    start = text.find('{')
    if start < 0:
        return {}
    try:
        obj, _ = json.JSONDecoder().raw_decode(text[start:])
    except ValueError:
        return {}
    return obj if isinstance(obj, dict) else {}


READ = """You read one source into the world's ontology: the things it names and the statements it makes about them. Reply with
one JSON object:
{"title": "<what the source is, a few words>", "summary": "<one sentence: what it says>",
 "things": [{"name": "<canonical name>", "kind": "<a plural common noun: people, companies, agencies, places, products,
   documents, events, programs, laws, materials, concepts, ...>", "aliases": ["<other spellings used in the source>"]}],
 "statements": [{"subject": "<a thing's name>", "relation": "<a short relation: makes, located in, part of, issued by, born on,
   is a, works for, capacity, ...>", "object": "<a thing's name>" OR "value": "<a date, number, amount, identifier or short
   phrase>", "note": "<the sentence or clause of the source that states it>"}]}
What a thing is: anything the source names specifically and that another source could name again: every person, organization,
place, product or model, document, event, program, law, and every concept it uses as a class of things (an environmental
control unit; a military environmental control unit as a narrower concept). A specific product is tied to its concept by an
"is a" statement, a narrower concept to the broader one the same way. Resolve pronouns and references ("the company", "it",
"she") to the thing meant. Not things: generic words (customers, the product line), identifiers, dates, amounts, quantities,
specifications, which are values of a statement (capacity: 5 ton). A thing that is the same as a KNOWN thing is given the
KNOWN name exactly; spell every other name short and canonical, without descriptions. Every thing appears in at least one
statement. Every statement is one fact the source states, with its own sentence as the note, never a guess or a summary. Be
exhaustive: a long source yields many statements. Reply with the JSON only."""

OBSERVE = """You are the main agent of a research workspace. You are given the whole workspace: what the person put in (files,
pages, pasted records, texts, each with what has been read from it so far), the statements the workspace holds, and the new
text that just arrived. Decide what the new text is and what to do next. Reply with one JSON object:
{"is": "request" | "source",
 "about": "<one line: what the request is actually about, naming the specific things in the workspace it concerns>",
 "answered_by_workspace": true|false,
 "questions": ["<0-4 web search queries, each precise (names, places, years), only for what the workspace's own sources do
   not answer; empty when the inputs already answer the request, or when research would mean looking up a private person's
   own records>"],
 "title": "<a short name for the workspace if the text states its purpose, else empty>"}
A request asks the agent to find out, investigate, compare, rank, check, explain or research something. A source states facts
itself. Search is one operation among others, never the default: a request about a document in the workspace is answered from
that document first; sub-questions are about the specific things named there, not about the general subject. Never plan a
search for a private individual's birth, medical, financial or similar personal records; public procedure or the public record
of organizations is fine."""

JUDGE = """You judge one web page against a question and read it into the world's ontology. Reply with one JSON object:
{"relevant": true|false, "why": "<one short line: what it says that bears on the question, or why it does not>",
 "title": "<the page's subject, a few words>", "summary": "<one sentence>",
 "things": [{"name": "...", "kind": "...", "aliases": []}],
 "statements": [{"subject": "...", "relation": "...", "object": "..." OR "value": "...", "note": "<the sentence>"}]}
Things are specifically named people, organizations, places, products, documents, events, programs and the concepts the page
uses as classes of things; a product is tied to its concept by "is a". Values (dates, amounts, identifiers, specifications)
belong to statements. A thing the same as a KNOWN thing is given the KNOWN name exactly. Every statement carries the sentence
that states it as its note; resolve pronouns. Read what bears on the question or on the things the question names; an
irrelevant page (a directory, an unrelated topic, a login wall, an empty shell) is {"relevant": false, ...} with empty lists."""

GAPS = """You are the main agent of a research workspace. Given the request, the sub-questions already searched, and the
statements found so far, name what is still missing. Reply with one JSON object: {"questions": ["<0-3 new, more specific web
search queries that would settle what is still unknown; none if the request is answered, or nothing more can be found on the
web, or what is missing is a private person's own records>"], "unknown": ["<what remains unknown, one short line each>"]}."""

COMPOSE = """You compose the reading of a research workspace: the answer to what the person asked (or, with no request, what the
sources state), as a short table of contents. You are given the request(s), the sources, and the things the workspace holds,
each with its path and its statements. Reply with one JSON object:
{"title": "<a short title for the workspace>", "sections": [{"heading": "<a few words>", "entries": [{"path": "<the path of a
thing from the list>", "name": "<its name>", "line": "<one plain line: the decisive fact about it here, from the statements>"}]}]}
The first section answers the request directly (ranked, if ranking was asked); later sections hold what supports it; a final
section "Unresolved" names what the statements do not settle, as things whose line says what is missing. At most five sections,
at most six entries each; a thing appears once, where it matters most; every path from the list, never invented; lines carry
facts from the statements, plain words, no jargon, no markdown."""


class WorkspaceHand(Hand):
    name = 'workspace'
    every = 30.0

    def __init__(self, world, log=print, **overrides):
        super().__init__(world, log=log, **overrides)
        self.root = '/' + world.node + '/user/workspaces/'
        self.archive_root = self.home + '/archive/'
        self.model = self.setting('model', DEFAULT_MODEL)
        self.pool = ThreadPoolExecutor(int(self.setting('workers', WORKERS)))   # jobs
        self.inner = ThreadPoolExecutor(12)                                      # sub-questions of a request
        self.io = ThreadPoolExecutor(24)                                         # model calls over hits and chunks
        self.lock = threading.Lock()
        self.busy = {}              # ws -> jobs running
        self.dirty = set()          # workspaces whose reading is stale
        self.known = {}             # ws -> set of standings already digested
        self.index = {}             # same_name -> (path, kind, name): what the namespace holds, by name
        self.indexed = 0            # when the index was last read whole
        self.found = {}             # ws -> [statement] landed this session, for the reading
        self.settle_interrupted()
        self.load_index()

    # ---- the stream
    def settle_interrupted(self):
        """Tasks left working by a hand that died are marked so; nothing is taken up twice."""
        try:
            for ws in (self.w.read(self.root.rstrip('/'), 'y', limit=200).get('children') or []):
                for t in (self.w.read(ws['path'] + '/asks', 'y', limit=500).get('children') or []):
                    props = t.get('properties') or {}
                    if props.get('/state') == 'working' and props.get('/who') == self.name:
                        self.write([{'path': t['path'], 'slots': {'state': 'done', 'found': 'interrupted'}, 'action': 'poke'}])
        except Exception as e:
            self.log(f'{self.name}: settle: {e}')

    def line(self, item):
        who = item.get('who') or ''
        if who == self.name:
            return 0
        did = 0
        for t in item.get('touched') or []:
            p = '/' + str(t).lstrip('/')
            if not p.startswith(self.root):
                continue
            rest = p[len(self.root):].split('/')
            ws = rest[0]
            if len(rest) == 3 and rest[1] == 'inputs' and who == 'person':
                self.submit(ws, self.digest, ws, p); did += 1
            elif len(rest) == 2 and rest[1] == 'world':
                for st in self.standings(ws):
                    if st not in self.known.setdefault(ws, set()) and not st.startswith(self.root) and not st.startswith('/x/'):
                        self.known[ws].add(st)
                        self.submit(ws, self.digest, ws, st); did += 1
        if did:
            self.mark_seen()
        return did

    def standings(self, ws):
        cell = self.w.read(self.root + ws + '/world', 'x')
        out = []
        for k, v in (cell.get('properties') or {}).items():
            m = re.match(r'^/h/[xyz]/[^/]+/\d+(/.*)$', str(v))
            if m and (k == '/sys/tack' or k.startswith('/standing/')):
                out.append(m.group(1))
        return out

    # ---- the main agent: a status line, work in threads, a reading when the round ends
    def status(self, ws, text, busy=None):
        slots = {'status': text}
        if busy is not None:
            slots['busy'] = busy
        try:
            self.write([{'path': self.root + ws + '/status', 'slots': slots, 'action': 'set'}])
        except Exception as e:
            self.log(f'{self.name}: status: {e}')

    def submit(self, ws, fn, *args):
        with self.lock:
            self.busy[ws] = self.busy.get(ws, 0) + 1
        if fn != self.compose:
            self.dirty.add(ws)
            self.status(ws, 'Reading new input', True)
        def run():
            try:
                fn(*args)
            except Exception as e:
                self.log(f'{self.name}: {fn.__name__}: {e}')
            finally:
                with self.lock:
                    self.busy[ws] = max(0, self.busy.get(ws, 1) - 1); left = self.busy[ws]
                if not left:
                    if ws in self.dirty:
                        self.dirty.discard(ws)
                        self.submit(ws, self.compose, ws)
                    else:
                        self.status(ws, 'Watching for inputs', False)
        self.pool.submit(run)

    def task(self, ws, title, detail, about=None):
        folder = self.root + ws + '/asks'
        with self.lock:
            page = self.w.read(folder, 'y', limit=500)
            n = 1 + max([0] + [int(m.group(1)) for c in (page.get('children') or []) for m in [re.search(r'/t(\d+)$', c['path'])] if m])
            path = folder + '/t%d' % n
            slots = {'task': title[:90], 'who': self.name, 'state': 'working', 'detail': detail[:90]}
            if about:
                slots['about'] = ref(about)
            self.write([{'path': path, 'slots': slots}])
        return path

    def done(self, path, found):
        self.write([{'path': path, 'slots': {'state': 'done', 'found': str(found)[:200]}, 'action': 'poke'}])

    def record(self, path):
        return {k.lstrip('/'): v for k, v in (self.w.read(path, 'x').get('properties') or {}).items()}

    def archive(self, key, slots):
        """The evidence itself, kept outside the domain: the text or image of a source, with its url."""
        path = self.archive_root + (segment_of(key) or 'source')
        flat = {}
        for k, v in slots.items():
            flat.update(parted(k, v))
        self.write([{'path': path, 'slots': flat, 'action': 'set'}])
        return path

    # ---- digesting an input or a standing
    def digest(self, ws, path):
        rec = self.record(path)
        name = str(rec.get('name') or path.rsplit('/', 1)[-1])
        image = whole(rec, 'image')
        if image:
            t = self.task(ws, 'Read ' + name[:60], 'Auto · document', about=path)
            reply = call_model(self.model, 'You transcribe a document image. Reply JSON {"title": "<what the document is, a few words>", '
                               '"text": "<everything it says, in reading order, as markdown; tables as tables; stamps, seals and '
                               'handwriting too, marked [handwritten]; nothing invented>"}', 'Transcribe this document.', image=image)
            text = str(reply.get('text') or '').strip()
            if not text:
                self.done(t, 'nothing legible'); return
            title = str(reply.get('title') or name)[:120]
            kept = self.archive(ws + ' ' + path.rsplit('/', 1)[-1] + ' ' + name[:40], {'name': name, 'image': image, 'text': text[:TEXT_CAP]})
            # the input keeps its identity and what was read; the bytes live in the archive
            self.write([{'path': path, 'slots': {'name': name, 'title': title, 'archive': ref(kept)}, 'action': 'set'}])
            self.done(t, f'{title}: {len(text)} characters read')
            self.read_source(ws, path, text, title, 'Read what ' + title[:40] + ' states')
            return
        if rec.get('url') and not rec.get('title'):
            t = self.task(ws, 'Read ' + str(rec['url'])[:70], 'Auto · page', about=path)
            try:
                title, text = self.fetch(str(rec['url']))
            except Exception as e:
                self.done(t, 'fetch failed: ' + str(e)[:80]); return
            kept = self.archive(ws + ' ' + path.rsplit('/', 1)[-1] + ' ' + name[:40], {'name': title[:120], 'url': str(rec['url']), 'text': text[:TEXT_CAP]})
            self.write([{'path': path, 'slots': {'title': title[:120], 'archive': ref(kept)}, 'action': 'poke'}])
            self.done(t, f'{len(text)} characters')
            self.read_source(ws, path, text, title, 'Read what ' + (title or name)[:40] + ' states')
            return
        text = whole(rec, 'text')
        if not text.strip():
            if not path.startswith(self.root):
                # a pasted record: its fields are its statements
                text = '\n'.join(f'{k}: {v}' for k, v in rec.items() if k not in RESERVED and not str(v).startswith('/h/') and str(v).strip())
                if text:
                    self.read_source(ws, path, name + '\n' + text, name, 'Read ' + name[:50])
            return
        if path.startswith(self.root) and not rec.get('url') and not image and not rec.get('summary'):
            self.wait_for_reads(ws, path)
            plan = self.observe(ws, path, text)
            if plan.get('is') == 'request':
                self.research(ws, path, text, plan)
                return
        self.read_source(ws, path, text, name, 'Read ' + name[:50])

    def wait_for_reads(self, ws, me, limit=150):
        """A request is planned after every other input of the workspace has been read (a file, a page): the plan sees them."""
        deadline = time.time() + limit
        while time.time() < deadline:
            unread = False
            for c in (self.w.read(self.root + ws + '/inputs', 'y', limit=100).get('children') or []):
                pr = c.get('properties') or {}
                if c['path'] != me and (any(k == '/image' or k.startswith('/image/') for k in pr) or (pr.get('/url') and not pr.get('/title'))):
                    unread = True
            if not unread:
                return
            time.sleep(3)

    def fetch(self, url):
        """A page as text: Firecrawl's markdown of the main content; our own fetch when there is no key."""
        if _web.firecrawl_key():
            d = _web.firecrawl('/scrape', {'url': url, 'formats': ['markdown'], 'onlyMainContent': True}, timeout=90)
            data = d.get('data') or {}
            md = str(data.get('markdown') or '')
            if md.strip():
                return str((data.get('metadata') or {}).get('title') or url)[:120], md
        markup, _ = _web.fetch_page(url)
        title, regions = _web.page_regions(markup, url)
        return title or url, '\n\n'.join((('## ' + r['heading'] + '\n') if r.get('heading') else '') + r['text'] for r in regions)

    # ---- what the namespace holds, by name: the guide for every reading
    def load_index(self):
        """Every thing under /user/<kind>, by the spelling names share; registry buckets and the web are left out."""
        index = {}
        try:
            for k in (self.w.read('/' + self.w.node + '/user', 'y', limit=200).get('children') or []):
                kind = k['path'].rsplit('/', 1)[-1]
                if kind in NOT_KINDS:
                    continue
                page = self.w.read(k['path'], 'y', limit=BIG + 1)
                kids = page.get('children') or []
                if len(kids) > BIG:
                    continue
                for c in kids:
                    n = (c.get('properties') or {}).get('/name')
                    if n:
                        index.setdefault(same_name(n), (c['path'], kind, str(n)))
        except Exception as e:
            self.log(f'{self.name}: index: {e}')
        with self.lock:
            for key, v in index.items():
                self.index.setdefault(key, v)
            self.indexed = time.time()

    def known_in(self, text):
        """The known things a source mentions: their names appear in its text. The model is told to reuse them."""
        low = ' ' + re.sub(r'[^a-z0-9 ]+', ' ', str(text).lower()) + ' '
        low = re.sub(r'\s+', ' ', low)
        with self.lock:
            items = list(self.index.items())
        out = []
        for key, (path, kind, name) in items:
            if len(key) >= 3 and (' ' + key + ' ') in low:
                out.append({'name': name, 'kind': kind})
                if len(out) >= KNOWN_CAP:
                    break
        return out

    def read_source(self, ws, source, text, title, task_title):
        t = self.task(ws, task_title, 'Auto · reading', about=source)
        chunks = [text[i:i + CHUNK] for i in range(0, min(len(text), CHUNK * 4), CHUNK)] or ['']
        known = self.known_in(text)
        def one(chunk):
            # a reply that does not parse (cut off, or refused) is tried again on each half of the chunk
            try:
                r = call_model(self.model, READ, json.dumps({'KNOWN': known, 'title': title, 'source': chunk}))
            except Exception as e:
                self.log(f'{self.name}: read: {e}'); r = {}
            if not r.get('statements') and len(chunk) > 2000:
                h = len(chunk) // 2
                a, b = one(chunk[:h]), one(chunk[h:])
                return {'summary': a.get('summary') or b.get('summary') or '', 'things': (a.get('things') or []) + (b.get('things') or []), 'statements': (a.get('statements') or []) + (b.get('statements') or [])}
            return r
        replies = list(self.io.map(one, chunks))
        things, statements, summary = [], [], ''
        for r in replies:
            things += [x for x in (r.get('things') or []) if isinstance(x, dict)]
            statements += [x for x in (r.get('statements') or []) if isinstance(x, dict)]
            summary = summary or str(r.get('summary') or '')
        if summary and source.startswith(self.root):
            self.write([{'path': source, 'slots': {'summary': summary[:300]}, 'action': 'poke'}])
        landed, stated = self.land(ws, things, statements, source)
        self.done(t, f'{landed} new things · {stated} statements')
        return stated

    def thing_path(self, name, kind):
        """Where a thing stands: the record spelling the same name in any kind, else a new one under /user/<kind>."""
        key = same_name(name)
        if not key or key in GENERIC or len(key) < 2:
            return None
        with self.lock:
            # the same name, or its plural or singular spelling (a concept named once as 'unit', once as 'units')
            had = self.index.get(key) or self.index.get(key + 's') or (self.index.get(key[:-1]) if key.endswith('s') and not key.endswith('ss') else None)
        if had:
            return had[0]
        with self.lock:
            known_kinds = {v[1] for v in self.index.values()}
        k = kind_of(kind, known_kinds)
        path = '/' + self.w.node + '/user/' + k + '/' + (segment_of(name) or segment_of(key) or 'thing')
        with self.lock:
            self.index[key] = (path, k, str(name).strip())
        return path

    def land(self, ws, things, statements, source):
        """Things once at shared names, statements beneath their subjects, each with the source; idempotent.
        A thing with no statement is not landed: a name alone means nothing."""
        kinds, alias = {}, {}
        for th in things:
            n, k = str(th.get('name') or '').strip(), str(th.get('kind') or 'things')
            if n and same_name(n) not in GENERIC:
                kinds[same_name(n)] = k
                for a in th.get('aliases') or []:
                    if isinstance(a, str) and a.strip() and same_name(a) != same_name(n):
                        alias[same_name(a)] = n
        new_things, stmts, paths = {}, [], {}
        def at(name):
            name = alias.get(same_name(name), name)
            key = same_name(name)
            if key in paths:
                return paths[key]
            p = self.thing_path(name, kinds.get(key, 'things'))
            paths[key] = p
            if p and p not in new_things and not self.w.read(p, 'x').get('exists'):
                new_things[p] = {'path': p, 'slots': {'name': str(name).strip()[:100]}}
            return p
        used, stated = set(), 0
        for st in statements:
            subj, rel = str(st.get('subject') or '').strip(), str(st.get('relation') or '').strip()
            if not subj or not rel:
                continue
            sp = at(subj)
            if not sp:
                continue
            r = segment_of(rel.lower()) or 'relates_to'
            if r in RESERVED:
                r = r + '_'
            note = str(st.get('note') or '')[:NOTE]
            obj = str(st.get('object') or '').strip()
            with self.lock:
                declared = same_name(obj) in kinds or same_name(alias.get(same_name(obj), obj)) in kinds or same_name(obj) in self.index
            if obj and declared:
                op = at(obj)
                if not op or op == sp:
                    continue
                tail, slots = op.rsplit('/', 1)[-1], {r: ref(op)}
                used.add(op)
            else:
                val = str(st.get('value') or obj or '').strip()
                if not val:
                    continue
                tail, slots = segment_of(val[:50]) or 'value', {'value': val[:120]}
            slots['note'] = note
            slots['source'] = ref(source)
            path = sp + '/' + r + '/' + tail
            existing = self.w.read(path, 'x')
            if existing.get('exists'):
                had = str((existing.get('properties') or {}).get('/source') or '')
                if had and not had.endswith(source):
                    ev = path + '/evidence/' + (segment_of(source.rsplit('/', 1)[-1]) or 'source')
                    if not self.w.read(ev, 'x').get('exists'):
                        stmts.append({'path': ev, 'slots': {'source': ref(source), 'note': note}})
                continue
            stmts.append({'path': path, 'slots': slots})
            used.add(sp)
            stated += 1
            self.found.setdefault(ws, []).append({'subject': subj, 'path': sp, 'relation': rel, 'object': obj or val, 'note': note})
        kept = [new_things[p] for p in new_things if p in used] + stmts
        for i in range(0, len(kept), 40):
            self.write(kept[i:i + 40])
        return sum(1 for p in new_things if p in used), stated

    # ---- a request: observe the workspace, plan, search with the page text in hand, judge and read, fill the gaps
    def observe(self, ws, path, text):
        inputs = []
        try:
            for c in (self.w.read(self.root + ws + '/inputs', 'y', limit=100).get('children') or []):
                pr = {k.lstrip('/'): v for k, v in (c.get('properties') or {}).items()}
                if c['path'] == path:
                    continue
                what = 'file' if (pr.get('archive') or whole(pr, 'image')) and not pr.get('url') else 'page' if pr.get('url') else 'text'
                inputs.append({'input': what, 'name': pr.get('title') or pr.get('name'), 'read': bool(pr.get('summary') or pr.get('title')),
                               'says': pr.get('summary') or str(pr.get('text') or '')[:400]})
        except Exception:
            pass
        for st in self.known.get(ws, set()):
            inputs.append({'input': 'record', 'name': st, 'read': True})
        with self.lock:
            found = self.found.get(ws, [])[-80:]
        reply = call_model(self.model, OBSERVE, json.dumps({'new_text': text[:4000], 'inputs': inputs, 'statements': found}))
        title = str(reply.get('title') or '').strip()
        wsrec = self.record(self.root + ws)
        if title and str(wsrec.get('name') or '') in ('', ws, ws.replace('_', ' ')):
            self.write([{'path': self.root + ws, 'slots': {'name': title[:60]}, 'action': 'poke'}])
        return reply

    def research(self, ws, path, text, plan):
        questions = [str(q) for q in (plan.get('questions') or []) if str(q).strip()][:SUBQUESTIONS]
        about = str(plan.get('about') or '')[:160]
        if not questions:
            t = self.task(ws, 'Answer from the workspace', 'Auto · request', about=path)
            self.done(t, (about + ' · ' if about else '') + 'no search needed: the reading answers from what the workspace holds')
            return
        asked = []
        for rnd in range(ROUNDS):
            if not questions:
                break
            list(self.inner.map(lambda q: self.search(ws, path, text, q), questions))
            asked += questions
            if rnd + 1 < ROUNDS:
                with self.lock:
                    found = self.found.get(ws, [])[-80:]
                reply = call_model(self.model, GAPS, json.dumps({'request': text[:2000], 'about': about, 'searched': asked, 'statements': found}))
                questions = [str(q) for q in (reply.get('questions') or []) if str(q).strip() and str(q) not in asked][:3]

    def search(self, ws, path, question, query):
        t = self.task(ws, 'Search · ' + query[:70], 'Auto · research', about=path)
        try:
            hits = self.hits(query)
        except Exception as e:
            self.done(t, 'no engine answered: ' + str(e)[:60]); return
        if not hits:
            self.done(t, 'nothing found'); return
        def judge(hit):
            url, title, md = hit
            try:
                r = call_model(self.model, JUDGE, json.dumps({'question': question[:1500], 'query': query, 'KNOWN': self.known_in(md), 'url': url, 'title': title, 'page': md[:CHUNK]}))
            except Exception as e:
                r = {'relevant': False, 'why': 'model failed: ' + str(e)[:40]}
            return (url, title, md, r)
        read = list(self.io.map(judge, hits))
        landed = 0
        for url, title, md, r in read:
            if not r.get('relevant') or not (r.get('statements') or []):
                continue
            page = _web.page_path(self.w.node, url)
            pt = str(r.get('title') or title or url)[:120]
            if not self.w.read(page, 'x').get('exists'):
                kept = self.archive(page[len('/' + self.w.node + '/user/web/pages/'):], {'name': pt, 'url': url, 'text': md[:TEXT_CAP]})
                self.write([{'path': page, 'slots': {'name': pt, 'url': url, 'title': pt, 'summary': str(r.get('summary') or '')[:300], 'archive': ref(kept)}}])
            slug = segment_of(pt[:50]) or 'page'
            self.write([{'path': path + '/pages/' + slug, 'slots': {'pages': ref(page), 'note': str(r.get('why') or '')[:NOTE], 'source': ref(path)}}])
            self.land(ws, r.get('things') or [], r.get('statements') or [], page)
            landed += 1
        self.done(t, f'{landed} of {len(read)} pages answered')

    def hits(self, query):
        """[(url, title, markdown)]: the engine hands the page text back with the hit."""
        if _web.firecrawl_key():
            d = _web.firecrawl('/search', {'query': query, 'limit': SEARCH_LIMIT, 'scrapeOptions': {'formats': ['markdown'], 'onlyMainContent': True}}, timeout=90)
            data = d.get('data')
            items = data if isinstance(data, list) else (data or {}).get('web') or []
            out = [(str(i.get('url') or ''), str(i.get('title') or ''), str(i.get('markdown') or i.get('description') or '')) for i in items if str(i.get('url') or '').startswith('http')]
            return [h for h in out if len(h[2]) > 200]
        found, _ = _web.search(query, limit=SEARCH_LIMIT)
        out = []
        for url, title, snippet in found:
            try:
                tt, text = self.fetch(url)
                out.append((url, tt or title, text))
            except Exception:
                continue
        return out

    # ---- the reading
    def compose(self, ws):
        self.status(ws, 'Composing the reading', True)
        base = self.root + ws
        inputs = [{k.lstrip('/'): v for k, v in (c.get('properties') or {}).items()} for c in (self.w.read(base + '/inputs', 'y', limit=100).get('children') or [])]
        requests = [whole(i, 'text')[:1500] for i in inputs if whole(i, 'text') and not i.get('url') and not whole(i, 'image') and not i.get('summary')]
        sources = [{'title': i.get('title') or i.get('name'), 'summary': i.get('summary')} for i in inputs if i.get('summary')]
        with self.lock:
            found = list(self.found.get(ws, []))
        if not found:
            self.status(ws, 'Watching for inputs', False); return
        things = {}
        for st in found[-400:]:
            things.setdefault(st['path'], {'path': st['path'], 'name': st['subject'], 'statements': []})
            things[st['path']]['statements'].append(f"{st['relation']} {st['object']}: {st['note'][:140]}")
        listed = [{'path': p, 'name': t['name'], 'statements': t['statements'][:12]} for p, t in things.items()][:120]
        reply = call_model(self.model, COMPOSE, json.dumps({'requests': requests, 'sources': sources, 'things': listed}), max_tokens=5000)
        sections = [sec for sec in (reply.get('sections') or []) if isinstance(sec, dict) and str(sec.get('heading') or '').strip()][:5]
        if not sections:
            self.status(ws, 'Watching for inputs', False); return
        old = [c['path'] for c in (self.w.read(base + '/views/reading', 'y', limit=200).get('children') or [])]
        v = 1 + max([0] + [int(m.group(1)) for p in old for m in [re.search(r'/v(\d+)$', p)] if m])
        here = base + '/views/reading/v%d' % v
        records = [{'path': here, 'slots': {'name': 'reading %d' % v, 'sections': len(sections)}}]
        seen = set()
        for i, sec in enumerate(sections, 1):
            head = str(sec['heading']).strip()[:40]; hs = segment_of(head) or ('section_%d' % i)
            entries = [e for e in (sec.get('entries') or []) if isinstance(e, dict) and str(e.get('path') or '') in things and str(e.get('path')) not in seen][:6]
            if not entries:
                continue
            records.append({'path': here + '/' + hs, 'slots': {'name': head, 'order': i}})
            for j, e in enumerate(entries, 1):
                p = str(e.get('path')); seen.add(p)
                nm = str(e.get('name') or things[p]['name']).strip()[:60]
                records.append({'path': here + '/' + hs + '/' + (segment_of(nm) or 'e%d' % j), 'slots': {'name': nm, 'order': j, 'note': str(e.get('line') or '').strip()[:200], 'about': ref(p)}})
        title = str(reply.get('title') or '').strip()
        wsrec = self.record(base)
        if title and str(wsrec.get('name') or '') in ('', ws, ws.replace('_', ' ')):
            records.append({'path': base, 'slots': {'name': title[:60]}, 'action': 'poke'})
        for i in range(0, len(records), 40):
            self.write(records[i:i + 40])
        self.status(ws, 'Watching for inputs', False)


if __name__ == '__main__':
    _hand.run(WorkspaceHand, settings=('model', 'workers'))
