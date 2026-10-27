"""The workspace hand: the main agent of every workspace. It watches what a person drops into a workspace and does
the work that follows, each piece in its own thread, writing back into the same world the page is reading:

    /user/workspaces/<ws>/inputs/<n>   a text, a url or a file the person dropped (the page writes it)
    /user/workspaces/<ws>/world        the overlay cell over the standings (the page writes it)
    /user/workspaces/<ws>/status       {status, busy}: the main agent's own word on what it is doing (this hand)
    /user/workspaces/<ws>/asks/t<n>    {task, who, state, detail, found}: one record per piece of delegated work (this hand)
    /user/workspaces/<ws>/views/reading/v<n>   the composed reading, one version per round (this hand)
    (asks, status and views are the segments the kernel already treats as machinery beneath a thing: never things,
    their references never drawn as edges, so the agent's own records never pollute the world they describe)

What each drop causes, bounded by the world as it stands:
    a text or a file   place its names: the model reads the text beside the names the workspace already reaches and
                       writes each mention back as the path in brackets; the index then holds the references and the
                       overlay joins what the text names. The first text that states a purpose names the workspace.
    a url              fetch the page and land its regions beneath the input, by the page's own heading hierarchy, each
                       region's hyperlinks kept in its prose; then place the names in the first regions.
    a path             link what is already known: the record's own note names candidates (May be [path] ...); each is
                       judged against the record on what both state (street, zip, name, city), and a judgement is
                       written beneath the record as same -> other, with the sentence of evidence and the source.
    anything landed    decompose: a record's prose (a description, a note, a region's text) is read for the things it
                       states. Each thing lands once, at a shared name under the world by its kind and its name
                       (/user/places/torrance_ca, /user/products/precooler), created with its facts the first time and
                       kept after; beneath the source a record in the one shape points at it (the kind as the slot, the
                       clause that states it as the note, the source), so every text that states the same thing meets
                       at that name. A thing the workspace already knows is pointed at the same way. The records a
                       standing reaches get the same, a few at a time.
    after a round      compose the reading: what the workspace asks, read against everything it now reaches, as a
                       table of contents at <ws>/reading: a few sections, each a short heading, under each a few things
                       with a short name, one line saying why it is there, and the thing as a reference. The page
                       draws the reading as the tree; the wired world stays beneath every entry. Recomposed after
                       each round of work as the next version beneath reading/, never while one is running; nothing
                       is culled.

Nothing is stored that the kernel can read off the records; the hand writes only notes with references, judgements,
its task records and its status line. OPENROUTER_API_KEY in the environment; the model is --model or
WORKSPACE_MODEL (a fast one by default). python3 workspace.py <base> [--node 0x11] [--model ...] [--once]
"""
import concurrent.futures
import importlib.util
import json
import os
import re
import threading
import time
import urllib.request

_here = os.path.dirname(os.path.abspath(__file__))
def _load(name):
    spec = importlib.util.spec_from_file_location('hand_' + name, os.path.join(_here, name + '.py'))
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod
_hand = _load('hand')
World, Hand, segment_of = _hand.World, _hand.Hand, _hand.segment_of
_web = _load('web')

ENDPOINT = 'https://openrouter.ai/api/v1/chat/completions'
DEFAULT_MODEL = os.environ.get('WORKSPACE_MODEL') or 'google/gemini-2.5-flash'
WORKERS = 4
REGIONS_PLACED = 8          # the first regions of a fetched page get their names placed; the rest wait for a reader
REGIONS_DECOMPOSED = 4      # the first regions of a fetched page are decomposed into the things they state
REACH_BUDGET = 6            # records the workspace reaches that are decomposed per round, nearest to any standing first
ABSENT = re.compile(r'^(unknown|none|n/?a|not (specified|established|found|available|stated|known)|no (specific|known)?\s*\w*|unspecified|unclear|various|other|tbd)\b', re.I)
GENERIC = {'company', 'companies', 'contract', 'contracts', 'product', 'products', 'material', 'materials', 'application', 'applications',
           'institution', 'institutions', 'facility', 'facilities', 'technology', 'technologies', 'equipment', 'system', 'systems', 'solution',
           'solutions', 'service', 'services', 'market', 'markets', 'capability', 'capabilities', 'research', 'development', 'industry',
           'customer', 'customers', 'supplier', 'suppliers', 'partner', 'partners', 'people', 'place', 'places', 'thing', 'things', 'item', 'items'}


def generic(name, kind):
    """A word that names a kind, not a thing: 'company', 'materials', 'applications' are never things."""
    t = same_name(name)
    return (not t) or t in GENERIC or t == same_name(kind) or t + 's' == same_name(kind) or (len(t.split()) == 1 and str(name).strip()[:1].islower() and len(t) < 14)


NOT_RELATIONS = {'name', 'note', 'source', 'sources', 'sys', 'same', 'unresolved', 'unknown', 'status', 'state', 'about', 'is', 'has'}
WORLD_CACHE = 20.0          # seconds a workspace's world read is reused across jobs
THINGS = 8                  # things taken out of one record's prose, at most
CANDIDATES = 6              # candidates judged per path
BRACKET = re.compile(r'\[(/[^\]\s]+)\]')
CODELIKE = re.compile(r'^[A-Z]{0,6}\s*\d[\d\-]{4,}$|^(EPA ECHO|NAICS|SIC|CAGE|UEI|DUNS|CIK|LEI)\b', re.I)
STATES = {'alabama': 'AL', 'alaska': 'AK', 'arizona': 'AZ', 'arkansas': 'AR', 'california': 'CA', 'colorado': 'CO', 'connecticut': 'CT', 'delaware': 'DE', 'florida': 'FL', 'georgia': 'GA', 'hawaii': 'HI', 'idaho': 'ID', 'illinois': 'IL', 'indiana': 'IN', 'iowa': 'IA', 'kansas': 'KS', 'kentucky': 'KY', 'louisiana': 'LA', 'maine': 'ME', 'maryland': 'MD', 'massachusetts': 'MA', 'michigan': 'MI', 'minnesota': 'MN', 'mississippi': 'MS', 'missouri': 'MO', 'montana': 'MT', 'nebraska': 'NE', 'nevada': 'NV', 'new hampshire': 'NH', 'new jersey': 'NJ', 'new mexico': 'NM', 'new york': 'NY', 'north carolina': 'NC', 'north dakota': 'ND', 'ohio': 'OH', 'oklahoma': 'OK', 'oregon': 'OR', 'pennsylvania': 'PA', 'rhode island': 'RI', 'south carolina': 'SC', 'south dakota': 'SD', 'tennessee': 'TN', 'texas': 'TX', 'utah': 'UT', 'vermont': 'VT', 'virginia': 'VA', 'washington': 'WA', 'west virginia': 'WV', 'wisconsin': 'WI', 'wyoming': 'WY', 'district of columbia': 'DC'}


LEGAL = re.compile(r"\b(incorporated|inc|corporation|corp|company|co|llc|l\.l\.c|ltd|limited|plc|lp|llp|gmbh|s\.?p\.?a|s\.?a)\b\.?", re.I)


def same_name(name):
    """The spelling under which two names are one: lowercase, no punctuation, no legal suffix, one space."""
    t = LEGAL.sub(' ', str(name or '').lower())
    t = re.sub(r"[^a-z0-9 ]+", ' ', t)
    return re.sub(r'\s+', ' ', t).strip()


def place_name(name):
    """A place's identity is its city and state: 'Rockledge, Florida' and 'Rockledge, FL' are one name."""
    m = re.match(r'^\s*([^,]+?)\s*,\s*([A-Za-z .]+?)\s*$', name)
    if not m:
        return name
    city, st = m.group(1), m.group(2).strip()
    code = STATES.get(st.lower()) or (st.upper() if len(st) == 2 else None)
    return f'{city}, {code}' if code else name
MAYBE = re.compile(r'May be \[(/[^\]\s]+)\]')


def call_model(model, system, user, timeout=120):
    key = os.environ.get('OPENROUTER_API_KEY') or ''
    headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key}
    body = json.dumps({'model': model, 'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
                       'temperature': 0, 'max_tokens': 4000, 'response_format': {'type': 'json_object'}}).encode()
    reply = json.load(urllib.request.urlopen(urllib.request.Request(ENDPOINT, body, headers), timeout=timeout))
    text = (reply.get('choices') or [{}])[0].get('message', {}).get('content') or '{}'
    start = text.find('{')
    if start < 0:
        return {}
    obj, _ = json.JSONDecoder().raw_decode(text[start:])
    return obj if isinstance(obj, dict) else {}


PLACE = """You find the names in a text: every meaningful thing it mentions, so each can become a name in a world of records.
You are given the text and the things the reader already knows, each as a path, a name and a kind. Reply with one
JSON object: {"mentions": [{"text": "<the words as they appear in the text, exactly>", "name": "<the thing's own
name, spelled so another text about it would spell it the same: a place as 'City, ST' or 'City, Country' or the
country or region itself; a company by its name; a person by full name; a product, material, component or
technology by its common name, singular>", "kind": "<one plural word: companies, places, people, products,
materials, components, technologies, agencies, programs, vehicles, standards, events, and the like>", "path":
"<the known thing's path when this mention is one of them, else null>"}], "title": "<if the text states what the
reader is trying to do, a short title for that work, at most six words, else null>"}. Rules: proper nouns and
meaningful noun phrases, never ordinary words ("cooling" no, "environmental control unit" yes); never an identifier
alone (an award number, a code) and never an amount or a date; a path only when the mention clearly is that known
thing, by name and kind, never by resemblance; one entry per distinct thing, the first words it appears as; at most
twenty-four, the most specific first."""

JUDGE = """You judge whether two registry records are the same real-world thing. You are given the record a person stands on
and one candidate, each as the facts the registry states (name, street, city, state, zip, identifiers), and the
sentence that proposed the candidate. Two records are the same thing only when their stated identifiers agree
beyond a shared name: the same street and zip, or the same identifier, or a parent/child relation the records
themselves state. A name alone is never enough. Reply with one JSON object: {"same": true | false, "why": "<one
sentence naming the fields that agree, in the records' own words, or why not>"}."""


DECOMPOSE = """You read a record's prose for the statements it makes, each a subject, a relation and an object. You are given one
record (its path and its slots, some of them prose) and the things the reader already knows, each with its path, its
name and its kind. Reply with one JSON object: {"statements": [{"subject": {"name": "...", "kind": "...", "path": "...
or null"}, "relation": "<one lowercase plural word from the record's own vocabulary: products, applications,
facilities, suppliers, customers, parts, materials, places, people, dates, amounts, and the like>", "object":
{"name": "...", "kind": "...", "path": "... or null"}, "facts": {"<slot>": <value>}, "sentence": "<the clause of the
prose that states it, verbatim>"}]}. Rules: only what the prose states, never a summary or a guess; the subject is
the thing the clause is about, which is usually the record's own subject (a page's company, a region's topic, an
award's recipient) and is a known thing when one matches; a path is given only when the thing is one of the known
things, exactly as listed; names are spelled so another text about the same thing would spell them the same (a
place as "City, ST", a product or material by its common name, singular, a company by its name); kinds are one
plural word; facts are the values the clause states (quantities as numbers, identifiers as text, dates as
YYYYMMDD); an identifier is never a thing; an absence is never an object ("unknown", "not specified", "none" are
not things: leave the statement out); a statement is made only where the prose states it, so most records yield
few, and a page that only lists or advertises yields none; at most eight statements, the most specific first;
an empty list when the prose states nothing beyond the record's own slots."""


COMPOSE = """You compose the reading of a research workspace: the answer to what the person asked, laid out as a short table of
contents over what is now known. You are given the person's inputs (texts, in order) and the things the workspace
reaches, each with its path, its name, its kind, a few stated facts, and what the world says about it by how it is
said: "stated" (a relation a record asserts, with its source), "named_in" (texts that merely mention it: nothing
asserted), "same_as" (identities judged on stated identifiers). Only "stated" and "same_as" are evidence; a mention
is a lead. Award totals, obligations and revenue are never evidence of what a company can build. Reply with one JSON object:
{"title": "<the workspace's title, at most six words, or null to keep it>", "sections": [{"heading": "<one to three
words>", "entries": [{"path": "<a path from the list>", "name": "<the thing in one to four words>", "line": "<at most
fourteen words: the decisive stated fact, with its number or identifier when there is one>"}]}]}. Rules: at most six
sections, at most six entries each; every path from the list, never invented; the first section answers the
question directly, ranked best first, holding only things with direct evidence for the very thing asked (an award
or a product statement for that equipment, a plant judged theirs); related equipment that is not the thing asked
(a cooling cart is not an environmental control unit) goes under a section named "Related", each line saying how it
differs; then the sources the answer rests on; then "Unresolved": what is named but not judged, or asked but not
found, each line saying what would settle it; a thing appears once in the whole reading, where it matters most; a
line never restates the thing's name or kind; plain words, no jargon, no markdown."""


def machinery(path):
    """A workspace's own reading, tasks and status are never things: they are about things."""
    return bool(re.search(r'/user/workspaces/[^/]+/(views|asks|status)(/|$)', path))


class WorkspaceHand(Hand):
    name = 'workspace'
    every = 30.0

    def __init__(self, world, log=print, **overrides):
        super().__init__(world, log, **overrides)
        self.model = self.setting('model') or DEFAULT_MODEL
        self.pool = concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS)
        self.lock = threading.Lock()
        self.known = {}             # ws -> set of standing paths already linked
        self.busy = {}              # ws -> count of jobs in flight
        self.dirty = set()          # workspaces whose reading is stale
        self.worlds = {}            # ws -> (time, nodes): the world read, reused for a while across jobs
        self.facts = {}             # path -> the record's few stated facts, read once
        self.read_once = {}         # ws -> records already read for their statements
        self.root = '/' + world.node + '/user/workspaces/'
        self.settle_interrupted()

    # ---- a task left working by an earlier run of the hand is over: say so, so the page stops waiting on it
    def settle_interrupted(self):
        try:
            for ws in (self.w.read(self.root.rstrip('/'), 'y', limit=200).get('children') or []):
                for t in (self.w.read(ws['path'] + '/asks', 'y', limit=200).get('children') or []):
                    props = t.get('properties') or {}
                    if props.get('/state') == 'working' and props.get('/who') == self.name:
                        self.write([{'path': t['path'], 'slots': {'state': 'done', 'found': 'interrupted; taken up again if still needed'}, 'action': 'poke'}])
        except Exception as e:
            self.log(f'{self.name}: settle: {e}')

    def world(self, ws):
        """The workspace's world, read once and reused for a while: every job in a round reads the same picture."""
        with self.lock:
            had = self.worlds.get(ws)
            if had and time.time() - had[0] < WORLD_CACHE:
                return had[1]
        nodes = self.w.read('/x' + self.root + ws + '/world', 'z', limit=500)
        with self.lock:
            self.worlds[ws] = (time.time(), nodes)
        return nodes

    # ---- the world's lines: what a person dropped, and what now stands
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
                self.submit(ws, self.digest_input, ws, p); did += 1
            elif len(rest) == 2 and rest[1] == 'world':
                with self.lock:
                    self.worlds.pop(ws, None)
                for st in self.standings(ws):
                    if st not in self.known.setdefault(ws, set()) and not st.startswith(self.root):
                        self.known[ws].add(st)
                        # a page landed by the web scheme, not yet fetched, is fetched; any other standing is linked
                        rec = {k.lstrip('/'): v for k, v in (self.w.read(st, 'x').get('properties') or {}).items()}
                        if rec.get('url') and not rec.get('fetched') and not rec.get('text'):
                            self.submit(ws, self.digest_input, ws, st); did += 1
                        else:
                            self.submit(ws, self.link_path, ws, st); did += 1
        if did:
            self.mark_seen()        # at once, so a restart does not take the same lines up again
        return did

    def standings(self, ws):
        cell = self.w.read(self.root + ws + '/world', 'x')
        out = []
        for k, v in (cell.get('properties') or {}).items():
            m = re.match(r'^/h/[xyz]/[^/]+/\d+(/.*)$', str(v))
            if m and (k == '/sys/tack' or k.startswith('/standing/')):
                out.append(m.group(1))
        return out

    # ---- the main agent: a status line, and work delegated to threads
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
        self.status(ws, 'Reading new input', True)
        if fn is not self.compose:
            self.dirty.add(ws)
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
            slots = {'task': title, 'who': self.name, 'state': 'working', 'detail': detail}
            if about:
                slots['about'] = {'type': 'reference', 'value': '/h/x/0/%d%s' % (len(about.split('/')) - 1, about)}
            self.write([{'path': path, 'slots': slots}])
        return path

    def done(self, path, found):
        self.write([{'path': path, 'slots': {'state': 'done', 'found': found}, 'action': 'poke'}])

    # ---- what the workspace reaches: names with a few facts, for the model to place
    def reach(self, ws):
        nodes = self.world(ws)
        things = {}
        def visit(n):
            props = {k.lstrip('/'): v for k, v in (n.get('properties') or {}).items()}
            m = re.match(r'^/h/[xyz]/[^/]+/\d+(/.*)$', str(props.get('at') or ''))
            # the workspace's own records (its inputs, its tasks, its reading) are not things to name in a text
            if m and props.get('name') and not m.group(1).startswith('/x/') and not m.group(1).startswith(self.root):
                things.setdefault(m.group(1), props['name'])
            for c in n.get('children') or []:
                visit(c)
        visit(nodes)
        out = []
        for p, name in list(things.items())[:60]:
            if p not in self.facts:
                try:
                    rec = {k.lstrip('/'): v for k, v in (self.w.read(p, 'x').get('properties') or {}).items()}
                except Exception:
                    rec = {}
                self.facts[p] = {k: str(rec[k])[:60] for k in ('city', 'state', 'zip', 'street', 'uei', 'applicant', 'inventors', 'url', 'agency', 'amount', 'obligated') if rec.get(k)}
            out.append({'path': p, 'name': str(name)[:80], 'kind': (p.split('/')[-2] if p.count('/') > 2 else ''), 'facts': self.facts[p]})
        return out

    def place(self, ws, path, text, title_wanted):
        """The names in a text, every meaningful one, each placed: a known thing when the mention clearly is one, a
        record spelling the same name, else a minimal record at its shared name under the world, with the text as
        its source. The text is written back with each mention followed by its path in brackets: the index then holds
        the references, the overlay follows them, and the thing's page says what names it."""
        known = self.reach(ws)
        by_name = {}
        for k in known:
            by_name.setdefault(same_name(k['name']), k['path'])
        reply = call_model(self.model, PLACE, json.dumps({'text': text, 'things': [{'path': k['path'], 'name': k['name'], 'kind': k.get('kind') or ''} for k in known[:80]]}))
        mentions = [m for m in (reply.get('mentions') or []) if isinstance(m, dict) and str(m.get('text') or '').strip() and str(m.get('name') or '').strip()][:24]
        ref = lambda p: {'type': 'reference', 'value': '/h/x/0/%d%s' % (len(p.split('/')) - 1, p)}
        records, placed, done, out = [], 0, set(), text
        for m in mentions:
            words = str(m['text']).strip()
            name = str(m['name']).strip()[:60]
            kind = segment_of(str(m.get('kind') or 'things').strip().lower()) or 'things'
            if CODELIKE.match(name) or ABSENT.match(name) or generic(name, kind) or kind in ('identifiers', 'codes', 'ids', 'amounts', 'dates'):
                continue
            if kind == 'places':
                name = place_name(name)
            target = m.get('path') if isinstance(m.get('path'), str) and m['path'].startswith('/') and m['path'] != path and not machinery(m['path']) else None
            target = target or by_name.get(same_name(name)) or self.shared_names(kind).get(same_name(name))
            if not target:
                target = '/' + self.w.node + '/user/' + kind + '/' + (segment_of(name) or 'thing')
                if target not in done and not self.w.read(target, 'x').get('exists'):
                    records.append({'path': target, 'slots': {'name': name, 'source': ref(path)}})
            done.add(target)
            if '[' + target + ']' in out:
                continue
            # the bracket goes after the first occurrence of the words, once
            i = out.find(words)
            if i < 0:
                continue
            j = i + len(words)
            if out[j:j + 2] == ' [':
                continue
            out = out[:j] + ' [' + target + ']' + out[j:]
            placed += 1
        if records:
            self.write(records)
        if placed and out != text:
            self.write([{'path': path, 'slots': {'text': out}, 'action': 'poke'}])
        title = reply.get('title')
        if title_wanted and isinstance(title, str) and 2 < len(title) < 60:
            self.write([{'path': self.root + ws, 'slots': {'name': title.strip()}, 'action': 'poke'}])
            return placed, title.strip()
        return placed, None

    def decompose(self, ws, path, known=None):
        rec = {k.lstrip('/'): v for k, v in (self.w.read(path, 'x').get('properties') or {}).items()}
        prose = ' '.join(str(rec[k]) for k in ('description', 'text', 'note', 'said', 'quote') if rec.get(k))
        prose = re.sub(r'(May be|Could supply) \[[^\]]*\]( \([^)]*\))?\.?', ' ', prose)      # candidate sentences name, they do not state
        if len(prose.strip()) < 40:
            return 0
        known = known if known is not None else self.reach(ws)
        by_name = {}
        for k in known:
            by_name.setdefault(same_name(k['name']), k['path'])
        shown = {k: str(v)[:600] for k, v in rec.items() if not k.startswith('sys')}
        reply = call_model(self.model, DECOMPOSE, json.dumps({'record': {'path': path, 'slots': shown}, 'known': [{'path': k['path'], 'name': k['name'], 'kind': k.get('kind') or k['path'].split('/')[-2]} for k in known[:80]]}))
        statements = [t for t in (reply.get('statements') or []) if isinstance(t, dict) and isinstance(t.get('subject'), dict) and isinstance(t.get('object'), dict)][:THINGS]
        ref = lambda p: {'type': 'reference', 'value': '/h/x/0/%d%s' % (len(p.split('/')) - 1, p)}
        records, made, seen, landed = [], 0, set(), set()
        def place_thing(t):
            """Where a named thing is: a known record, a record spelling the same name, or its shared name under the
            world, created with its facts the first time."""
            name = str(t.get('name') or '').strip()[:60]
            kind = segment_of(str(t.get('kind') or 'things').strip().lower()) or 'things'
            if not name or CODELIKE.match(name) or ABSENT.match(name) or generic(name, kind) or kind in ('identifiers', 'codes', 'ids'):
                return None, None
            if kind == 'places':
                name = place_name(name)
            if isinstance(t.get('path'), str) and t['path'].startswith('/') and t['path'] != path and not machinery(t['path']):
                return t['path'], name
            found = by_name.get(same_name(name)) or self.shared_names(kind).get(same_name(name))
            if found:
                return found, name
            shared = '/' + self.w.node + '/user/' + kind + '/' + (segment_of(name) or 'thing')
            if shared not in landed and not self.w.read(shared, 'x').get('exists'):
                records.append({'path': shared, 'slots': {'name': name, 'source': ref(path)}})
            landed.add(shared)
            return shared, name
        for t in statements:
            relation = segment_of(str(t.get('relation') or '').strip().lower())
            if not relation or relation in NOT_RELATIONS:
                continue
            subject, _ = place_thing(t['subject'])
            obj, obj_name = place_thing(t['object'])
            if not obj:
                continue
            subject = subject or path                      # a statement with no subject of its own is about the record
            slug = segment_of(obj_name)
            if (subject, relation, slug) in seen:
                continue
            seen.add((subject, relation, slug))
            there = self.w.read(subject + '/' + relation + '/' + slug, 'x')
            if there.get('exists'):
                # one relationship, another observation: the new source lands as evidence beneath the statement,
                # the first attribution untouched
                had = str((there.get('properties') or {}).get('/source') or '')
                if path not in had:
                    records.append({'path': subject + '/' + relation + '/' + slug + '/evidence/' + segment_of(path.split('/')[-1]), 'slots': {'source': ref(path), 'note': str(t.get('sentence') or '').strip()[:400]}})
                    made += 1
                continue
            # the one shape, beneath the subject: the relation as the slot that pins the object, the clause, the source
            slots = {relation: ref(obj), 'source': ref(path)}
            sentence = str(t.get('sentence') or '').strip()[:400]
            if sentence:
                slots['note'] = sentence
            for k, v in (t.get('facts') or {}).items() if isinstance(t.get('facts'), dict) else []:
                key = segment_of(str(k).lower())
                if key and key not in ('name', 'note', 'source', 'sys', relation) and isinstance(v, (str, int, float)) and str(v).strip():
                    slots[key] = v if isinstance(v, (int, float)) and not isinstance(v, bool) else str(v)[:200]
            records.append({'path': subject + '/' + relation + '/' + slug, 'slots': slots})
            made += 1
        if records:
            self.write(records)
        return made

    def shared_names(self, kind):
        """What already stands under /user/<kind>, by the spelling names share; read once a minute."""
        with self.lock:
            had = getattr(self, '_shared', {}).get(kind)
            if had and time.time() - had[0] < 60:
                return had[1]
        names = {}
        try:
            for c in (self.w.read('/' + self.w.node + '/user/' + kind, 'y', limit=500).get('children') or []):
                n = (c.get('properties') or {}).get('/name')
                if n:
                    names.setdefault(same_name(n), c['path'])
        except Exception:
            pass
        with self.lock:
            self._shared = getattr(self, '_shared', {}); self._shared[kind] = (time.time(), names)
        return names

    def decompose_many(self, ws, paths, title):
        t = self.task(ws, title, f'Auto · {len(paths)} record{"" if len(paths) == 1 else "s"} to read', about=paths[0] if len(paths) == 1 else None)
        known = self.reach(ws)
        made = 0
        for p in paths:
            try:
                made += self.decompose(ws, p, known)
            except Exception as e:
                self.log(f'{self.name}: decompose {p}: {e}')
        self.done(t, f'{made} statement{"" if made == 1 else "s"} out of {len(paths)} record{"" if len(paths) == 1 else "s"}')

    def reached(self, ws):
        """The records the workspace reaches, nearest to any standing first (the page's own order), that hold prose and
        have not been read yet; a bounded set per round, no standing privileged."""
        nodes = self.world(ws)
        found = []
        standings = set(self.standings(ws))
        def visit(n, depth):
            props = {k.lstrip('/'): v for k, v in (n.get('properties') or {}).items()}
            m = re.match(r'^/h/[xyz]/[^/]+/\d+(/.*)$', str(props.get('at') or ''))
            if m and not m.group(1).startswith('/x/') and not machinery(m.group(1)):
                found.append((depth, m.group(1)))
            for c in n.get('children') or []:
                visit(c, depth + 1)
        visit(nodes, 0)
        read = self.read_once.setdefault(ws, set())
        out, seen = [], set()
        for depth, p in sorted(found, key=lambda x: x[0]):
            if p in seen or p in read:
                continue
            seen.add(p)
            rec = {k.lstrip('/'): v for k, v in (self.w.read(p, 'x').get('properties') or {}).items()}
            if any(len(str(rec.get(k) or '')) >= 40 for k in ('description', 'text', 'note')):
                out.append(p); read.add(p)
            if len(out) >= REACH_BUDGET:
                break
        return out

    # ---- the reading: the agent's own table of contents for the workspace, recomposed after each round
    def edges(self, nodes):
        """Every node of the world keyed by its path beneath the cell."""
        out = []
        base = nodes.get('path', '')
        def visit(n):
            out.append((n.get('path', '')[len(base):], {k.lstrip('/'): v for k, v in (n.get('properties') or {}).items()}))
            for c in n.get('children') or []:
                visit(c)
        visit(nodes)
        return out

    def compose(self, ws):
        self.status(ws, 'Composing the reading', True)
        base = self.root + ws
        inputs = [{k.lstrip('/'): v for k, v in (c.get('properties') or {}).items()} for c in (self.w.read(base + '/inputs', 'y', limit=100).get('children') or [])]
        texts = [str(i.get('text'))[:1500] for i in inputs if i.get('text') and not i.get('url')]
        with self.lock:
            self.worlds.pop(ws, None)          # the reading wants the world as it stands after the round
        nodes = self.world(ws)
        things = {}
        def visit(n):
            props = {k.lstrip('/'): v for k, v in (n.get('properties') or {}).items()}
            m = re.match(r'^/h/[xyz]/[^/]+/\d+(/.*)$', str(props.get('at') or ''))
            if m and props.get('name') and not m.group(1).startswith('/x/') and not machinery(m.group(1)):
                t = things.setdefault(m.group(1), {'path': m.group(1), 'name': str(props['name'])[:80], 'facts': {}, 'sentence': ''})
                for k, v in props.items():
                    if k.startswith('note/') and k[5:] in ('text', 'note', 'description') and not t['sentence']:
                        t['sentence'] = str(v)[:240]
                    elif k.startswith('note/') and k[5:] in ('city', 'state', 'zip', 'amount', 'obligated', 'agency', 'applicant', 'granted', 'heading'):
                        t['facts'][k[5:]] = str(v)[:60]
            for c in n.get('children') or []:
                visit(c)
        visit(nodes)
        # what the world says about each thing, by how it says it: a stated relation (a record beneath, with its source),
        # a mention in prose (named in a text, nothing asserted), an identity (judged the same)
        def visit2(n, rel=''):
            props = {k.lstrip('/'): v for k, v in (n.get('properties') or {}).items()}
            m = re.match(r'^/h/[xyz]/[^/]+/\d+(/.*)$', str(props.get('at') or ''))
            here = n.get('path', '')
            if m and m.group(1) in things:
                parent = re.search(r'/(\d+)/([^/]+(?:/[^/]+)*?)/(out|in|part|up)/\d+/([^/]+)/\d+/', here + '/')
            for c in n.get('children') or []:
                visit2(c)
        for t in things.values():
            segs = t['path'].split('/')
            t['kind'] = segs[-2] if len(segs) > 2 else ''
            t['stated'], t['named_in'], t['same_as'] = [], [], []
        # every edge on the page: <thing>/<dir>/<n>/<label...>/<n>/<other>: a label that is a prose slot is a mention,
        # same is identity, anything else is a stated relation
        for n_path, props in self.edges(nodes):
            m = re.match(r'^(.*?)/(out|in|part|up)/(\d+)/(.+?)/(\d+)/(.+)$', n_path)
            if not m:
                continue
            thing, direction, label, other = '/' + m.group(1).split('/', 2)[-1] if m.group(1).count('/') > 1 else '', m.group(2), m.group(4), '/' + m.group(6)
            subject = things.get(thing)
            if not subject or other.startswith('/x/') or machinery(other):
                continue
            name = str(props.get('name') or other.split('/')[-1])[:60]
            if label.split('/')[-1] in ('text', 'note', 'description', 'said', 'quote'):
                subject['named_in'].append(name)
            elif label == 'same':
                subject['same_as'].append(name)
            elif direction in ('out', 'part'):
                note = str(props.get('note/note') or props.get('note/description') or '')[:120]
                subject['stated'].append(f'{label}: {name}' + (f' ({note})' if note else ''))
        for t in things.values():
            t['stated'] = t['stated'][:8]; t['named_in'] = t['named_in'][:6]; t['same_as'] = t['same_as'][:4]
        listed = list(things.values())[:150]
        if not listed:
            return
        reply = call_model(self.model, COMPOSE, json.dumps({'inputs': texts, 'things': listed}))
        sections = [sec for sec in (reply.get('sections') or []) if isinstance(sec, dict) and str(sec.get('heading') or '').strip()][:6]
        if not sections:
            return
        # a reading is never culled: each composition is the next version beneath reading/, the page draws the latest
        old = [c['path'] for c in (self.w.read(base + '/views/reading', 'y', limit=200).get('children') or [])]
        v = 1 + max([0] + [int(m.group(1)) for p in old for m in [re.search(r'/v(\d+)$', p)] if m])
        here = base + '/reading/v%d' % v
        records = [{'path': here, 'slots': {'name': 'reading %d' % v, 'sections': len(sections)}}]
        seen = set()
        for i, sec in enumerate(sections, 1):
            head = str(sec['heading']).strip()[:40]; hs = segment_of(head) or ('section_%d' % i)
            entries = [e for e in (sec.get('entries') or []) if isinstance(e, dict) and str(e.get('path') or '') in things and str(e.get('path')) not in seen][:8]
            if not entries:
                continue
            records.append({'path': here + '/' + hs, 'slots': {'name': head, 'order': i}})
            for j, e in enumerate(entries, 1):
                path = str(e.get('path') or '')
                seen.add(path)
                name = str(e.get('name') or things[path]['name']).strip()[:60]
                records.append({'path': here + '/' + hs + '/' + (segment_of(name) or 'e%d' % j), 'slots': {'name': name, 'order': j, 'note': str(e.get('line') or '').strip()[:200], 'about': {'type': 'reference', 'value': '/h/x/0/%d%s' % (len(path.split('/')) - 1, path)}}})
        title = reply.get('title')
        if isinstance(title, str) and 2 < len(title.strip()) < 60:
            records.append({'path': base, 'slots': {'name': title.strip()}, 'action': 'poke'})
        self.write(records)
        self.status(ws, f'Reading composed · {len(sections)} sections', False)

    def digest_input(self, ws, path):
        rec = {k.lstrip('/'): v for k, v in (self.w.read(path, 'x').get('properties') or {}).items()}
        wsrec = {k.lstrip('/'): v for k, v in (self.w.read(self.root + ws, 'x').get('properties') or {}).items()}
        untitled = str(wsrec.get('name') or '') in ('', ws, ws.replace('_', ' '))
        if rec.get('url'):
            t = self.task(ws, 'Fetch and digest ' + str(rec['url'])[:60], 'Auto · URL source', about=path)
            try:
                markup, _ = _web.fetch_page(str(rec['url']))
                title, regions = _web.page_regions(markup, str(rec['url']))
            except Exception as e:
                self.done(t, 'fetch failed: ' + str(e)[:80]); return
            paths = _web.region_paths(path, regions)
            records = [{'path': path, 'slots': {k: v for k, v in {'title': title, 'fetched': 'yes'}.items() if v}, 'action': 'poke'}]
            for p, r in zip(paths, regions):
                records.append({'path': p, 'slots': {'heading': r.get('heading') or '', 'text': r['text'], 'level': int(r.get('level') or 0)}})
            self.write(records)
            placed = 0
            for p, r in list(zip(paths, regions))[:REGIONS_PLACED]:
                try:
                    n, _ = self.place(ws, p, r['text'], False); placed += n
                except Exception as e:
                    self.log(f'{self.name}: place: {e}')
            self.done(t, f'{len(regions)} regions · {placed} names placed')
            self.decompose_many(ws, paths[:REGIONS_DECOMPOSED], 'Decompose the first regions of ' + (title or str(rec['url']))[:40])
            return
        text = str(rec.get('text') or '')
        if not text.strip():
            return
        t = self.task(ws, 'Place the names in ' + (str(rec.get('name') or 'the text'))[:50], 'Auto · reading the text', about=path)
        placed, title = self.place(ws, path, text, untitled)
        self.done(t, f'{placed} name{"" if placed == 1 else "s"} placed' + (f' · named the workspace "{title}"' if title else ''))
        self.decompose_many(ws, [path], 'Decompose ' + (str(rec.get('name') or 'the text'))[:40])

    def link_path(self, ws, path):
        rec = {k.lstrip('/'): v for k, v in (self.w.read(path, 'x').get('properties') or {}).items()}
        note = str(rec.get('note') or '')
        candidates = [c for c in MAYBE.findall(note)][:CANDIDATES]
        # only where the standings do not all meet is what the workspace reaches read for its statements: the agent
        # works where the perspective has a gap, a bounded set nearest to any standing
        root = {k.lstrip('/'): v for k, v in (self.world(ws).get('properties') or {}).items()}
        apart = int(root.get('components') or 0) > 1
        reach = self.reached(ws) if apart else []
        if reach:
            self.submit(ws, self.decompose_many, ws, reach, 'Read what the workspace reaches')
        if not candidates:
            return
        already = {c['path'].split('/')[-1] for c in (self.w.read(path + '/same', 'y', limit=100).get('children') or [])}
        t = self.task(ws, 'Judge ' + str(rec.get('name') or path.split('/')[-1])[:40] + ' against its candidates', f'Auto · {len(candidates)} candidate{"" if len(candidates) == 1 else "s"} named', about=path)
        shown = {k: str(rec[k])[:80] for k in rec if k not in ('note', 'kinds', 'source')}
        linked = 0
        for cand in candidates:
            slug = segment_of(cand.split('/')[-1])
            if slug in already:
                continue
            other = {k.lstrip('/'): str(v)[:80] for k, v in (self.w.read(cand, 'x').get('properties') or {}).items() if k not in ('/note', '/kinds')}
            if not other:
                continue
            sentence = next((s for s in re.split(r'(?<=\.)\s+', note) if cand in s), '')
            try:
                reply = call_model(self.model, JUDGE, json.dumps({'record': shown, 'candidate': other, 'proposed_by': sentence}))
            except Exception as e:
                self.log(f'{self.name}: judge: {e}'); continue
            if reply.get('same') is True and str(reply.get('why') or '').strip():
                self.write([{'path': path + '/same/' + slug, 'slots': {'same': {'type': 'reference', 'value': '/h/x/0/%d%s' % (len(cand.split('/')) - 1, cand)},
                                                                        'note': str(reply['why'])[:400], 'source': {'type': 'reference', 'value': '/h/x/0/%d%s' % (len(path.split('/')) - 1, path)}}}])
                linked += 1
        self.done(t, f'{linked} linked of {len(candidates)}')


if __name__ == '__main__':
    _hand.run(WorkspaceHand, settings=('model',))
