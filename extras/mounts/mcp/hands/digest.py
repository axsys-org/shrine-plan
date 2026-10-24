"""The digest hand: every text in the world is decomposed into the world, soon after it arrives.

The links index keeps the queue of texts not yet digested, newest first. Four workers take them a few at a time and
ask a fast model to write what each text states, under the world's structure rules and nothing else: one canonical
record per thing, a slash only for parts, every relation asserted once as a slot naming the other thing (child
records when it has several values or qualifiers), and a source slot naming the text. The other direction of a
relation is never written; the index reads it. The hand then marks each text digested.

    python3 digest.py <base> [--node 0x11] [--model anthropic/claude-haiku-5.5] [--workers 4]
"""
import importlib.util
import json
import os
import re
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

_here = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location('agent_hand', os.path.join(_here, 'agent.py'))
_agent = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_agent)
_hand = _agent._hand
Hand, segment_of = _hand.Hand, _hand.segment_of
call_model, render, unwrap_path = _agent.call_model, _agent.render, _agent.unwrap_path

DEFAULT_MODEL = 'anthropic/claude-haiku-5.5'
BATCH = 3

RULES = """You decompose texts into a world of records under /0x11/user. Reply with one JSON object and nothing else:
{"writes": [ ... ]}, each write {"path": ..., "slots": {...}}.

Structure, and only structure:
- One thing, one canonical record, at /0x11/user/<a folder for its kind>/<slug>. A slash means part of: file a thing
  under another only when it is a part of it (a section of a document, a team inside a company). Reuse the records
  listed for you; make a new one, with name and description and nothing invented, only for a thing the text says
  something about.
- A relation is asserted once, on the record it belongs to, as a slot whose value is the other thing's path:
  {"founder": "/0x11/user/people/forbes_mckenzie"}. Never write the other direction.
- A relation with several values or with qualifiers is child records of the thing, one per value, each holding the
  path and its qualifiers: /0x11/user/books/walkaway/authors/cory_doctorow {"author": "/0x11/user/people/cory_doctorow",
  "role": "writer"}.
- Provenance: a source slot on what you write, holding the text's path (sources/<n> child records when several).
- Values: numbers as numbers, days as YYYYMMDD, years as YYYY. Slugs: lowercase letters, digits, underscores.
- Reuse slot labels already in use; write only what the texts state; skip opinion and colour; nothing already recorded.
"""


class DigestHand(Hand):
    name = 'digest'
    every = 5.0

    def __init__(self, world, log=print, **overrides):
        super().__init__(world, log=log, **overrides)
        self.node = '/' + world.node
        self.model = self.setting('model') or DEFAULT_MODEL
        self.pool = ThreadPoolExecutor(max_workers=int(self.setting('workers') or 4))
        self.flight = {}            # text -> when it was handed to a worker (or when it may be tried again)
        self.lock = threading.Lock()
        self.gather = None
        self.log(f'digest: {self.model}, {self.pool._max_workers} workers')

    def index(self, route):
        try:
            return json.load(urllib.request.urlopen('http://127.0.0.1:' + str(self.setting('links_port') or 8312) + route, timeout=10))
        except Exception:
            return {}

    def quiet(self, item):
        return True                 # it works from the index's queue, not from the stream

    def mark_seen(self):
        pass

    def tick(self, now):
        q = self.index('/undigested?limit=24')
        texts = [t['path'] for t in (q.get('texts') or [])]
        with self.lock:
            free = [t for t in texts if now >= self.flight.get(t, 0)]
            for t in free:
                self.flight[t] = now + 600
        for i in range(0, len(free), BATCH):
            self.pool.submit(self.safe_batch, free[i:i + BATCH])
        return 0

    def safe_batch(self, texts):
        try:
            self.batch(texts)
        except Exception as e:
            self.log(f'digest: batch failed ({str(e)[:120]}); tried again in ten minutes')

    def batch(self, texts):
        blocks = []
        for t in texts:
            props = self.w.read(t, 'x').get('properties') or {}
            body = ' '.join(str(props[k]) for k in ('/heading', '/title', '/text', '/said', '/quote', '/note') if isinstance(props.get(k), str))
            page = t.rsplit('/', 1)[0]
            pp = self.w.read(page, 'x').get('properties') or {}
            lines = [f'TEXT {t}' + (f"  (from {pp.get('/title', '')}, {pp.get('/url', '')}, fetched {pp.get('/fetched', '')})" if pp.get('/url') else ''), body[:4000]]
            mentions = self.w.read(t + '/mentions', 'x').get('properties') or {}
            known = [unwrap_path(str(v)) for k, v in mentions.items() if not k.startswith('/sys')]
            if known:
                lines.append('REAL RECORDS IT NAMES (reuse these):')
                for k in known[:10]:
                    a = self.index('/around?at=' + urllib.parse.quote(k) + '&depth=1')
                    rels = '; '.join(f"{r['label']}{' of' if r['way'] == 'in' else ''} {r['other']}" for r in (a.get('relations') or [])[:6])
                    lines.append('  ' + ' | '.join(render(self.w.read(k, 'x'))[:3]) + (f'  relations: {rels}' if rels else ''))
            cands = [c['name'] for c in (self.index('/candidates?in=' + urllib.parse.quote(t)).get('candidates') or [])]
            if cands:
                lines.append('NAMES IN IT WITH NO RECORD YET: ' + ', '.join(cands[:20]))
            blocks.append('\n'.join(lines))
        user = '\n\n'.join(blocks)
        text = call_model(_agent.DEFAULT_ENDPOINT, self.model, [{'role': 'system', 'content': RULES}, {'role': 'user', 'content': user}])
        start = (text or '').find('{')
        reply = json.JSONDecoder().raw_decode(text[start:])[0] if start >= 0 else {}
        writes = [w for w in (reply.get('writes') or []) if isinstance(w, dict) and str(w.get('path', '')).startswith(self.node + '/user/')]
        refused = self.apply(writes)
        done = [{'path': t, 'action': 'poke', 'slots': {'digested': True}} for t in texts]
        self.w.tool('write', records=done, who=self.name)
        with self.lock:
            for t in texts:
                self.flight.pop(t, None)
        rels = sum(1 for w in writes for v in (w.get('slots') or {}).values() if isinstance(v, dict))
        self.log(f"digest: {len(texts)} texts, {len(writes)} writes ({rels} relation slots), {len(refused)} refused" + (f": {refused[0]}" if refused else ''))

    def apply(self, writes):
        if self.gather is None:
            stdlib = self.w.read(self.node + '/weft/stdlib', 'y', limit=100).get('children') or []
            self.gather = next((c['reference'] for c in stdlib if c['path'].endswith('/gather')), None)
        for w in writes:
            w['path'] = re.sub(r'/+', '/', str(w['path']).rstrip('/'))
            w.pop('overlay', None); w.pop('note', None)
            slots = {}
            for k, v in (w.get('slots') or {}).items():
                if isinstance(v, str) and re.match(r'^/0x[0-9a-f]+/[a-z]', v.strip()) and ' ' not in v.strip():
                    slots[k] = {'type': 'reference', 'path': unwrap_path(v.strip()), 'care': 'x', 'case': 0}   # a name, read at its own place
                elif isinstance(v, dict) and v.get('type') == 'reference':
                    slots[k] = dict(v, path=unwrap_path(str(v.get('path'))), care='x', case=0)
                elif not isinstance(v, (dict, list)):
                    slots[k] = v
            w['slots'] = slots
            try:
                exists = bool(self.w.read(w['path'], 'x').get('exists'))
            except Exception:
                exists = False
            w['action'] = 'poke' if exists and not w.get('action') else (w.get('action') or 'make')
            if w['action'] == 'poke' and not exists:
                w['action'] = 'make'
        refused = []
        try:
            r = self.w.tool('write', records=writes, who=self.name)
            if not r.get('refused'):
                return []
        except Exception:
            pass
        for w in writes:
            try:
                r = self.w.tool('write', records=[w], who=self.name)
                if r.get('refused'):
                    refused.append((w['path'], str(r.get('reason'))[:80]))
            except Exception as e:
                refused.append((w['path'], str(e)[:80]))
        return refused


if __name__ == '__main__':
    _hand.run(DigestHand, settings=('model', 'workers', 'links_port'))
