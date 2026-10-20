"""The ask hand: a driver that answers ask cells with a model and writes the answer stamped.

Usage: python3 ask.py <base> [--node 0x11] [--model NAME] [--endpoint URL] [--fake] [--once] [--interval 2]
A first run walks the log from epoch 0 (see Hand.__init__ for the cost); --once answers every ask pending now and exits.

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
import importlib.util
import json
import os
import urllib.request

_base = importlib.util.spec_from_file_location('hand_base', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hand.py'))
_hand = importlib.util.module_from_spec(_base); _base.loader.exec_module(_hand)
World, Hand, stream_poll = _hand.World, _hand.Hand, _hand.stream_poll

DEFAULT_ENDPOINT = 'http://127.0.0.1:11434/v1/chat/completions'
DEFAULT_MODEL = 'llama3.2'


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


class AskHand(Hand):
    """The ask hand on the base: line() learns the ask cells a line wrote and answers what is asking; tick() catches
    up and answers everything pending."""
    name = 'ask'
    every = 30.0

    def __init__(self, world, model=None, endpoint=None, fake=False, log=print):
        super().__init__(world, log=log, model=model, endpoint=endpoint)
        self.fake = fake
        self.model = self.setting('model') or DEFAULT_MODEL
        self.endpoint = self.setting('endpoint') or DEFAULT_ENDPOINT
        self.asks = {}          # cell path -> (input path, care)
        self.ask_ref = next(c['reference'] for c in self.w.read('/' + world.node + '/weft/stdlib', 'y', limit=100)['children'] if c['path'].endswith('/ask'))
        self.ask_key = self.ask_ref.split('/', 5)[-1]      # the stdlib path without its case: a cell pins any case of it

    def is_ask(self, props):
        weft = props.get('/sys/weft') or ''
        return weft.endswith('/weft/stdlib/ask') or weft.split('/', 5)[-1:] == [self.ask_key]

    def learn(self, line):
        """The ask cells a line wrote."""
        for path, view in (line.get('with') or {}).items():
            if path.startswith('/x/') or path.startswith('/c/x/'):
                continue
            props = view.get('properties') or {}
            if self.is_ask(props) and props.get('/sys/tack'):
                self.asks[path] = tack_target(props['/sys/tack'])

    def line(self, line):
        self.learn(line)
        return sum(self.answer(cell) for cell in list(self.asks))

    def tick(self, now=None):
        """Answer what is asking; with no time given, one whole pass (catch up, answer, mark seen), as the tests call it."""
        if now is None:
            return self.once()
        return sum(self.answer(cell) for cell in list(self.asks))

    def answer(self, cell):
        """One ask: nothing when it is not asking; else the whole answer computed, then one write."""
        context = self.w.read('/c/x' + cell, 'x').get('properties') or {}
        why = context.get('/sys/view/asking')
        if why is None:
            return 0
        case = int(context.get('/sys/tack/case') or 0)
        prompt = context.get('/prompt') or ''
        model = context.get('/model') or self.model
        path, care = self.asks[cell]
        view = self.w.read(path, care, limit=500)
        lines = render(view)
        try:
            answer = fake_model(prompt, lines) if self.fake else call_model(self.endpoint, model, prompt, lines)
        except Exception as e:                      # a model failure leaves the cell asking; the next line or tick retries
            self.log(f'ask {cell}: {e}')
            return 0
        records = [{'path': cell + '/result', 'slots': {'answer': answer, 'case': case, 'model': model, 'prompt': prompt}}]
        if '/result' not in context:
            records.append({'path': cell, 'action': 'poke', 'slots': {'result': live(cell + '/result', 'x')}})
        self.write(records)
        self.log(f'ask {cell}: answered at case {case} with {model} ({why})')
        return 1

    # the names the tests and the setup page use
    def discover(self):
        return self.catch_up()

    def handle(self, line):
        self.learn(line)


Hand = AskHand


def main(argv=None):
    return _hand.run(AskHand, argv, settings=('model', 'endpoint'))


if __name__ == '__main__':
    main()
