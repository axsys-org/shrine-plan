"""The ask hand: a driver that answers ask cells with a model and writes the answer stamped.

Usage: python3 ask.py <base> [--node 0x11] [--model NAME] [--endpoint URL] [--fake] [--once]
--once answers every ask pending now and exits.

An ask cell is a record whose /sys/weft is /weft/stdlib/ask, with /sys/tack (the input), /prompt and an optional /model.
The hand finds every ask cell through the reverse index (the holders of a /sys/weft reference to the stdlib ask, read at
/r/<len>/<node>/weft/stdlib/ask), answers the ones whose context says /sys/view/asking, then follows the world's commit
stream (hands/stream.py) and looks again only at the cells a commit woke: each event's `woke` names the cells it wrote
and the cells reading a name it changed, through the reverse index's references, so a write elsewhere costs the hand
nothing. For an ask that is asking it reads the input at its current case, calls the model with the prompt, and writes
one event: the result record at <cell>/result with /answer, /case (the input's case, from /sys/tack/case), /model and
/prompt (the stamp), plus the cell's /result reference when the cell has none yet. From then on /x/<cell> is that answer
until the input, the prompt or the model moves.

The model behind it is a config slot on the hand's record, /agent/hands/ask {model, endpoint}, default the local
OpenAI-compatible endpoint (ollama at 127.0.0.1:11434, model llama3.2); --model and --endpoint override it;
OPENROUTER_API_KEY or OPENAI_API_KEY in the environment is sent as a bearer when set. --fake answers without a
model (a deterministic summary of the input), for tests. The hand keeps no place in the log: on a restart it finds
what is asking through the reverse index again.
"""
import argparse
import importlib.util
import json
import os
import sys
import time
import urllib.request

_spec = importlib.util.spec_from_file_location('stream_hand', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stream.py'))
_stream = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_stream)
stream_follow, Stream = _stream.follow, _stream.Stream

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
        self.asks = {}          # cell path -> (input path, care) for an ask; None for a cell that is not one
        self.ask_path = '/' + world.node + '/weft/stdlib/ask'
        self.checked = 0        # contexts read: the cost of looking
        self.answered = 0

    def learn(self, cell):
        """Read a cell's record once: an ask (with its input) or not."""
        props = self.w.read(cell, 'x').get('properties') or {}
        weft = props.get('/sys/weft') or ''
        is_ask = weft.split('/', 5)[-1:] == [self.ask_path.strip('/')] or weft.endswith(self.ask_path)
        self.asks[cell] = tack_target(props['/sys/tack']) if is_ask and props.get('/sys/tack') else None

    def discover(self):
        """Every ask cell, from the reverse index: the holders of a /sys/weft reference to the stdlib ask."""
        listing = '/r/' + str(len(self.ask_path.strip('/').split('/'))) + self.ask_path
        cells = set()

        def walk(view):
            props = view.get('properties') or {}
            if props.get('/slot') == '/sys/weft' and props.get('/holder'):
                cells.add(tack_target(props['/holder'])[0])
            for child in view.get('children') or []:
                walk(child)
        after = None
        while True:
            page = self.w.read(listing, 'z', limit=500, **({'next': after} if after else {}))
            walk(page)
            after = page.get('next')
            if not after:
                break
        for cell in cells:
            if cell not in self.asks:
                self.learn(cell)
        return cells

    def answer(self, cell):
        """Answer one ask if its context says it is asking; True when it did."""
        self.checked += 1
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
        self.answered += 1
        self.log(f'ask {cell}: answered at case {case} with {model} ({why})')
        return True

    def pending(self):
        """Answer every known ask that is asking."""
        answered = 0
        for cell, ask in list(self.asks.items()):
            if ask:
                try:
                    answered += self.answer(cell)
                except Exception as e:                  # a model or write failure leaves the cell asking
                    self.log(f'ask {cell}: {e}')
        return answered

    def tick(self):
        """Find every ask and answer what is asking now (--once, and a hand's start)."""
        self.discover()
        return self.pending()

    def wake(self, line):
        """One commit: look at the asks it woke, and only those. A cell the commit wrote is read again (its input,
        prompt or model may have moved); a woken cell never seen is learned. A commit that woke more cells than its
        event names (woke_count) sends the hand back to the reverse index."""
        woke = line.get('woke') or []
        if line.get('woke_count', len(woke)) > len(woke):
            self.discover()
            woke = [c for c, a in self.asks.items() if a]
        touched = set(line.get('touched') or [])
        answered = 0
        for cell in woke:
            try:
                if cell not in self.asks or cell in touched:
                    self.learn(cell)
                if self.asks.get(cell):
                    answered += self.answer(cell)
            except Exception as e:
                self.log(f'ask {cell}: {e}')
        return answered

    def run(self, lines):
        """The hand's life: every commit the stream pushes, then the asks it woke."""
        for line in lines:
            if 'epoch' in line:
                self.wake(line)


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('base'); p.add_argument('--node', default='0x11'); p.add_argument('--model'); p.add_argument('--endpoint')
    p.add_argument('--fake', action='store_true'); p.add_argument('--once', action='store_true')
    a = p.parse_args(argv)
    hand = Hand(World(a.base, a.node), a.model, a.endpoint, a.fake)
    if a.once:
        return hand.tick()
    # open the stream first, so a commit between the discovery and the first event is still heard
    opened = Stream(a.base)
    seen = opened.opened_at()
    opened.close()
    hand.tick()
    hand.run(stream_follow(a.base, seen=seen, log=hand.log))


if __name__ == '__main__':
    main()
