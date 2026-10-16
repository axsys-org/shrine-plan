"""The ask hand: a driver that answers ask cells with a model and writes the answer stamped.

Usage: python3 ask.py <base> [--node 0x11] [--model NAME] [--endpoint URL] [--fake] [--once] [--interval 2]

An ask cell is a record whose /sys/weft is /weft/stdlib/ask, with /sys/tack (the input), /prompt and an optional /model.
The hand watches the event log (history after <seen> with x) for ask cells and for writes under their inputs, and for
every ask whose context says /sys/view/asking it reads the input at its current case, calls the model with the prompt,
and writes one event: the result record at <cell>/result with /answer, /case (the input's case, from /sys/tack/case),
/model and /prompt (the stamp), plus the cell's /result reference when the cell has none yet. From then on
/x/<cell> is that answer until the input, the prompt or the model moves.

The model behind it is a config slot on the hand's record, /agent/hands/ask {model, endpoint}, default the local
OpenAI-compatible endpoint (ollama at 127.0.0.1:11434, model llama3.2); --model and --endpoint override it;
OPENROUTER_API_KEY or OPENAI_API_KEY in the environment is sent as a bearer when set. --fake answers without a
model (a deterministic summary of the input), for tests. Where the hand left off is /agent/hands/ask/seen {epoch}.
"""
import argparse
import json
import os
import sys
import time
import urllib.request

DEFAULT_ENDPOINT = 'http://127.0.0.1:11434/v1/chat/completions'
DEFAULT_MODEL = 'llama3.2'


class World:
    def __init__(self, base, node, timeout=120):
        self.base, self.node, self.timeout, self.seq = base, node, timeout, 0

    def tool(self, name, **arguments):
        self.seq += 1
        body = json.dumps(dict(jsonrpc='2.0', id=self.seq, method='tools/call', params={'name': 'mcp/' + name, 'arguments': arguments})).encode()
        req = urllib.request.Request(self.base + '/mcp', body, {'Content-Type': 'application/json'})
        reply = json.load(urllib.request.urlopen(req, timeout=self.timeout))
        result = reply.get('result') or {}
        if 'error' in reply or result.get('isError'):
            raise RuntimeError(json.dumps(reply)[:300])
        return result['structuredContent']

    def read(self, path, care='x', **more):
        return self.tool('read', path=path, care=care, **more)


def live(path, care='y'):
    return {'type': 'reference', 'value': '/h/' + care + '/0/' + str(len(path.strip('/').split('/'))) + path}


def tack_target(reference):
    """The path and care a tack reference names: /h/<care>/<case>/<len>/<path>."""
    parts = reference.split('/')
    care, length = parts[2], int(parts[4])
    return '/' + '/'.join(parts[5:5 + length]), care


def render(view, depth=0, out=None):
    """The input as plain lines for a prompt: path, then slot: value."""
    out = [] if out is None else out
    props = view.get('properties') or {}
    if props or depth == 0:
        out.append(view['path'] + ' ' + ', '.join(f'{k.lstrip("/")}: {v}' for k, v in sorted(props.items()) if not k.startswith('/sys/')))
    for child in view.get('children') or []:
        render(child, depth + 1, out)
    return out


def fake_model(prompt, lines):
    """A deterministic stand-in: counts the records and sums every numeric slot, so a test can check an answer."""
    records = [l for l in lines[1:] if l.strip()]
    total = 0
    for l in records:
        for part in l.split(' ', 1)[1].split(', ') if ' ' in l else []:
            k, _, v = part.partition(': ')
            if k == 'amount' and v.lstrip('-').isdigit():
                total += int(v)
    return f'{len(records)} records, amount total {total}, asked: {prompt}'


def call_model(endpoint, model, prompt, lines, timeout=120):
    key = os.environ.get('OPENROUTER_API_KEY') or os.environ.get('OPENAI_API_KEY')
    headers = {'Content-Type': 'application/json'}
    if key:
        headers['Authorization'] = 'Bearer ' + key
    body = json.dumps({'model': model, 'messages': [
        {'role': 'system', 'content': 'You answer a question about records from a namespace. Answer in one short paragraph, from the records only.'},
        {'role': 'user', 'content': prompt + '\n\nRecords:\n' + '\n'.join(lines)}]}).encode()
    req = urllib.request.Request(endpoint, body, headers)
    reply = json.load(urllib.request.urlopen(req, timeout=timeout))
    return reply['choices'][0]['message']['content'].strip()


class Hand:
    def __init__(self, world, model=None, endpoint=None, fake=False, log=print):
        self.w, self.fake, self.log = world, fake, log
        home = '/' + world.node + '/agent/hands/ask'
        self.home = home
        config = self.w.read(home, 'x').get('properties') or {}
        self.model = model or config.get('/model') or DEFAULT_MODEL
        self.endpoint = endpoint or config.get('/endpoint') or DEFAULT_ENDPOINT
        seen = self.w.read(home + '/seen', 'x').get('properties') or {}
        self.seen = int(seen.get('/epoch') or 0) or self.epoch()     # a hand's first run starts from now, not from the world's boot
        self.asks = {}          # cell path -> (input path, care)
        self.ask_ref = next(c['reference'] for c in self.w.read('/' + world.node + '/weft/stdlib', 'y', limit=100)['children'] if c['path'].endswith('/ask'))
        self.ask_key = self.ask_ref.split('/', 5)[-1]      # the stdlib path without its case: a cell pins any case of it

    def epoch(self):
        with urllib.request.urlopen(self.w.base + '/probe/read?path=/' + self.w.node, timeout=self.w.timeout) as r:
            return int(json.load(r).get('epoch') or 0)

    def is_ask(self, props):
        weft = props.get('/sys/weft') or ''
        return weft.endswith('/weft/stdlib/ask') or weft.split('/', 5)[-1:] == [self.ask_key]

    def discover(self):
        """Every ask cell the log has seen since the hand's seen epoch; the hand's own events are skipped."""
        changed = set()
        while True:
            page = self.w.tool('history', after=self.seen, limit=40, **{'with': 'x'})
            for event in page['events']:
                for path, view in (event.get('with') or {}).items():
                    if path.startswith('/x/') or path.startswith('/c/x/'):
                        continue
                    props = view.get('properties') or {}
                    if self.is_ask(props) and props.get('/sys/tack'):
                        self.asks[path] = tack_target(props['/sys/tack'])
                    changed.add(path)
                self.seen = event['epoch']
            if page.get('next') is None:
                break
        return changed

    def answer(self, cell):
        context = self.w.read('/c/x' + cell, 'x').get('properties') or {}
        why = context.get('/sys/view/asking')
        if why is None:
            return False
        case = int(context.get('/sys/tack/case') or 0)
        prompt = context.get('/prompt') or ''
        model = context.get('/model') or self.model
        path, care = self.asks[cell]
        view = self.w.read(path, care, limit=500)
        lines = render(view)
        answer = fake_model(prompt, lines) if self.fake else call_model(self.endpoint, model, prompt, lines)
        records = [{'path': cell + '/result', 'slots': {'answer': answer, 'case': case, 'model': model, 'prompt': prompt}}]
        if '/result' not in context:
            records.append({'path': cell, 'action': 'poke', 'slots': {'result': live(cell + '/result', 'x')}})
        self.w.tool('write', records=records, who='ask')
        self.log(f'ask {cell}: answered at case {case} with {model} ({why})')
        return True

    def tick(self):
        self.discover()
        answered = 0
        for cell in list(self.asks):
            try:
                answered += self.answer(cell)
            except Exception as e:                      # a model or write failure leaves the cell asking; the next tick retries
                self.log(f'ask {cell}: {e}')
        self.discover()                                   # the hand's own events, so they are not re-read next tick
        self.w.tool('write', records=[{'path': self.home + '/seen', 'slots': {'epoch': self.seen}}], who='ask')
        self.discover()
        return answered


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('base'); p.add_argument('--node', default='0x11'); p.add_argument('--model'); p.add_argument('--endpoint')
    p.add_argument('--fake', action='store_true'); p.add_argument('--once', action='store_true'); p.add_argument('--interval', type=float, default=2.0)
    a = p.parse_args(argv)
    hand = Hand(World(a.base, a.node), a.model, a.endpoint, a.fake)
    while True:
        n = hand.tick()
        if a.once:
            return n
        time.sleep(a.interval)


if __name__ == '__main__':
    main()
