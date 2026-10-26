"""The base every hand is built on: the world half, written once.

A hand is a process outside the world. It never runs inside the runtime and never touches the store; it talks to the
world only through the MCP surface a coworker's agent gets: read, write, history and the stream. The five parts, from
the coverage note:

1. Config is a record: /agent/hands/<name> holds the hand's settings as slots; the hand reads it at start and a person
   changes it with a write (overrides given on the command line win).
2. Where it left off is a record: /agent/hands/<name>/seen {epoch}. A hand with no seen record starts from the world's
   first event.
3. It follows the stream, and polls when it cannot (stream.follow): a hand reacts to lines, it never sleeps and re-reads.
4. Everything it does is a write with its name on it (who: <name>, or <name>_<artifact>), idempotent: a hand that runs twice over the same
   events writes the same records. update() is write-if-unchanged: it carries the case it read, so two hands on one
   record cannot lose each other's work.
5. A failure leaves the world honest: the base logs it and retries on the next line; a hand computes its whole answer
   before its one write, so it never writes a partial one.

A hand is a subclass with at most two methods: line(line), what to do with a stream line, and tick(now), what to do
on a tick (every `every` seconds, and once at start). Both return how many writes they made.

    class Clock(Hand):
        name = 'clock'
        def tick(self, now): ...

Run one with run(argv): python3 <hand>.py <base> [--node 0x11] [--once] [--interval 2] [--<setting> value]...
"""
import argparse
import importlib.util
import json
import os
import re
import sys
import time
import urllib.request

_spec = importlib.util.spec_from_file_location('stream_hand', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stream.py'))
_stream = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_stream)
stream_follow, stream_poll = _stream.follow, _stream.poll


class World:
    """The MCP surface, as any agent sees it."""
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

    def view(self, name, thing):
        """A standard woven view (overlay, frontier, union) applied to a thing, read from
        the world at /o: every node beneath the application keyed by its relative path, slots without the leading
        slash. None when the world has no such definition (an older kernel) or the view faulted."""
        node = '/' + self.node
        case = self._view_cases.get(name) if hasattr(self, '_view_cases') else None
        if case is None:
            try:
                r = self.read(f'{node}/weft/graph/{name}', 'x')
                m = re.match(r'^/h/x/(\d+)/', str(r.get('reference') or ''))
                case = int(m.group(1)) if r.get('exists') and m else 0
            except Exception:
                case = 0
            self._view_cases = getattr(self, '_view_cases', {}); self._view_cases[name] = case
        if not case:
            return None
        defn = [self.node, 'weft', 'graph', name]; segs = [x for x in str(thing).split('/') if x]
        base = f"/o/{case}/{len(defn)}/{'/'.join(defn)}/{len(segs)}/{'/'.join(segs)}"
        nodes, nxt = {}, None
        for _ in range(20):
            r = self.read(base, 'z', limit=500, **({'next': nxt} if nxt else {}))
            def visit(n):
                if n.get('path', '').startswith(base):
                    nodes[n['path'][len(base):]] = {k.lstrip('/'): v for k, v in (n.get('properties') or {}).items()}
                for c in n.get('children') or []:
                    visit(c)
            visit(r); nxt = r.get('next')
            if not nxt:
                break
        if not nodes or nodes.get('', {}).get('sys/view/fault'):
            return None
        return nodes

    def read_all(self, path, care='y'):
        """A folder whole: every page's nodes indexed by path, then one tree rebuilt from the index."""
        nodes, order = {}, {}
        page = self.read(path, care, limit=500)
        root = page['path']
        while True:
            def walk(n, parent):
                if n['path'] not in nodes or (nodes[n['path']].get('paged') and not n.get('paged')):
                    nodes[n['path']] = {k: v for k, v in n.items() if k != 'children'}
                if parent is not None:
                    order.setdefault(parent, [])
                    if n['path'] not in order[parent]:
                        order[parent].append(n['path'])
                for ch in n.get('children', []):
                    walk(ch, n['path'])
            walk(page, None)
            if not page.get('next'):
                break
            page = self.read(path, care, limit=500, next=page['next'])

        def build(p):
            n = dict(nodes[p])
            n.pop('paged', None)
            n['children'] = [build(c) for c in order.get(p, [])]
            return n
        return build(root)

    def epoch(self):
        with urllib.request.urlopen(self.base + '/probe/read?path=/' + self.node, timeout=self.timeout) as r:
            return int(json.load(r).get('epoch') or 0)


def segment_of(text):
    """A valid name from an id, a field or a path: letters, digits and underscores kept, anything else an
    underscore, a letter first (c-7 is c_7; /0x11/user/views/total is user_views_total; 2024 is c_2024).  The one
    rule every hand needs when it names a record after something it did not choose."""
    text = str(text).strip('/')
    parts = text.split('/')
    if len(parts) > 1 and re.fullmatch(r'0x[0-9a-fA-F]+', parts[0]):
        parts = parts[1:]                                          # a path: the node is the folder, not the name
    key = re.sub(r'[^A-Za-z0-9_]', '_', '_'.join(parts)) or 'empty'
    return key if re.match(r'[A-Za-z]', key) else 'c_' + key


def live(path, care='y'):
    return {'type': 'reference', 'value': '/h/' + care + '/0/' + str(len(path.strip('/').split('/'))) + path}


def case_of(reference):
    """The case a rendered x reference carries: /h/x/<case>/<len>/<path>."""
    return int(reference.split('/')[3]) if reference else 0


HANDS = ('clock', 'source', 'agent', 'web', 'links', 'digest', 'sync')


class Hand:
    name = 'hand'
    every = 60.0            # seconds between ticks
    lag = 100               # lines a hand may fall behind its seen mark before a tick marks it anyway

    def __init__(self, world, log=print, **overrides):
        self.w, self.log = world, log
        self.home = '/' + world.node + '/agent/hands/' + self.name
        config = (self.w.read(self.home, 'x').get('properties') or {})
        self.config = {k.lstrip('/'): v for k, v in config.items() if not k.startswith('/sys')}
        self.config.update({k: v for k, v in overrides.items() if v is not None})
        seen = self.w.read(self.home + '/seen', 'x').get('properties') or {}
        self.seen = int(seen.get('/epoch') or 0)
        self.marked = self.seen
        self.last_tick = None

    # ---- the two methods a hand writes
    def line(self, line):
        return 0

    def tick(self, now):
        return 0

    # ---- what the base gives it
    def setting(self, key, default=None):
        return self.config.get(key, default)

    def write(self, records):
        """One signed event; a hand writes once, with everything computed."""
        return self.w.tool('write', records=records, who=self.name)

    def update(self, path, slots, action='poke'):
        """Write-if-unchanged: the record's case as read rides with the write, so a record another hand changed
        meanwhile refuses this write instead of losing theirs."""
        current = self.w.read(path, 'x')
        record = {'path': path, 'slots': slots, 'action': action}
        if current.get('exists'):
            record['if_case'] = case_of(current.get('reference'))
        return self.w.tool('write', records=[record], who=self.name)

    def mark_seen(self):
        """Write the seen mark when it moved.  A mark is an event: on the live page it lands on top of whatever the
        hand just saw, so it is written after the hand's own writes, and otherwise only when the hand has fallen
        `lag` lines behind its last mark (a restart then catches up from there, which is reads, not events)."""
        if self.seen != self.marked:
            self.w.tool('write', records=[{'path': self.home + '/seen', 'slots': {'epoch': self.seen}}], who=self.name)
            self.marked = self.seen

    def behind(self):
        return self.seen - self.marked >= self.lag

    def catch_up(self):
        """Every line since seen, from the log (the poll's shape), through line()."""
        done = 0
        while True:
            lines, nxt = stream_poll(self.w.base, self.w.node, self.seen)
            for item in lines:
                done += self.take(item)
            if not lines or nxt == self.seen:
                break
            self.seen = nxt
        return done

    def quiet(self, item):
        """A line that never causes a write by itself: one from any hand (its name, or its name and an underscore, as
        the source hand signs source_<artifact>), or one whose touched paths all sit under /agent/hands (a seen mark,
        a kept value, a config poke).  Without this rule two hands ping-pong on each
        other's seen marks forever."""
        who = item.get('who') or ''
        if who in HANDS or who.split('_', 1)[0] in HANDS or who == self.name:
            return True
        touched = item.get('touched') or []
        hands = '/' + self.w.node + '/agent/hands'
        return bool(touched) and all(t == hands or t.startswith(hands + '/') for t in touched)

    def take(self, item):
        """One line: its epoch is seen; a quiet line is skipped; a failure is logged and the next line retries."""
        if 'epoch' in item:
            self.seen = max(self.seen, item['epoch'])
        if self.quiet(item):
            return 0
        try:
            return self.line(item) or 0
        except Exception as e:
            self.log(f'{self.name}: {e}')
            return 0

    def once(self, now=None):
        """Catch up, tick, mark seen: one pass, for --once and for tests."""
        now = time.time() if now is None else now
        done = self.catch_up()
        try:
            done += self.tick(now) or 0
        except Exception as e:
            self.log(f'{self.name}: {e}')
        self.last_tick = now
        self.catch_up()
        if done or self.behind():
            self.mark_seen()
        return done

    def run(self, follow_lines, clock=time.time):
        """The hand's life: a tick at start, every line as it comes, a tick every `every` seconds.  Seen is marked
        after the hand wrote something, or on a tick once it is `lag` lines behind its mark: a mark is an event, a
        line to every other hand and the top of the live page, so an idle hand writes none."""
        self.once(clock())
        for item in follow_lines:
            did = self.take(item)
            now = clock()
            ticked = self.last_tick is None or now - self.last_tick >= self.every
            if ticked:
                try:
                    did += self.tick(now) or 0
                except Exception as e:
                    self.log(f'{self.name}: {e}')
                self.last_tick = now
            if did or (ticked and self.behind()):
                self.mark_seen()


def run(cls, argv=None, settings=()):
    """Start a hand from the command line: python3 <hand>.py <base> [--node 0x11] [--once] [--interval 2] [--<setting> V]."""
    p = argparse.ArgumentParser()
    p.add_argument('base'); p.add_argument('--node', default='0x11'); p.add_argument('--once', action='store_true'); p.add_argument('--interval', type=float, default=2.0)
    for key in settings:
        p.add_argument('--' + key.replace('_', '-'), dest=key)
    a = p.parse_args(argv)
    hand = cls(World(a.base, a.node), **{key: getattr(a, key) for key in settings})
    if a.once:
        return hand.once()
    hand.run(stream_follow(a.base, a.node, seen=hand.seen, interval=a.interval, log=hand.log))
