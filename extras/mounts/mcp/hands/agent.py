"""The agent hand: a model that lives at a position in the world.

The model sees exactly two things per turn: the reading of its context cell (/x/agent/<name>/context) and the
person's latest message. No transcript, no tool results, no memory of its own. Its reply is a set of writes: what it
says to the person (a turn record), what it decided to write in the world, and the next lens: the context cell
rewritten as a gather over the references it wants to see next turn. The context is live, so next turn's reading is
the world as it then stands, through that lens.

Within one turn the model may ask for reads (paths it wants to look at before answering); the hand performs them
and asks again with the lookups attached. Lookups are not persisted: what the model wants to keep seeing it puts in
the next context.

    /agent/<name>/turns/<n>     {said, who}            the person's message (who: person) or the agent's reply
    /agent/<name>/context       a gather cell           tack: the latest turn; slots: references (the lens) and a note
    /agent/hands/agent          {name, model, endpoint} config; OPENROUTER_API_KEY in the environment

    python3 agent.py <base> [--node 0x11] [--name a] [--model anthropic/claude-sonnet-5.5] [--once]
"""
import importlib.util
import json
import queue
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
import re
import time
import urllib.parse
import urllib.request

_base = importlib.util.spec_from_file_location('hand_base', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hand.py'))
_hand = importlib.util.module_from_spec(_base); _base.loader.exec_module(_hand)
World, Hand = _hand.World, _hand.Hand

DEFAULT_MODEL = 'anthropic/claude-sonnet-5.5'
DEFAULT_ENDPOINT = 'https://openrouter.ai/api/v1/chat/completions'
MAX_LOOKUPS = 4

BOOTSTRAP = """You are an agent that lives at a position in a world of records. The world is a tree: records at paths
like /0x11/user/org/deals/d1, each with a few typed slots (numbers, days as YYYYMMDD, flags, text, references to other
records). A cell is a record that computes: it names a formula and an input, and reading /x/<path> gives its answer,
live. You see exactly two things each turn: the reading of your context cell (your lens on the world, as it stands
now) and the person's latest message. Nothing else. You have no memory except what you keep in the world and what
you put in your next lens.

Reply in two parts. First, what you say to the person: plain words, short, no markdown, no JSON; they are streamed to
the person as you write them. Then a line holding only --- and then exactly one JSON object, no fence, no XML, no
tool-call syntax. When you need lookups before you can answer, the words may be a few ("Looking.") or none.
{
  "reads":   ["/0x11/...", {"find": "a term", "under": "/0x11/..."}, {"pointing": "/0x11/..."}, {"tree": "/0x11/..."}],
                                            optional. Paths to look at before you answer (a record, a folder, /x/<cell>),
                                            or a search: the records under a folder whose name or any slot holds the
                                            term, each with the slot that matched. You will be asked again with those
                                            lookups attached. At most a few.
  "writes":  [{"path": "/0x11/...", "slots": {...}}, ...],   optional. Records to write, signed by you. Only facts worth
                                            keeping, references over copies, cells over copied answers. Never a status,
                                            a summary or a note about your own work. A cell: slots sys/weft (a reference
                                            to /0x11/weft/stdlib/<formula>, spelled as in a lookup's 'reference') and
                                            sys/tack (a reference to its input: {"type":"reference","path": "/0x11/...",
                                            "care": "y", "case": 0}), plus the formula's settings.
  "context": {"<slot>": "/0x11/<path>" | "/x/0x11/<cell>" | "/h/x/<case>/<len>/<path>" | "a short text", ...},
                                            required. Your next lens: what you want to see next turn, as references to
                                            records, folders, cells' answers (/x/...) or pinned readings (/h/...). Keep it
                                            compact and immediately useful. A text value is a note to yourself. Include a
                                            slot "note" saying what this lens changed from the last and why.
}
Formulas you may use in a cell (settings in brackets): count[into], sum/min/max/avg[slot,into], where[key,value,op | expr],
sort[slot,order], top[slot,count], by[key,op,slot,into], select[slots], distinct[slot], diff[other], except[other,key],
intersect[other,key], follow[slot,into + a secondary input], lookup[key,take,table], validate[key,op,value | expr],
latest/earliest[slot], each[expr,into], gather (nests secondary inputs). A secondary input is any other slot holding a
reference. Read /0x11/weft/stdlib to see the formulas' references.
The person's node is 0x11; their things live under /0x11/user; your own folder is /0x11/agent/<your name>.
Your context reading is shown with its lens first: each slot and the path it points at. To keep seeing something,
reference that path (the thing itself), never a path inside your own context.

Big documents live in a pool, not in your lens: a document record (pages, paragraphs, where) whose regions are the
paragraphs beneath it. Keep the document record in your lens at most, never the regions. When the world's records and
views cannot answer, search the pool ({"find": term, "under": the document's path}), read the regions that match,
integrate what they state as records, and answer from those; next time the records answer and the search is not needed.
A document in your lens is work to do, not something to keep. Its regions (paragraphs) are records with a text slot
and done: false. As you integrate a region's facts into the world, mark it done: write {"path": <the region's path>,
"action": "poke", "slots": {"done": true}} and it leaves your reading on the next turn. Integrate means: find the
thing the region is about (read the folder its kind lives in first) and change that record, add a reference, or add
a row to a folder that already has that shape; make a new record only for a thing the world has never seen, at the
path its kind lives at; put a source reference to the region on what you changed. Never copy sentences into slots;
a slot is a number, a day (YYYYMMDD), a flag, a reference, a name, or a short quotation when the words are the fact.
Mark a region done only when nothing in it is left to integrate; a region you only read and did not need is done too.
Before you ask the web, use what the world already holds: the record's own website, github and source slots, the
page records already under /0x11/user/web/pages (a page record exists beside its regions; read a page at y to see
both), and the sources under /0x11/user. When those cannot answer, send the question out instead of guessing: write
an ask, {"path": "<your folder>/asks/<short id>", "slots": {"asked": "<the question, precisely>", "query": "<three to
eight search words>", "site": "<the host or GitHub org the answer lives on, when the thing or its owner has one:
axiomatic.systems, github.com/axsys-org>", "scope": "<years, terms that bound the search>", "shape": "<the slots you
want back, with types: e.g. year: YYYY, revenue_usd: number, published: YYYYMMDD>", "about": "<the record the answer
belongs to>", "slot": "<the slot it would fill>"}}. The turn then waits while the web hand searches (the person
watches it search), and the rows come back to you in this same turn as THE WEB CAME BACK, each with a page and a
source reference. Write each fact where it belongs with a source reference to the row's own source, and answer; say
plainly what was not found. With a site, the web hand reads that site's pages first and searches only after.
For a collection (what a publication posted, an org's repos, a team's members), add "many": true to the ask and give
the shape of one item, plus "site": the thing's website when it has one (the web hand then maps the whole site and
reads its pages, instead of trusting a search); the items come back as many rows, and you put them beneath their
parent, one vocabulary.
A path segment starts with a letter: a name that begins with a digit gets its kind in front (orgs/org_8vc, people/p_50cent).
An ask that comes back empty is answered plainly: say what was not found and write nothing for it; there are no
placeholders, nothing pre-known. A fact that changes on its own (a count, a status, a price) is written with as_of:
the day it was true.

Every kind folder (/0x11/user/<kind>) is a record that carries the vocabulary of its members in a slots slot: one
line naming each slot, its type and, for a reference, the kind it points at ("name: text, description: text, website:
domain, github: text, hq -> places, parent -> orgs, founded: YYYY"). The kinds and their vocabularies are shown to
you every turn. Before you make a record, use its kind's names, types and value forms exactly; when a fact needs a
slot the vocabulary lacks, add the slot to the kind's slots line in the same reply (a poke on the kind folder) so the
next record uses it too. When you make a kind that does not exist, write its folder record first, with name,
description and the slots line you will follow. The same relation always has the same slot name in both directions
of the world: a thing is in its container, a person works_at an organisation, an organisation has hq, a product has
maker; never invent a second name for a relation that has one.
Link everything, duplicate nothing. Every record gets a name slot and a description slot (one line: what it is). A
slot that names another thing (a language, a licence, an organisation, a person, a publication, a protocol, a
product, a place) is a reference to that thing's record, never its name as text. Find the record first ({"find": name,
"under": "/0x11/user"}); a thing is one record, so never make a second for something that exists under another
spelling. If none exists, make it where its kind lives (/0x11/user/<kinds>/<slug>) with name and description and
nothing invented, and point the slot at it. Research it only when the person wants to know more or the answer needs
it: an ask blocks the turn while the web hand searches, and the person watches. When you add a record to a list (a
folder of siblings), read a sibling first and use the same slot names and types, the same vocabulary for any slot
that takes one of a few values, the same day and number forms; extra slots are welcome when they follow that
pattern. Grouping by children (a thing's issues, repos, members beneath it) and references between things are how
the world stays one web a person can walk, everything a hop or two from everything else. When you integrate a found
row, its source is the page region the row cites (the row's own source slot), never the ask.

Hierarchy and cross-reference are two different things, and both are references, never paths. A thing lives at
/0x11/user/<kind>/<slug> and never moves. What it is inside of is one slot, in: a city is in its county, a county in
its state, a repository in the organisation that owns it, an article in its issue and the issue in its journal, a
commit in its repository, a team in its company. Introducing a container later costs one record and one poke per
member (poke their in); the tree reshapes itself, since the tree is computed from in, never from paths. Every other
relation (works_at, maker, develops, hq, distinct_from) is a cross-reference in its own slot, named once in the
kind's vocabulary; a cross-reference never stands in for in, and in never stands in for a cross-reference. A thing's
own parts that have no identity of their own (a page's regions, a document's paragraphs, a talk's turns) are
physical children and stay beneath it; everything with a name of its own is a thing in its kind folder with an in.
You never cull a thing, never make-and-cull to move one, never nest a thing beneath another by path. The only
move is a wrong kind (a company filed under people): make it in the right kind, poke the old path to {"moved_to":
<reference>}, and point what referenced it at the new one ({"pointing": path} in reads shows them). The world's shape
and the tree around the record you are at are shown to you every turn; use them to place things so that every kind
has few roots and every thing is in something, unless it truly is a root (a country, a company with no parent).
A record that is the same thing as one in another world links to it with a same slot; identity across worlds rests
on strong keys (a website domain, a handle, an email, a registry id), so write those slots when you know them.
A person's other names (a git author name, a handle, an email) go in an aliases slot, comma-separated, so the index
links their commits and posts to them.
Every text you or the person write is scanned against the names in the world, and the things it names are written
beside it as mentions, so a record's "pointing here" grows from what is said about it; you still write references in
slots yourself, since a mention is weaker than a slot that says what the relation is.
Your aim across turns is a smaller reading and a richer world. Work in portions: at most about thirty writes in
one reply, then say what is next; the following turn continues from a smaller reading.
"""


def reference(path, care='x', case=0):
    return {'type': 'reference', 'path': path, 'care': care, 'case': case}


def render(node, depth=0, out=None, limit=4000):
    """A read answer as the tree the model reads: path tail, slots on one line, children indented."""
    out = [] if out is None else out
    if len(out) > limit:
        return out
    props = node.get('properties') or {}
    slots = ', '.join(f'{k.lstrip("/")}: {str(v) if k == "/text" else str(v)[:160]}' for k, v in sorted(props.items()) if not k.startswith('/sys'))
    name = node['path'].rsplit('/', 1)[-1] if depth else node['path']
    if node.get('exists') is False and not node.get('children'):
        out.append('  ' * depth + f'{name}  (absent)')
    else:
        out.append('  ' * depth + f'{name}' + (f'  {slots}' if slots else ''))
    for ch in node.get('children') or []:
        render(ch, depth + 1, out, limit)
    return out


# ---- live: what each chat's agent is doing right now, pushed to the page over server-sent events
LIVE = {}                       # chat -> {'said': partial text, 'phase': what it is doing}
SUBS = {}                       # chat -> [queue]
LIVE_LOCK = threading.Lock()


def publish(chat, **state):
    with LIVE_LOCK:
        cur = LIVE.setdefault(chat, {})
        cur.update(state)
        data = json.dumps(cur)
        for q in SUBS.get(chat, []):
            q.put(data)


class LiveHandler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        m = re.match(r'^/stop/([a-z0-9_]+)$', self.path)
        if not m:
            self.send_response(404); self.end_headers(); return
        STOPS.add(m.group(1))
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*'); self.send_header('Content-Length', '2'); self.end_headers()
        self.wfile.write(b'ok')

    def do_GET(self):
        m = re.match(r'^/stream/([a-z0-9_]+)$', self.path)
        if not m:
            self.send_response(404); self.end_headers(); return
        chat = m.group(1)
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream'); self.send_header('Cache-Control', 'no-cache')
        self.send_header('Access-Control-Allow-Origin', '*'); self.end_headers()
        q = queue.Queue()
        with LIVE_LOCK:
            SUBS.setdefault(chat, []).append(q)
            first = json.dumps(LIVE.get(chat, {}))
        try:
            self.wfile.write(f'data: {first}\n\n'.encode()); self.wfile.flush()
            while True:
                try:
                    data = q.get(timeout=15)
                    self.wfile.write(f'data: {data}\n\n'.encode())
                except queue.Empty:
                    self.wfile.write(b': keepalive\n\n')
                self.wfile.flush()
        except Exception:
            pass
        finally:
            with LIVE_LOCK:
                if q in SUBS.get(chat, []):
                    SUBS[chat].remove(q)


def serve_live(port):
    server = ThreadingHTTPServer(('127.0.0.1', port), LiveHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def partial_said(text):
    """The said value of a JSON reply still being written: from its opening quote to the last whole character."""
    m = re.search(r'"said"\s*:\s*"', text)
    if not m:
        return None
    out, i, raw = [], m.end(), text[m.end():]
    j = 0
    while j < len(raw):
        c = raw[j]
        if c == '\\':
            if j + 1 >= len(raw):
                break
            j += 2; continue
        if c == '"':
            raw = raw[:j]; break
        j += 1
    try:
        return json.loads('"' + raw.rstrip('\\') + '"')
    except Exception:
        return raw


def call_model_stream(endpoint, model, messages, on_text, timeout=180, should_stop=None):
    """call_model with stream: on_text(text so far) as tokens arrive; returns the whole reply."""
    key = os.environ.get('OPENROUTER_API_KEY') or os.environ.get('OPENAI_API_KEY')
    headers = {'Content-Type': 'application/json', 'HTTP-Referer': 'https://shrine.local', 'X-Title': 'shrine agent hand'}
    if key:
        headers['Authorization'] = 'Bearer ' + key
    body = json.dumps({'model': model, 'messages': messages, 'temperature': 0.2, 'max_tokens': 12000, 'stop': ['<invoke', '<parameter'], 'stream': True}).encode()
    text = ''
    with urllib.request.urlopen(urllib.request.Request(endpoint, body, headers), timeout=timeout) as r:
        for raw in r:
            line = raw.decode('utf-8', 'replace').strip()
            if not line.startswith('data:'):
                continue
            data = line[5:].strip()
            if data == '[DONE]':
                break
            try:
                delta = (json.loads(data).get('choices') or [{}])[0].get('delta', {}).get('content') or ''
            except Exception:
                continue
            if delta:
                text += delta
                on_text(text)
            if should_stop and should_stop():
                raise Stopped(text)
    raw_log = os.environ.get('AGENT_RAW_LOG')
    if raw_log:
        last_user = next((m['content'] for m in reversed(messages) if m['role'] == 'user'), '')
        with open(raw_log, 'a') as f:
            f.write('\n===== ' + time.strftime('%H:%M:%S') + ' ' + model + ' (stream)\n--- asked: ' + last_user[-400:].replace('\n', ' ') + '\n--- replied:\n' + text + '\n')
    return text


def call_model(endpoint, model, messages, timeout=180):
    key = os.environ.get('OPENROUTER_API_KEY') or os.environ.get('OPENAI_API_KEY')
    headers = {'Content-Type': 'application/json', 'HTTP-Referer': 'https://shrine.local', 'X-Title': 'shrine agent hand'}
    if key:
        headers['Authorization'] = 'Bearer ' + key
    # stop sequences cut a reply the moment it drifts into a tool-call form; the caller retries with a nudge
    body = json.dumps({'model': model, 'messages': messages, 'temperature': 0.2, 'max_tokens': 12000, 'stop': ['<invoke', '<parameter'], 'response_format': {'type': 'json_object'}}).encode()
    req = urllib.request.Request(endpoint, body, headers)
    reply = json.load(urllib.request.urlopen(req, timeout=timeout))
    content = reply['choices'][0]['message']['content'] or ''
    raw = os.environ.get('AGENT_RAW_LOG')
    if raw:
        last_user = next((m['content'] for m in reversed(messages) if m['role'] == 'user'), '')
        with open(raw, 'a') as f:
            f.write('\n===== ' + time.strftime('%H:%M:%S') + ' ' + model + '\n--- asked: ' + last_user[-400:].replace('\n', ' ') + '\n--- replied:\n' + (content or '') + '\n')
    return content


def parse_json(text):
    """The reply as a dict: the last complete JSON object in the text (routes sometimes think aloud or emit a tool-call
    form first and the JSON last), else the <invoke name=..>..</invoke> or <parameter name=..> form, else nothing."""
    text = (text or '').strip()
    last = text.rfind('}')
    if last >= 0:
        for i in [m.start() for m in re.finditer(r'\{', text)][::-1]:
            try:
                obj = json.loads(text[i:last + 1])
                if isinstance(obj, dict) and ('said' in obj or 'context' in obj or 'reads' in obj or 'writes' in obj):
                    return obj
            except Exception:
                continue
    blocks = re.findall(r'<(?:invoke|parameter) name="([^"]+)">(.*?)</(?:invoke|parameter)>', text, re.S)
    if blocks:
        out = {}
        for k, v in blocks:
            v = v.strip()
            try:
                out[k] = json.loads(v)
            except Exception:
                out[k] = v
        return out
    return {}


SEP = re.compile(r'^[ \t]*-{3,}[ \t]*$', re.M)


def split_reply(text):
    """(words to the person, the JSON object) from a reply: the words before the --- line and the object after it;
    a reply that is all JSON gives its said; a reply with no JSON at all is all words."""
    text = text or ''
    m = SEP.search(text)
    if m:
        said, rest = text[:m.start()].strip(), text[m.end():]
        obj = parse_json(rest) or {}
    else:
        obj = parse_json(text) or {}
        if obj:
            i = text.find('{')
            said = (str(obj.get('said') or '') or text[:i].strip()) if i >= 0 else str(obj.get('said') or '')
        else:
            said = text.strip()
    if not said and obj.get('said'):
        said = str(obj['said'])
    return said, obj


def partial_words(text):
    """What has been said so far while a reply streams: the words before the separator, with a half-typed separator or
    a JSON object that started without one cut off."""
    text = text or ''
    m = SEP.search(text)
    if m:
        return text[:m.start()].rstrip()
    if text.lstrip().startswith('{'):
        return partial_said(text) or ''
    cut = re.search(r'\n[ \t]*-{0,2}$', text)
    return (text[:cut.start()] if cut else text).rstrip()


class Stopped(Exception):
    def __init__(self, text):
        super().__init__('stopped'); self.text = text


STOPS = set()


def unwrap_path(path):
    """A reference's path is a record's path: a reading path (/h/<care>/<case>/<len>/...) given instead is unwrapped,
    as many times as it is wrapped, and a cell's /x prefix is dropped."""
    p = str(path).strip()
    while True:
        m = re.match(r'^/h/[xyz]/\d+/\d+(/.*)$', p)
        if not m:
            break
        p = m.group(1)
    return p


def lens_value(v):
    """A context slot the model asked for: a path becomes a reference (live, or pinned when spelled /h/...); text stays."""
    if not isinstance(v, str):
        return str(v)
    s = v.strip()
    m = re.match(r'^/h/([xyz])/(\d+)/\d+(/.*)$', s)
    if m:
        return reference(m.group(3), m.group(1), int(m.group(2)))
    if s.startswith('/x/') or s.startswith('/c/x/'):
        return reference(s, 'y', 0)
    if re.match(r'^/0x[0-9a-f]+/', s):
        return reference(s, 'y', 0)
    return s


def chat_key(folder):
    """The name the live stream and the stop endpoint know a chat by: a chat under /agent by its name, a talk at a
    record by the record's path (user_orgs_axsys)."""
    m = re.match(r'^/0x[0-9a-f]+/agent/([a-z]\d*)$', folder)
    if m:
        return m.group(1)
    rel = re.sub(r'^/0x[0-9a-f]+/', '', folder)
    rel = rel[:-len('/talk')] if rel.endswith('/talk') else rel
    return re.sub(r'[^a-z0-9]+', '_', rel.lower()).strip('_')


TALK_TURN = re.compile(r'^(/0x[0-9a-f]+/(?:user|agent)(?:/.+)?/talk)/turns/t(\d+)$')   # a talk at any record or folder, the root folders too


class AgentHand(Hand):
    name = 'agent'
    every = 60.0

    def __init__(self, world, log=print, **overrides):
        super().__init__(world, log=log, **overrides)
        self.name = self.setting('name') or 'a'          # the default chat; the hand answers every chat under /agent
        self.model = self.setting('model') or DEFAULT_MODEL
        self.endpoint = self.setting('endpoint') or DEFAULT_ENDPOINT
        self.folder = '/' + world.node + '/agent/' + self.name
        self.stdlib = None
        self.last_look = {}         # weave and reform: when each last ran
        port = int(self.setting('stream_port') or 8311)
        try:
            serve_live(port)
        except OSError as e:
            self.log(f'agent: live stream not served on {port}: {e}')

    def chats(self):
        """Every folder under /agent that is a chat: a single letter and digits, as the page names them."""
        page = self.w.read('/' + self.w.node + '/agent', 'y', limit=200)
        return [c['path'] for c in page.get('children', []) if c.get('exists') and re.search(r'/agent/[a-z]\d*$', c['path'])]

    # ---- the world as it stands
    def turns(self):
        page = self.w.read(self.folder + '/turns', 'y', limit=500)
        # self.folder is the chat being answered; answer() sets it per chat
        out = []
        for ch in page.get('children', []):
            if not ch.get('exists'):
                continue
            n = ch['path'].rsplit('/', 1)[1]
            if n.startswith('t') and n[1:].isdigit():
                out.append((int(n[1:]), ch.get('properties') or {}))
        return sorted(out)

    def pending(self):
        """Every chat whose latest turn is the person's: (folder, n, props). The chats under /agent by reading them;
        the talks at records from the index, which knows every talk in the world and whose turn is latest."""
        out = []
        for folder in self.chats():
            self.folder = folder
            ts = self.turns()
            if ts and ts[-1][1].get('/who') == 'person':
                out.append((folder, ts[-1][0], ts[-1][1]))
        try:
            talks = json.load(urllib.request.urlopen('http://127.0.0.1:' + str(self.setting('links_port') or 8312) + '/talks', timeout=5))
            for t in (talks.get('talks') or []) if talks.get('ready') else []:
                if t.get('who') == 'person':
                    props = self.w.read(f"{t['folder']}/turns/t{t['n']}", 'x').get('properties') or {}
                    if props.get('/who') == 'person':
                        out.append((t['folder'], int(t['n']), props))
        except Exception:
            pass                                             # the index is not up: talks are answered from the stream
        return out

    def context_reading(self):
        rec = self.w.read(self.folder + '/context', 'x')
        if not rec.get('exists'):
            return ['(your context is empty: you have not written a lens yet)']
        lens = ["LENS (slot -> what it points at; a view's rows are records under the folder it reads):"]
        for k, v in sorted((rec.get('properties') or {}).items()):
            if k.startswith('/sys'):
                continue
            line = f'  {k.lstrip("/")} -> {v}'
            m = re.match(r'^/h/[xyz]/\d+/\d+(/x/.*)$', str(v))
            if m:
                cell = self.w.read(m.group(1)[2:], 'x').get('properties') or {}
                t = re.match(r'^/h/[xyz]/\d+/\d+(/.*)$', str(cell.get('/sys/tack') or ''))
                if t:
                    line += f'   (rows are records under {t.group(1)})'
            lens.append(line)
        tree = self.w.read('/x' + self.folder + '/context', 'z', limit=400)
        if tree.get('exists') is False:
            ctx = self.w.read('/c/x' + self.folder + '/context', 'x').get('properties') or {}
            return lens + ['(your context cannot be read: ' + json.dumps(ctx)[:300] + ')']
        return lens + ['', 'READING:'] + render(tree)

    def index(self, route):
        try:
            return json.load(urllib.request.urlopen('http://127.0.0.1:' + str(self.setting('links_port') or 8312) + route, timeout=10))
        except Exception:
            return {}

    def tree_reading(self, at, depth=3):
        """The hierarchy around a record, computed from in: what it is in, upward, and what is in it, nested."""
        t = self.index('/tree?to=' + urllib.parse.quote(at) + f'&depth={depth}')
        if not t.get('ready'):
            return ''
        lines = ['IN: ' + (' < '.join(f"{c['name']} ({c['path']})" for c in t.get('in') or []) or 'nothing (a root)')]
        def walk(nodes, d):
            for n in nodes[:40]:
                lines.append('  ' * d + f"- {n['name']} ({n['path']})")
                walk(n.get('children') or [], d + 1)
        lines.append('CONTENTS (things whose in points here, nested):')
        if t.get('contents'):
            walk(t['contents'], 1)
        else:
            lines.append('  (nothing is in it yet)')
        return '\n' + '\n'.join(lines)

    # ---- hygiene as cells: the kernel computes what is wrong with each kind; the agent reads the answers, never the folders
    HYGIENE = (('count', 'count', {}), ('without_in', 'validate', {'key': '/in', 'op': 'present', 'reason': 'in nothing'}),
               ('without_description', 'validate', {'key': '/description', 'op': 'present', 'reason': 'no description'}),
               ('by_container', 'by', {'key': '/in', 'op': 'count'}))
    SYSTEM_KINDS = ('web', 'views', 'sources', 'notes', 'talk')

    def ensure_hygiene(self):
        """Four cells per kind under /user/views/hygiene, made once; a new kind gets its four on the next tick."""
        node = '/' + self.w.node
        kinds = [c['path'].rsplit('/', 1)[1] for c in (self.w.read(node + '/user', 'y', limit=200).get('children') or []) if c['path'].rsplit('/', 1)[1] not in self.SYSTEM_KINDS]
        have = {c['path'].rsplit('/', 1)[1] for c in (self.w.read(node + '/user/views/hygiene', 'y', limit=500).get('children') or []) if c.get('exists')}
        refs = self.stdlib_refs()
        records = []
        for kind in kinds:
            for name, formula, settings in self.HYGIENE:
                cell = f'{kind}_{name}'
                if cell in have or formula not in refs:
                    continue
                records.append({'path': f'{node}/user/views/hygiene/{cell}', 'slots': dict(settings, **{'sys/weft': {'type': 'reference', 'value': refs[formula]}, 'sys/tack': reference(f'{node}/user/{kind}', 'y', 0)})})
        if records:
            self.w.tool('write', records=[{'path': node + '/user/views/hygiene', 'slots': {'name': 'hygiene', 'description': 'cells that say what is wrong with each kind: count, things in nothing, things without a description, things by container'}}] + records, who='agent')
            self.log(f'agent: {len(records)} hygiene cells made')
        return len(records)

    def hygiene_reading(self):
        """One line per kind from the cells' answers: how many, which are in nothing, which lack a description, by container."""
        node = '/' + self.w.node
        cells = [c for c in (self.w.read(node + '/user/views/hygiene', 'y', limit=500).get('children') or []) if c.get('exists')]
        by_kind = {}
        for c in cells:
            name = c['path'].rsplit('/', 1)[1]
            for suffix in ('_without_in', '_without_description', '_by_container', '_count'):
                if name.endswith(suffix):
                    by_kind.setdefault(name[:-len(suffix)], {})[suffix[1:]] = c['path']
        lines = []
        for kind, cs in sorted(by_kind.items()):
            parts = []
            try:
                if 'count' in cs:
                    x = self.w.read('/x' + cs['count'], 'x').get('properties') or {}
                    parts.append(f"{x.get('/count', '?')} things")
                for key, label in (('without_in', 'in nothing'), ('without_description', 'no description')):
                    if key in cs:
                        rows = [r['path'].rsplit('/', 1)[1] for r in (self.w.read('/x' + cs[key], 'y', limit=60).get('children') or []) if r.get('exists')]
                        if rows:
                            parts.append(f'{len(rows)} {label}: ' + ', '.join(rows[:8]) + (' …' if len(rows) > 8 else ''))
                if 'by_container' in cs:
                    groups = [(re.sub(r'^\$?_?h_[xyz]_\d+_\d+_0x[0-9a-f]+_user_', '', r['path'].rsplit('/', 1)[1]), (r.get('properties') or {}).get('/count')) for r in (self.w.read('/x' + cs['by_container'], 'y', limit=40).get('children') or []) if r.get('exists')]
                    if groups:
                        parts.append('by container: ' + ', '.join(f'{g} {n}' for g, n in groups[:8]))
            except Exception as e:
                parts.append(f'(cells not readable: {str(e)[:40]})')
            lines.append(f'  {kind}: ' + '; '.join(parts))
        return ('HYGIENE (from the cells under /0x11/user/views/hygiene; read /x/<cell> for the whole list):\n' + '\n'.join(lines)) if lines else ''

    def shape_reading(self):
        sh = self.index('/shape')
        if not sh.get('ready') or not sh.get('kinds'):
            return ''
        return 'THE WORLD\'S SHAPE (things per kind, and how many are roots, in nothing): ' + ', '.join(f"{k} {v['things']} ({v['roots']} roots)" for k, v in sorted(sh['kinds'].items()))

    def kinds_reading(self):
        """One line per kind folder under /user: its vocabulary, so every record made this turn uses the same names."""
        page = self.w.read('/' + self.w.node + '/user', 'y', limit=200)
        lines = []
        for c in page.get('children', []):
            kind = c['path'].rsplit('/', 1)[1]
            props = c.get('properties') or {}
            if kind in ('web', 'views', 'sources', 'notes', 'talk'):
                continue
            if not c.get('exists'):
                lines.append(f'  {kind}: (a folder with members but no record yet: write {{"path": "/{self.w.node}/user/{kind}", "slots": {{"name": ..., "description": ..., "slots": "..."}}}} with the vocabulary its members already use)')
            else:
                lines.append(f'  {kind}: ' + str(props.get('/slots') or '(no slots line yet: poke one onto the folder record)')[:400])
        return 'THE KINDS AND THEIR SLOTS (/0x11/user/<kind>, each a record whose slots slot is the vocabulary of its members):\n' + ('\n'.join(lines) or '  (none yet: the first kind you make gets a folder record with name, description and slots)')

    def stdlib_refs(self):
        if self.stdlib is None:
            self.stdlib = {c['path'].rsplit('/', 1)[1]: c['reference'] for c in self.w.read('/' + self.w.node + '/weft/stdlib', 'y', limit=100)['children']}
        return self.stdlib

    # ---- one turn
    def answer(self, folder, n, props):
        self.folder = folder
        self.name = folder.rsplit('/', 1)[1]          # 'a' for a chat under /agent; 'talk' for a talk at a record
        said = props.get('/said') or ''
        reading = '\n'.join(self.context_reading())
        at = folder[:-len('/talk')] if folder.endswith('/talk') else ''   # a talk lives beneath the record it is about
        here = ''
        if at:
            rec = self.w.read(at, 'y', limit=120)
            here = (f'\n\nYOU ARE AT {at}: the person is looking at this record and talking to you about it. What you add '
                    'here is a slot on it (a reference to a thing in the world, a fact, a note); a thing it names that has '
                    'no record yet gets one in its kind folder, with in pointing here when it is part of this. Another '
                    'world synced to this path sees what lands here.\nTHE RECORD, NOW:\n' + '\n'.join(render(rec)) + self.tree_reading(at))
        kinds = self.kinds_reading() + '\n' + self.shape_reading() + '\n' + self.hygiene_reading()
        user = f'YOUR NAME: {self.name}   YOUR FOLDER: {self.folder}   (your asks go under {self.folder}/asks, your views under {self.folder}/views, your lens is {self.folder}/context)\n\n{kinds}\n\nYOUR CONTEXT (the world through your lens, now):\n{reading}{here}\n\nTHE PERSON SAYS:\n{said}'
        messages = [{'role': 'system', 'content': BOOTSTRAP}, {'role': 'user', 'content': user}]
        reply, spoken, stopped, text = {}, [], False, ''
        chat = chat_key(folder)
        STOPS.discard(chat)
        stop_now = lambda: chat in STOPS
        publish(chat, said='', phase='thinking', busy=True)
        def on_text(t):
            words = partial_words(t)
            publish(chat, said='\n\n'.join(spoken + ([words] if words else [])), phase='writing' if words else 'thinking')
        def ask_model(msgs):
            try:
                return call_model_stream(self.endpoint, self.model, msgs, on_text, should_stop=stop_now)
            except Stopped:
                raise
            except Exception as e:
                self.log(f'{self.name}: stream failed ({str(e)[:80]}); asking without it')
                return call_model(self.endpoint, self.model, msgs)
        asked_json = 'Now the line --- and your JSON object: writes and context, and reads only if you still need lookups.'
        try:
            for round_ in range(MAX_LOOKUPS + 1):
                text = ask_model(messages)
                said, reply = split_reply(text)
                if not reply and not stop_now():
                    self.log(f'{self.name}: no JSON after the words; asking for it')
                    more = ask_model(messages + [{'role': 'assistant', 'content': text.strip() or '(nothing)'}, {'role': 'user', 'content': 'That had no JSON object. ' + asked_json}])
                    said2, reply = split_reply(more)
                    said = said or said2
                if said:
                    spoken.append(said)
                reads = reply.get('reads') or []
                if not reads or round_ == MAX_LOOKUPS or stop_now():
                    break
                publish(chat, said='\n\n'.join(spoken), phase='looking at ' + ', '.join((p.get('find') if isinstance(p, dict) else str(p).split('/')[-1]) or '' for p in reads[:4]))
                looked = []
                for p in reads[:6]:
                    try:
                        if isinstance(p, dict) and p.get('tree'):
                            looked.append(f'TREE AT {p["tree"]}:' + (self.tree_reading(str(p['tree']), depth=4) or ' (the index is not up)'))
                        elif isinstance(p, dict) and p.get('pointing'):
                            by = json.load(urllib.request.urlopen('http://127.0.0.1:' + str(self.setting('links_port') or 8312) + '/by?to=' + urllib.parse.quote(str(p['pointing'])), timeout=10)).get('by') or {}
                            looked.append(f'POINTING AT {p["pointing"]}:\n' + ('\n'.join(f'  {slot}: ' + ', '.join(m['path'] for m in ms[:20]) for slot, ms in sorted(by.items())) or '  nothing'))
                        elif isinstance(p, dict) and p.get('find'):
                            r = self.w.tool('read', path=p.get('under') or '/' + self.w.node + '/user', care='z', find=str(p['find']), limit=200)
                            hits = r.get('matches') or []
                            lines = [f'SEARCH {p["find"]!r} under {p.get("under")}: {len(hits)} matches']
                            for h in hits[:12]:
                                rec = self.w.read(h['path'], 'x')
                                lines.append('\n'.join(render(rec)))
                            looked.append('\n'.join(lines))
                        else:
                            r = self.w.read(p, 'y', limit=80)
                            looked.append('\n'.join(render(r)))
                    except Exception as e:
                        looked.append(f'{p}  (error: {str(e)[:120]})')
                messages.append({'role': 'assistant', 'content': text})
                messages.append({'role': 'user', 'content': 'LOOKUPS (not kept; put what you want to keep seeing in your next context):\n' + '\n\n'.join(looked) + '\n\nThere are no tools to call. Answer now: your words to the person, then --- and your JSON (writes, context).'})
            # the world: what it decided to write, signed by its name
            writes = [w for w in (reply.get('writes') or []) if isinstance(w, dict) and w.get('path')]
            refused = self.apply(writes)
            if refused:
                self.log(f'{self.name}: {len(refused)} of {len(writes)} writes refused')
                spoken.append('(refused: ' + '; '.join(f'{p} {why}' for p, why in refused[:4]) + ')')
            # a web ask blocks the turn like a tool call: the person watches the search, and the answer continues with what came back
            asks = [w['path'] for w in writes if re.fullmatch(re.escape(self.folder) + r'/asks/[a-z][a-z0-9_]*', str(w['path'])) and w.get('action', 'make') != 'cull']
            if asks and not stop_now():
                came_back = self.await_asks(asks, chat, spoken, stop_now)
                if not stop_now():
                    messages.append({'role': 'assistant', 'content': text})
                    messages.append({'role': 'user', 'content': 'THE WEB CAME BACK:\n' + came_back + '\n\nNow answer the person with what came back (say plainly what was not found), then --- and your JSON: writes that put each fact where it belongs with a source reference to the found row\'s own source, and your context.'})
                    text = ask_model(messages)
                    said, reply2 = split_reply(text)
                    if said:
                        spoken.append(said)
                    if reply2:
                        more = [w for w in (reply2.get('writes') or []) if isinstance(w, dict) and w.get('path')]
                        refused = self.apply(more)
                        writes += more
                        if refused:
                            spoken.append('(refused: ' + '; '.join(f'{p} {why}' for p, why in refused[:4]) + ')')
                        if reply2.get('context'):
                            reply['context'] = reply2['context']
        except Stopped as e:
            stopped = True
            words = partial_words(e.text)
            if words:
                spoken.append(words)
            spoken.append('(stopped)')
            writes = []
            self.log(f'{self.name}: stopped by the person')
        reply['said'] = '\n\n'.join(x for x in spoken if x)
        # the reply, and the next lens
        lens = reply.get('context') or {}
        if isinstance(lens, str):
            try:
                lens = json.loads(lens)
            except Exception:
                lens = {'note': lens}
        slots = {}
        for k, v in (lens or {}).items():
            if not k or k == 'sys':
                continue
            if isinstance(v, str) and v.strip().replace('/x', '', 1).startswith(self.folder + '/context'):
                self.log(f'{self.name}: lens slot {k} points inside my own context; dropped')
                continue
            slots[k] = lens_value(v)
        turn = self.folder + '/turns/t' + str(n + 1)
        records = [{'path': turn, 'slots': {'said': (reply.get('said') or '')[:4000], 'who': self.name}}]
        if slots:
            records.append({'path': self.folder + '/context', 'slots': dict(slots, **{'sys/weft': {'type': 'reference', 'value': self.stdlib_refs()['gather']}, 'sys/tack': reference(turn, 'x', 0)})})
        self.w.tool('write', records=records, who=self.name)
        publish(chat, said='', phase='', busy=False)
        self.log(f'{self.name}: turn {n + 1} ({len(writes)} writes, lens of {len(slots)})')
        return 1

    def await_asks(self, asks, chat, spoken, stop_now, patience=300):
        """Wait for the web hand to fill the asks this turn sent out, publishing where it is searching; then the rows."""
        t0, host = time.time(), lambda u: re.sub(r'^https?://(www\.)?', '', str(u)).split('/')[0]
        asked = {a: str((self.w.read(a, 'x').get('properties') or {}).get('/asked') or a.rsplit('/', 1)[1]) for a in asks}
        settled = {}
        while time.time() - t0 < patience and not stop_now():
            for a in asks:
                if a in settled:
                    continue
                st = {k.lstrip('/'): v for k, v in (self.w.read(a + '/status', 'x').get('properties') or {}).items()}
                rows = [c for c in (self.w.read(a + '/found', 'y', limit=100).get('children') or []) if c.get('exists')]
                if rows or st.get('state') in ('done', 'empty', 'failed'):
                    settled[a] = (st, rows)
                    continue
                where = st.get('state') or 'queued'
                if where == 'reading':
                    where = 'reading ' + host(st.get('step'))
                elif where == 'searching':
                    where = 'searching “' + str(st.get('step') or '')[:60] + '”'
                elif where == 'mapping':
                    where = 'mapping ' + host(st.get('step'))
                publish(chat, said='\n\n'.join(spoken), phase=f'searching the web for: {asked[a][:70]} · {where}', busy=True)
            if len(settled) == len(asks):
                break
            time.sleep(1)
        out = []
        for a in asks:
            st, rows = settled.get(a, ({}, []))
            if rows:
                out.append(f'ASK {a}: {asked[a]}\n' + '\n'.join('  ' + c['path'].rsplit('/', 1)[1] + '  ' + ', '.join(f'{k.lstrip("/")}: {str(v)[:160]}' for k, v in sorted((c.get('properties') or {}).items()) if not k.startswith('/sys')) for c in rows[:40]))
            elif st:
                out.append(f'ASK {a}: {asked[a]}\n  nothing found ({st.get("reason") or st.get("state")})')
            else:
                out.append(f'ASK {a}: {asked[a]}\n  still searching after {patience} s; it will land under the ask later')
        publish(chat, said='\n\n'.join(spoken), phase='writing', busy=True)
        return '\n\n'.join(out)

    def apply(self, writes):
        """The model's writes as one event; when the batch is refused, one by one, so one wrong record does not
        take the rest with it. Returns the refused ones with the kernel's reason."""
        if not writes:
            return []
        for w in writes:
            for k, v in list((w.get('slots') or {}).items()):
                if isinstance(v, dict) and v.get('type') == 'reference' and isinstance(v.get('path'), str):
                    v['path'] = unwrap_path(v['path'])
                elif isinstance(v, str) and v.startswith('/h/') and v.count('/h/') > 1:
                    w['slots'][k] = '/h/' + v.split('/h/', 2)[2]          # the innermost reading is the one meant
                elif isinstance(v, str) and re.match(r'^/0x[0-9a-f]+/[a-z]', v.strip()) and ' ' not in v.strip() and k not in ('sys/weft', 'sys/tack'):
                    w['slots'][k] = {'type': 'reference', 'path': v.strip(), 'care': 'x', 'case': 0}   # a path written as text is a reference
            action = w.get('action') or 'make'
            if action in ('make', 'poke'):
                try:
                    exists = bool(self.w.read(w['path'], 'x').get('exists'))
                except Exception:
                    continue
                if exists and not w.get('action'):
                    w['action'] = 'poke'                       # the slots given are added or changed; the rest stay
                elif not exists and action == 'poke':
                    w['action'] = 'make'                       # nothing to poke yet: the slots given make the record
        def attempt(records):
            r = self.w.tool('write', records=records, who=self.name)
            if r.get('refused'):
                raise RuntimeError(r.get('reason') or 'refused')
        try:
            attempt(writes)
            return []
        except Exception:
            pass
        refused = []
        for w in writes:
            try:
                attempt([w])
            except Exception as e:
                why = str(e)
                m = re.search(r'"reason"\s*:\s*"([^"]{1,120})"', why)
                refused.append((w['path'], m.group(1) if m else why[:80]))
        return refused

    def quiet(self, item):
        """Two hand lines wake me: a web fill under one of my asks, and the index writing the mentions of a new text."""
        touched = item.get('touched') or []
        if any(re.search(r'/asks/[^/]+/found/', t) for t in touched):
            return False
        if (item.get('who') or '') == 'links' and any(t.endswith('/mentions') or '/agent/weave/names/' in t for t in touched):
            return False
        return super().quiet(item)


    # ---- the weave: names the index could not resolve, placed when the agent is sure, left when it is not
    def weave(self, now):
        folder = '/' + self.w.node + '/agent/weave'
        names = [c for c in (self.w.read(folder + '/names', 'y', limit=200).get('children') or []) if c.get('exists')]
        if not names or now - self.last_look.get(folder, 0) < 120:
            return 0
        self.last_look[folder] = now
        lines = []
        for c in names[:30]:
            props = c.get('properties') or {}
            srcs = ', '.join(re.sub(r'^/h/[xyz]/\d+/\d+', '', str(v)) for k, v in sorted(props.items()) if k.startswith('/source_'))
            lines.append(f"  {c['path']}  name: {props.get('/name')}  seen {props.get('/count')}x  in: {srcs}")
        self.folder = folder
        ts = self.turns()
        n = ts[-1][0] if ts else 0
        prompt = ('(not the person: names that appeared in texts and match no record, queued at ' + folder + '/names:\n' + '\n'.join(lines) +
                  '\nFor each one you are sure of: if it is a thing (a person, organisation, place, product, publication, event, language, '
                  'protocol), find whether it already exists under another spelling ({"find": ...}); if it does, add the spelling to that '
                  'record\'s aliases slot; if not, make it where its kind lives with name and description, and link it the way its kind links '
                  '(a place: in -> the place that contains it, making that place too if needed; a person: org; an organisation: parent or hq; '
                  'a product: maker). Then cull its name record. A name that is not a thing (a fragment, a common word, a date) is culled '
                  'too. A name you are unsure about is left where it is for a later pass. Nothing is invented: a stub holds only what the '
                  'texts it appeared in say. Say in one line what you placed and what you left.)')
        return self.answer(folder, n, {'/said': prompt})

    # ---- the reform: one kind folder at a time, on a slow clock, so the world tightens as it grows
    KINDS_SKIP = ('web', 'views', 'sources', 'eng', 'legal', 'game', 'recipes')

    def reform(self, now):
        folder = '/' + self.w.node + '/agent/weave'
        if now - self.last_look.get('reform', 0) < 1800:
            return 0
        kinds = [c['path'] for c in (self.w.read('/' + self.w.node + '/user', 'y', limit=200).get('children') or []) if c['path'].rsplit('/', 1)[1] not in self.KINDS_SKIP]
        if not kinds:
            return 0
        i = int(self.last_look.get('reform_i', -1)) + 1
        kind = kinds[i % len(kinds)]
        self.last_look['reform'], self.last_look['reform_i'] = now, i
        self.folder = folder
        ts = self.turns()
        n = ts[-1][0] if ts else 0
        prompt = ('(not the person: a hygiene pass over ' + kind + '. Start from the HYGIENE lines for it (they come from cells; read /x/<cell> for the full list), then read the records they name and what points at them. '
                  'Then, only where you are sure: two records that are one thing become one (move the facts to the fuller record, point the '
                  'thinner one at it with moved_to); a text slot that names a thing becomes a reference to its record; a thing that is part of or owned by another gets its in when the world knows it, and a '
                  'within, part_of or parent slot that means in becomes in; a record without '
                  'description gets one line; slot names and value forms '
                  'that differ from the folder\'s siblings are brought in line with a poke. Leave what you are not sure of. Say in one line '
                  'what you changed.)')
        return self.answer(folder, n, {'/said': prompt})


    def line(self, line):
        touched = line.get('touched') or []
        done = 0
        if (line.get('who') or '') == 'links':
            return 0                                         # names and reform run on the tick, in their own time
        # a fill landing under one of my asks is the alert: a turn of my own, unprompted, to integrate it and tell the person
        for t in touched:
            m = re.match(r'^(/' + self.w.node + r'/agent/[a-z]\d*|/' + self.w.node + r'/(?:user|agent)(?:/.+)?/talk)/asks/([^/]+)/found/', t)
            if m and (line.get('who') or '') != m.group(1).rsplit('/', 1)[1]:
                folder, aid = m.group(1), m.group(2)
                self.folder = folder
                ts = self.turns()
                n = ts[-1][0] if ts else 0
                done += self.answer(folder, n, {'/said': f'(not the person: the web hand filled your ask {aid}; its rows are in your reading. Decide what is a fact, write it where it belongs with a source reference to the row, compose the view, drop the ask from your lens, and tell the person what came back.)'})
                break
        # a person's turn in a talk at a record: answered where it is, no folder under /agent involved
        if (line.get('who') or '') == 'person':
            for t in touched:
                m = TALK_TURN.match(t)
                if m:
                    props = self.w.read(t, 'x').get('properties') or {}
                    if props.get('/who') == 'person':
                        done += self.answer(m.group(1), int(m.group(2)), props)
        if not any(re.search(r'/agent/[a-z]\d*/turns', t) for t in touched):
            return done
        return done + sum(self.answer(*p) for p in self.pending())

    def tick(self, now):
        try:
            self.ensure_hygiene()
        except Exception as e:
            self.log(f'agent: hygiene cells: {str(e)[:80]}')
        done = sum(self.answer(*p) for p in self.pending())
        if done:
            return done
        return self.weave(now) or self.reform(now)


if __name__ == '__main__':
    _hand.run(AgentHand, settings=('name', 'model', 'endpoint', 'stream_port', 'links_port'))
