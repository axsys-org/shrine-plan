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
  "reads":   ["/0x11/...", {"find": "a term", "under": "/0x11/..."}, {"tree": "/0x11/..."},
              {"view": "<formula>", "over": "/0x11/...", "care": "y" | "z", "settings": {...}}],
                                            optional. Paths to look at before you answer (a record, a folder, /x/<cell>),
                                            or a search: the records under a folder whose name or any slot holds the
                                            term, each with the slot that matched; tree: what a record is in and what is in
                                            it; view: any formula below run
                                            by the kernel over a folder, nothing written (where, validate, by, select, sort,
                                            top, count, diff, follow ...). You will be asked again with those lookups
                                            attached. At most a few.
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
plainly what was not found. Never say what a search found, or that it found nothing, before THE WEB CAME BACK is in
front of you: until then say only that you are sending it out. With a site, the web hand reads that site's pages first and searches only after.
For a collection (what a publication posted, an org's repos, a team's members), add "many": true to the ask and give
the shape of one item, plus "site": the thing's website when it has one (the web hand then maps the whole site and
reads its pages, instead of trusting a search); the items come back as many rows, and you put them beneath their
parent, one vocabulary.
A path segment starts with a letter: a name that begins with a digit gets its kind in front (orgs/org_8vc, people/p_50cent).
An ask that comes back empty is answered plainly: say what was not found and write nothing for it; there are no
placeholders, nothing pre-known. A fact that changes on its own (a count, a status, a price) is written with as_of:
the day it was true.

One thing, one canonical record, at one path. A slash means part of: a record's children are its own parts, the
ones that would not exist without it and change with it (a document's sections, a talk's turns, a team inside a
company, a city inside its country when you file places that way). A thing that exists on its own is never filed
under another thing it merely relates to. A name never moves, because other worlds hold it; a wrong filing is fixed
by making the record at the right path and poking the old one to {"moved_to": <reference>}. Never cull a thing. Find
before you make ({"find": name, "under": "/0x11/user"}, and the names the person's words resolve to are shown to you);
never make a second record for a thing that exists, add the spelling to its aliases instead.
A relation is asserted once, on the record it belongs to, as a slot whose value is the other thing's name:
{"founder": "/0x11/user/people/forbes_mckenzie"}. The name is enough: it is read at its own place, never copied, so a
peer following this record receives the name, not the other thing. A relation with several values, or with qualifiers
(a role, a date, a source), becomes child records of the thing, one per value, each holding the name and its
qualifiers: /0x11/user/books/walkaway/authors/cory_doctorow {"author": <name>, "role": "writer"}. Slot names are
descriptive labels with no meaning to the system; reuse labels in use nearby (LABELS IN USE) so the world reads
consistently. The other direction of a relation is never written: who founded what, who points here, what a thing
contains by relation, all of it is read from these slots, and you are shown it as relations in and out.
Other worlds you can read sit at /0x11/<peer>/user (0x12, 0x13 ...); their records are theirs, never written by you.
When a thing in your world is the same as a thing in another world and the evidence says so, join them with a judgement
record beneath your record, <your record>/same/<slug>_<world> (verisk_0x13) {"same": <the other world's record>, "why": <what evidence>};
your record itself is not changed. When neither record is yours (two other worlds describe one thing), keep the
judgement in your world at /0x11/user/identities/<slug> {"subject": <one record>, "same": <the other>, "why": ...}.
The evidence a why names: a shared website, domain,
ticker or other identifier; the same relation to one thing (both name the same founder); texts or sources that agree.
Its facts then appear in your views by union, tagged with the world that asserts them, and nothing is copied. A name
alone is a candidate, not proof: two records called Apple may be a fruit and a company. When the evidence says two
records are different things despite a shared name, record the judgement the same way with a different slot in place of
same (<your record>/different/<slug>_<world>, or under identities with a subject), so nobody asks again.
You are shown candidates with their evidence; judge each, never join on similarity of wording.
Disagreement is kept, never resolved by overwriting. A slot holds the preferred value; every value asserted for it is
kept as a claim under <thing>/claims with its value, source and asserter, and the hands write those claims for you
whenever a value changes. Change a preferred value only when you judge the new one better supported, and add "why":
"<one line>" to that write; the hands keep the old value as a claim. You are shown the disagreements on the records
you read: present the preferred answer and say plainly that sources differ.
A fact's provenance is a slot too: source, holding the name of the region, row or text it came from (sources/<n>
child records when there are several). Derived things (an inverse, a grouping, a summary, a count) are cells under
/0x11/user/views, computed on read, never written as records.
Hygiene is structural, and you are shown the signals each turn: dangling references and overlays, orphans, names
written as text, numbered labels, shared literals that may mean two records are one, texts not yet decomposed. Each
is a candidate for your judgement, never an instruction.
Research only when the person wants to know more or the answer needs it: an ask blocks the turn while the web hand
searches, and the person watches. When you integrate a found row, its source is the page region the row cites (the
row's own source slot), never the ask.
Every text you or the person write is scanned against the names in the world, and the things it names are written
into its prose as paths in brackets, so a record's "pointing here" grows from what is said about it; you still write references in
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


# ---- claims: a value that disagrees with what a record holds is kept beside it, with its origin, never lost
CLAIM_SKIP = {'name', 'description', 'source', 'aliases', 'digested', 'moved_to', 'researched', 'note', 'notes', 'text', 'said'}


def _norm(v):
    return re.sub(r'\s+', ' ', str(v).strip().lower())


def claim_slug(slot, value):
    import hashlib
    return _hand.segment_of(f'{slot}_' + hashlib.sha1(_norm(value).encode()).hexdigest()[:8])


def preserve_claims(world, writes, who, may_prefer):
    """For each literal a write would change on an existing record, keep both values as claims under the record's
    claims folder, each with its value, source, asserter and day. A writer that may prefer (the person, the agent)
    changes the slot; one that may not (a hand reading a source) leaves the slot as it is and only adds its claim.
    Returns the claim records to write alongside."""
    extra, today = [], int(time.strftime('%Y%m%d'))
    for w in writes:
        path, slots = w.get('path'), w.get('slots') or {}
        if not path or w.get('action') == 'cull' or '/claims/' in path or '/talk/' in path:
            continue
        try:
            cur = world.read(path, 'x')
        except Exception:
            continue
        if not cur.get('exists'):
            continue
        props = {k.lstrip('/'): v for k, v in (cur.get('properties') or {}).items() if not k.startswith('/sys')}
        new_source = slots.get('source')
        for k, v in list(slots.items()):
            if k in CLAIM_SKIP or k not in props or isinstance(v, dict) or str(props[k]).startswith('/h/'):
                continue
            old = props[k]
            if _norm(old) == _norm(v):
                continue
            base = path + '/claims'
            old_claim = {'slot': k, 'value': old, 'by': 'recorded', 'day': today}
            if props.get('source'):
                old_claim['source'] = {'type': 'reference', 'path': re.sub(r'^/h/[xyz]/\d+/\d+', '', str(props['source'])), 'care': 'x', 'case': 0}
            new_claim = {'slot': k, 'value': v, 'by': who, 'day': today}
            if new_source:
                new_claim['source'] = new_source
            if w.get('why'):
                new_claim['why'] = str(w['why'])[:300]
            extra.append({'path': f'{base}/{claim_slug(k, old)}', 'slots': old_claim, '_if_absent': True})
            extra.append({'path': f'{base}/{claim_slug(k, v)}', 'slots': new_claim})
            if not may_prefer:
                slots.pop(k)                                  # reading a source is not permission to overwrite what is known
        w['slots'] = slots
        w.pop('why', None)
    out = []
    for e in extra:
        if e.pop('_if_absent', False):
            try:
                if world.read(e['path'], 'x').get('exists'):
                    continue
            except Exception:
                pass
        out.append(e)
    return out


def keep_sources(world, writes):
    """A record already citing one source keeps it: a new source goes beside it as <record>/sources/h<hash>, with the
    slots this source supports, so every fact still says where it came from and no writer overwrites provenance."""
    import hashlib
    extra = []
    for w in writes:
        src = (w.get('slots') or {}).get('source')
        if not src or w.get('action') == 'cull' or not w.get('path'):
            continue
        try:
            cur = world.read(w['path'], 'x')
        except Exception:
            continue
        have = (cur.get('properties') or {}).get('/source') if cur.get('exists') else None
        if not have:
            continue
        new_path = unwrap_path(src.get('path') if isinstance(src, dict) else src)
        if unwrap_path(have) == new_path:
            continue
        w['slots'].pop('source')
        supports = ' '.join(k for k in w['slots'] if k not in ('source', 'sources'))
        extra.append({'path': f"{w['path'].rstrip('/')}/sources/h{hashlib.sha1(new_path.encode()).hexdigest()[:10]}",
                      'slots': {'source': {'type': 'reference', 'path': new_path, 'care': 'x', 'case': 0}, 'supports': supports}})
    return extra


# ---- the world's own views: relations and the union from the kernel's standard woven cells, read at /o
def unref(v):
    m = re.match(r'^/h/[xyz]/[^/]+/\d+(/.*)$', str(v or ''))
    return m.group(1) if m else (v if isinstance(v, str) and v.startswith('/') else None)


def world_of_path(p):
    segs = [x for x in str(p).split('/') if x]
    return segs[segs.index('user') - 1] if 'user' in segs and segs.index('user') > 0 else (segs[0] if segs else '')


def views_of(world, at):
    """relations and union for a thing, in the shapes the agent's reading expects, or None without kernel views."""
    rn = world.view('relations', at)
    if rn is None:
        return None
    relations = []
    for rel, props in rn.items():
        m = re.match(r'^/(out|in|part)/(\d+)/(.+)$', rel)
        if not m or '/assertions/' in rel:
            continue
        other = unref(props.get('other'))
        if not other:
            continue
        via = unref(props.get('via')) or other
        note = {k[5:]: (unref(v) or v) for k, v in props.items() if k.startswith('note/')}
        relations.append({'way': 'in' if props.get('direction') == 'in' else 'out', 'label': str(props.get('label') or '').lstrip('/'),
                          'other': other, 'name': props.get('name') or other.rsplit('/', 1)[-1], 'via': via, 'note': note,
                          'world': world_of_path(via), 'about': unref(props.get('about')) or at})
    un = world.view('union', at)
    union = None
    if un:
        records = []
        for rel, props in un.items():
            m = re.match(r'^/records/(\d+)/(.+)$', rel)
            if m:
                p = '/' + m.group(2); records.append({'path': p, 'world': world_of_path(p), 'name': props.get('name') or p.rsplit('/', 1)[-1]})
        worlds = sorted({r['world'] for r in records})
        by_slot = {}
        for rel, props in un.items():
            m = re.match(r'^/facts/(\d+)/(.+?)/assertions/(\d+)/(.+)$', rel)
            if not m:
                continue
            slot, about, source = m.group(2), unref(props.get('about')), unref(props.get('source')) or ''
            w = world_of_path(about or source); claim = '/claims/' in source
            key = re.sub(r'\s+', ' ', str(props.get('value', '')).strip().lower())
            g = by_slot.setdefault(slot, {}).setdefault(key, {'value': props.get('value'), 'worlds': set(), 'tags': set()})
            g['tags'].add(w + (f" (claim by {props.get('evidence/by', '?')})" if claim else ''))
            if not claim:
                g['worlds'].add(w)
        facts = [{'kind': 'value', 'value': v['value'], 'labels': [slot], 'worlds': sorted(v['worlds']), 'all': set(worlds) <= v['worlds']}
                 for slot, vals in by_slot.items() for v in vals.values() if v['worlds']]
        rels = {}
        for r in relations:
            g = rels.setdefault(r['other'], {'kind': 'relation', 'way': r['way'], 'other': r['other'], 'name': r['name'], 'labels': set(), 'worlds': set()})
            g['labels'].add(r['label'] + (' of' if r['way'] == 'in' else '')); g['worlds'].add(r['world'])
        facts += [dict(g, labels=sorted(g['labels']), worlds=sorted(g['worlds']), all=set(worlds) <= g['worlds']) for g in rels.values()]
        disagreements = [{'slot': slot, 'values': {str(v['value']): sorted(v['tags']) for v in vals.values()}} for slot, vals in by_slot.items() if len(vals) > 1]
        union = {'at': at, 'records': records, 'worlds': worlds, 'facts': facts, 'disagreements': disagreements}
    return {'relations': relations, 'union': union}


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
        """Every chat whose latest turn is the person's: (folder, n, props), by reading the chats under /agent."""
        out = []
        for folder in self.chats():
            self.folder = folder
            ts = self.turns()
            if ts and ts[-1][1].get('/who') == 'person':
                out.append((folder, ts[-1][0], ts[-1][1]))
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

    def tree_reading(self, at):
        """Where a record sits: its relations from the world's own view, each tagged with the asserting world, the
        claims whose sources differ, and what every world says about the same thing."""
        kernel = views_of(self.w, at)
        if kernel is None:
            return ''
        lines = [f"WHERE {at} SITS:"]
        claims = [c for c in (self.w.read(at + '/claims', 'y', limit=60).get('children') or []) if c.get('exists') and '/retracted' not in (c.get('properties') or {})]
        by_slot = {}
        for c in claims:
            cp = {k.lstrip('/'): v for k, v in (c.get('properties') or {}).items()}
            by_slot.setdefault(cp.get('slot'), []).append(cp)
        for slot_, cs in by_slot.items():
            if len({_norm(c.get('value')) for c in cs}) > 1:
                lines.append(f"  sources differ on {slot_}: " + '; '.join(f"{c.get('value')} (by {c.get('by')}{', source ' + re.sub(r'^/h/[xyz]/[0-9]+/[0-9]+', '', str(c.get('source'))) if c.get('source') else ''})" for c in cs))
        rel = kernel['relations']
        if rel:
            note = lambda r: (' [' + '; '.join(f'{k}: {v}' for k, v in r['note'].items() if not str(v).startswith('/')) + ']') if r.get('note') else ''
            lines.append('  relations:')
            here = at.split('/')[1]
            tag = lambda r: f" [asserted by {r['world']}]" if r.get('world') and r['world'] != here else ''
            for r in rel[:30]:
                if r['way'] == 'out':
                    lines.append(f"    {r['label']}: {r['name']} ({r['other']}){note(r)}{tag(r)}")
                else:
                    lines.append(f"    {r['label']} of: {r['name']} ({r['other']}){note(r)}{tag(r)}")
        # the same thing in other worlds: what each world says, where they agree and where they differ
        u = kernel.get('union') or {}
        if len(u.get('worlds') or []) > 1:
            lines.append('  described by worlds ' + ', '.join(u['worlds']) + ': ' + '; '.join(f"{m['world']} at {m['path']}" for m in u['records']))
            agree = [f.get('value') or f"{f['labels'][0]} {f['name']}" for f in u['facts'] if f['all']]
            if agree:
                lines.append('    all of them say: ' + '; '.join(map(str, agree[:12])))
            for w in u['worlds']:
                only = [f"{f['labels'][0]}: {f.get('value') or f['name']}" for f in u['facts'] if f['worlds'] == [w]]
                if only:
                    lines.append(f'    only {w} says: ' + '; '.join(only[:10]))
            for d in u.get('disagreements') or []:
                lines.append(f"    worlds differ on {d['slot']}: " + '; '.join(f"{v} ({', '.join(ws)})" for v, ws in d['values'].items()))
        return '\n' + '\n'.join(lines)

    # ---- hygiene as cells: the kernel computes what is wrong with each kind; the agent reads the answers, never the folders
    HYGIENE = (('count', 'count', {}),
               ('without_description', 'validate', {'key': '/description', 'op': 'present', 'reason': 'no description'}),
               ('without_source', 'validate', {'key': '/source', 'op': 'present', 'reason': 'no source'}))
    SYSTEM_KINDS = ('web', 'views', 'sources', 'talk')      # the hands' own folders, not anyone's filing

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
            for suffix in ('_without_in', '_without_description', '_without_source', '_by_container', '_count'):
                if name.endswith(suffix):
                    by_kind.setdefault(name[:-len(suffix)], {})[suffix[1:]] = c['path']
        lines = []
        for kind, cs in sorted(by_kind.items()):
            parts = []
            try:
                if 'count' in cs:
                    x = self.w.read('/x' + cs['count'], 'x').get('properties') or {}
                    parts.append(f"{x.get('/count', '?')} things")
                for key, label in (('without_in', 'in nothing'), ('without_description', 'no description'), ('without_source', 'no source')):
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

    def stdlib_refs(self):
        if self.stdlib is None:
            self.stdlib = {c['path'].rsplit('/', 1)[1]: c['reference'] for c in self.w.read('/' + self.w.node + '/weft/stdlib', 'y', limit=100)['children']}
        return self.stdlib

    # ---- one turn
    def answer(self, folder, n, props):
        """One turn; a failure ends the live bubble and, for a person's turn, says plainly why in the conversation."""
        try:
            return self._answer(folder, n, props)
        except Exception as e:
            publish(chat_key(folder), said='', phase='', busy=False)
            why = str(e)
            if props.get('/who') == 'person':
                plain = ('the model service refused the request: the OpenRouter credit is used up (402 Payment Required)' if '402' in why
                         else 'the model service failed: ' + why[:160])
                try:
                    self.w.tool('write', records=[{'path': f'{folder}/turns/t{n + 1}', 'slots': {'said': f'({plain}. Nothing was written. Send it again once that is fixed.)', 'who': folder.rsplit('/', 1)[1]}}], who=folder.rsplit('/', 1)[1])
                except Exception:
                    pass
            self.log(f'{folder.rsplit("/", 1)[1]}: {why[:160]}')
            return 0

    def _answer(self, folder, n, props):
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
        user = f'YOUR NAME: {self.name}   YOUR FOLDER: {self.folder}   (your asks go under {self.folder}/asks, your views under {self.folder}/views, your lens is {self.folder}/context)\n\nYOUR CONTEXT (the world through your lens, now):\n{reading}{here}\n\nTHE PERSON SAYS:\n{said}'
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
            kept = []                                         # writes from every round: a reply that also looks something up still writes
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
                kept += [w for w in (reply.get('writes') or []) if isinstance(w, dict) and w.get('path')]
                reads = reply.get('reads') or []
                if not reads or round_ == MAX_LOOKUPS or stop_now():
                    break
                publish(chat, said='\n\n'.join(spoken), phase='looking at ' + ', '.join((p.get('find') if isinstance(p, dict) else str(p).split('/')[-1]) or '' for p in reads[:4]))
                looked = []
                for p in reads[:6]:
                    try:
                        if isinstance(p, dict) and p.get('view'):
                            r = self.w.tool('read', path=str(p.get('over') or '/' + self.w.node + '/user'), care=str(p.get('care') or 'y'), formula=str(p['view']), settings=p.get('settings') or {}, limit=200)
                            res = r.get('result') or r
                            rows = [c for c in (res.get('children') or []) if c.get('exists')]
                            ctx = {k: v for k, v in ((r.get('context') or {}).get('properties') or {}).items() if '/sys/view/' in k}
                            looked.append(f"VIEW {p['view']} over {p.get('over')} {json.dumps(p.get('settings') or {})}: {len(rows)} rows" + (f' (context: {ctx})' if ctx else '') + '\n' +
                                          '\n'.join(render(res))[:6000])
                        elif isinstance(p, dict) and p.get('tree'):
                            looked.append(f'TREE AT {p["tree"]}:' + (self.tree_reading(str(p['tree'])) or ' (no relations view for it)'))
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
                pending = [w['path'] for w in kept]
                messages.append({'role': 'user', 'content': 'LOOKUPS (not kept; put what you want to keep seeing in your next context):\n' + '\n\n'.join(looked) +
                                 ('\n\nYour writes so far are kept and will be applied: ' + ', '.join(pending[:12]) + '. Do not repeat them; an ask among them is searched after this reply, and its rows come back to you as THE WEB CAME BACK.' if pending else '') +
                                 '\n\nThere are no tools to call. Answer now: your words to the person, then --- and your JSON (writes, context).'})
            # the world: what it decided to write, signed by its name
            seen_paths, writes = set(), []
            for w in reversed(kept):                          # a later round's write of the same path wins
                key = (w['path'], w.get('action') or 'make')
                if key not in seen_paths:
                    seen_paths.add(key); writes.insert(0, w)
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
        gather = (self.stdlib_refs() or {}).get('gather')
        writes += preserve_claims(self.w, writes, self.name if self.name != 'talk' else 'agent', may_prefer=True)
        writes += keep_sources(self.w, writes)                # a record's first source stays; a new one sits beside it
        writes = [w for w in writes if w.get('slots') or w.get('action') == 'cull']
        for w in writes:
            if w.get('overlay'):
                real = unwrap_path(str(w.pop('overlay')))
                slots = dict(w.get('slots') or {})
                if w.get('note'):
                    slots['note'] = str(w.pop('note'))
                slots.update({'sys/weft': {'type': 'reference', 'value': gather}, 'sys/tack': {'type': 'reference', 'path': real, 'care': 'z', 'case': 0}})
                w['slots'] = slots
            w.pop('note', None)
            for k, v in list((w.get('slots') or {}).items()):
                if isinstance(v, dict) and v.get('type') == 'reference' and isinstance(v.get('path'), str):
                    v['path'] = unwrap_path(v['path'])
                elif isinstance(v, str) and v.startswith('/h/') and v.count('/h/') > 1:
                    w['slots'][k] = '/h/' + v.split('/h/', 2)[2]          # the innermost reading is the one meant
                elif isinstance(v, str) and re.match(r'^/0x[0-9a-f]+/(0x[0-9a-f]+/)?[a-z]', v.strip()) and ' ' not in v.strip() and k not in ('sys/weft', 'sys/tack'):
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
        """One hand line wakes me: a web fill under one of my asks."""
        touched = item.get('touched') or []
        if any(re.search(r'/asks/[^/]+/found/', t) for t in touched):
            return False
        return super().quiet(item)


    # ---- the reform: one kind folder at a time, on a slow clock, so the world tightens as it grows
    KINDS_SKIP = SYSTEM_KINDS

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
                  'thinner one at it with moved_to); a text slot that names a thing becomes a reference to its record; a reference that the vantage shows is missing is added when a text in the world states it; a record without '
                  'description gets one line; slot names and value forms '
                  'that differ from the folder\'s siblings are brought in line with a poke. Leave what you are not sure of. Say in one line '
                  'what you changed.)')
        return self.answer(folder, n, {'/said': prompt})


    def line(self, line):
        touched = line.get('touched') or []
        done = 0
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
        if str(self.setting('background') or os.environ.get('AGENT_BACKGROUND', 'off')).lower() in ('off', '0', 'false', 'no'):
            return 0                                          # digest, weave and reform are paused: only what the person says is answered
        return self.reform(now)                                 # the digest hand decomposes texts; the agent tidies


if __name__ == '__main__':
    _hand.run(AgentHand, settings=('name', 'model', 'endpoint', 'stream_port', 'background'))
