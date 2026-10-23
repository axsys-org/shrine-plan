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
import os
import re
import time
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

Reply with one JSON object and nothing else: no prose around it, no markdown fence, no XML, no tool-call syntax.
{
  "reads":   ["/0x11/...", {"find": "a term", "under": "/0x11/..."}],
                                            optional. Paths to look at before you answer (a record, a folder, /x/<cell>),
                                            or a search: the records under a folder whose name or any slot holds the
                                            term, each with the slot that matched. You will be asked again with those
                                            lookups attached. At most a few.
  "said":    "...",                         what you say to the person. Plain words. Short.
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
When the world cannot answer and the pool cannot either, send the question out instead of guessing: write an ask,
{"path": "<your folder>/asks/<short id>", "slots": {"asked": "<the question, precisely>", "scope": "<sites, years,
terms that bound the search>", "shape": "<the slots you want back, with types: e.g. year: YYYY, revenue_usd: number,
published: YYYYMMDD>"}}, and a cell that counts its answers: {"path": "<your folder>/views/<id>_found", "slots":
{"sys/weft": <count's reference>, "sys/tack": {"type":"reference","path":"<your folder>/asks/<id>/found","care":"y","case":0}}}.
Put that cell's /x in your next lens. Tell the person you have sent it out and keep working; a web hand fills
<ask>/found/* with typed rows (each with a page and a source reference) and your next reading shows them. Then decide
what is a fact, write it where it belongs in /0x11/user with a source reference to the found row, compose the view,
and drop the ask from your lens. You may also fill an ask yourself from the pool if you find the answer there.
For a collection (what a publication posted, an org's repos, a team's members), add "many": true to the ask and give
the shape of one item; the items come back as many rows, and you put them beneath their parent, one vocabulary.

Be curious, and link everything. A slot that names another thing (a language, a licence, an organisation, a person, a
publication, a protocol, a product, a place) is a reference to that thing's record, never its name as text. Find the
record first ({"find": name, "under": "/0x11/user"}). If none exists, make a stub where its kind lives
(/0x11/user/<kinds>/<slug>, e.g. /0x11/user/languages/hoon, with name and nothing invented), point the slot at it, and
unless you are certain of what it is (the MIT licence), write an ask to research it, shaped for its kind (a language:
creator, first_appeared, paradigm, site; a publication: publisher, founded, site, plus a "many" ask for its issues or
articles). Every unknown name becomes a hole the web hand fills, and the world becomes a web of records a person can
walk: everything a hop or two from everything else. When you integrate a found row, its source is the page region the
row cites (the row's own source slot), never the ask.

A slot that will change on its own (stars, last commit, a price, a headcount, a latest version) gets a recipe, written
once, so it stays current without you: {"path": "/0x11/user/recipes/<slug>", "slots": {"record": <reference to the
record>, "slot": "<slot name>", "url": "<where it is read>", "kind": "json" or "css", "select": "<a dotted path into
the JSON, e.g. stargazers_count>" (for css leave select out: the refresh hand finds it from the record's current value),
"parse": "number" or "day" or "text", "every": <seconds>}}. For a GitHub repo prefer kind json on
https://api.github.com/repos/<owner>/<repo> (stargazers_count, pushed_at). Never re-research a slot that has a recipe.
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
                if isinstance(obj, dict) and ('said' in obj or 'context' in obj or 'reads' in obj):
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


class AgentHand(Hand):
    name = 'agent'
    every = 3600.0

    def __init__(self, world, log=print, **overrides):
        super().__init__(world, log=log, **overrides)
        self.name = self.setting('name') or 'a'          # the default chat; the hand answers every chat under /agent
        self.model = self.setting('model') or DEFAULT_MODEL
        self.endpoint = self.setting('endpoint') or DEFAULT_ENDPOINT
        self.folder = '/' + world.node + '/agent/' + self.name
        self.stdlib = None

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
        """Every chat whose latest turn is the person's: (folder, n, props)."""
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

    def stdlib_refs(self):
        if self.stdlib is None:
            self.stdlib = {c['path'].rsplit('/', 1)[1]: c['reference'] for c in self.w.read('/' + self.w.node + '/weft/stdlib', 'y', limit=100)['children']}
        return self.stdlib

    # ---- one turn
    def answer(self, folder, n, props):
        self.folder = folder
        self.name = folder.rsplit('/', 1)[1]
        said = props.get('/said') or ''
        reading = '\n'.join(self.context_reading())
        user = f'YOUR NAME: {self.name}   YOUR FOLDER: {self.folder}   (your asks go under {self.folder}/asks, your views under {self.folder}/views, your lens is {self.folder}/context)\n\nYOUR CONTEXT (the world through your lens, now):\n{reading}\n\nTHE PERSON SAYS:\n{said}'
        messages = [{'role': 'system', 'content': BOOTSTRAP}, {'role': 'user', 'content': user}]
        reply = {}
        for round_ in range(MAX_LOOKUPS + 1):
            text = call_model(self.endpoint, self.model, messages)
            if not parse_json(text):
                self.log(f'{self.name}: no JSON in the reply; asking once more')
                text = call_model(self.endpoint, self.model, messages + [{'role': 'assistant', 'content': text or '(empty)'}, {'role': 'user', 'content': 'That was not a JSON object. Reply with exactly one JSON object: {"said": ..., "writes": [...], "context": {...}} and nothing else.'}])
            try:
                reply = parse_json(text)
            except Exception as e:
                self.log(f'{self.name}: unparseable reply: {e}: {text[:200]}')
                reply = {'said': text.strip()[:2000], 'context': {}}
                break
            reads = reply.get('reads') or []
            if not reads or round_ == MAX_LOOKUPS:
                break
            looked = []
            for p in reads[:6]:
                try:
                    if isinstance(p, dict) and p.get('find'):
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
            messages.append({'role': 'assistant', 'content': text.lstrip('{') if False else text})
            messages.append({'role': 'user', 'content': 'LOOKUPS (not kept; put what you want to keep seeing in your next context):\n' + '\n\n'.join(looked) + '\n\nNow reply with your JSON (said, writes, context).'})
        # the world: what it decided to write, signed by its name
        writes = [w for w in (reply.get('writes') or []) if isinstance(w, dict) and w.get('path')]
        refused = self.apply(writes)
        if refused:
            self.log(f'{self.name}: {len(refused)} of {len(writes)} writes refused')
            reply['said'] = (reply.get('said') or '') + '\n(refused: ' + '; '.join(f'{p} {why}' for p, why in refused[:4]) + ')'
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
        self.log(f'{self.name}: turn {n + 1} ({len(writes)} writes, lens of {len(slots)})')
        return 1

    def apply(self, writes):
        """The model's writes as one event; when the batch is refused, one by one, so one wrong record does not
        take the rest with it. Returns the refused ones with the kernel's reason."""
        if not writes:
            return []
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
                refused.append((w['path'], str(e)[:80]))
        return refused

    def quiet(self, item):
        """A web hand's fill under one of my asks is the one hand line that must wake me."""
        if any(re.search(r'/agent/[a-z]\d*/asks/[^/]+/found/', t) for t in (item.get('touched') or [])):
            return False
        return super().quiet(item)

    def line(self, line):
        touched = line.get('touched') or []
        done = 0
        # a fill landing under one of my asks is the alert: a turn of my own, unprompted, to integrate it and tell the person
        for t in touched:
            m = re.match(r'^(/' + self.w.node + r'/agent/[a-z]\d*)/asks/([^/]+)/found/', t)
            if m and (line.get('who') or '') != m.group(1).rsplit('/', 1)[1]:
                folder, aid = m.group(1), m.group(2)
                self.folder = folder
                ts = self.turns()
                n = ts[-1][0] if ts else 0
                done += self.answer(folder, n, {'/said': f'(not the person: the web hand filled your ask {aid}; its rows are in your reading. Decide what is a fact, write it where it belongs with a source reference to the row, compose the view, drop the ask from your lens, and tell the person what came back.)'})
                break
        if not any(re.search(r'/agent/[a-z]\d*/turns', t) for t in touched):
            return done
        return done + sum(self.answer(*p) for p in self.pending())

    def tick(self, now):
        return sum(self.answer(*p) for p in self.pending())


if __name__ == '__main__':
    _hand.run(AgentHand, settings=('name', 'model', 'endpoint'))
