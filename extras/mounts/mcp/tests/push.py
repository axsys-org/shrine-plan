"""The commit push, end to end: a write in the world reaches a subscriber of /mcp/stream in milliseconds, from any
writer (MCP and the probe mount); a subscriber that reconnects with ?after=<epoch> gets every commit after it from the
journal, once each, while writes keep coming; each event's `woke` names exactly the cells reading what the commit
changed, through the reverse index (a cell over a cell included); the ask hand, driven by the stream, re-asks only when
a name its ask reads changes. Prints the measured latencies as one JSON line.

Usage: python3 -I -c "import runpy; runpy.run_path('extras/mounts/mcp/tests/push.py')['check']('http://127.0.0.1:8300', '0x11', 120)"
"""
import importlib.util
import json
import os
import statistics
import threading
import time
import urllib.request
import uuid


def _load(name, *parts):
    spec = importlib.util.spec_from_file_location(name, os.path.join(os.path.dirname(os.path.abspath(__file__)), *parts))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check(base, node, timeout):
    stream_hand = _load('stream_hand', '..', 'hands', 'stream.py')
    ask_hand = _load('ask_hand', '..', 'hands', 'ask.py')
    Stream = stream_hand.Stream
    seq = [0]
    checks = []
    lock = threading.Lock()

    def expect(label, got, want):
        checks.append((label, got, want, got == want))
        assert got == want, (label, got, want)

    def tool(name, **arguments):
        with lock:
            seq[0] += 1
            n = seq[0]
        body = json.dumps(dict(jsonrpc='2.0', id=n, method='tools/call', params={'name': 'mcp/' + name, 'arguments': arguments})).encode()
        req = urllib.request.Request(base + '/mcp', body, {'Content-Type': 'application/json'})
        reply = json.load(urllib.request.urlopen(req, timeout=timeout))
        result = reply['result']
        assert not result.get('isError'), result
        return result['structuredContent']

    def write(records, who='tester'):
        return tool('write', records=records, who=who)['epoch']

    def probe_write(path, **slots):
        body = '&'.join(['path=' + path] + [k + '=' + str(v) for k, v in slots.items()]).encode()
        urllib.request.urlopen(urllib.request.Request(base + '/probe/make', body), timeout=timeout).read()

    def top():
        with urllib.request.urlopen(base + '/probe/read?path=/' + node, timeout=timeout) as r:
            return json.load(r)['epoch']

    def ref(path, care='y'):
        return {'type': 'reference', 'value': '/h/' + care + '/0/' + str(len(path.strip('/').split('/'))) + path}

    def until(stream, epoch, limit=10):
        """Events from a stream up to and including epoch."""
        got = []
        while True:
            e = stream.event()
            if 'epoch' in e:
                got.append(e)
                if e['epoch'] >= epoch:
                    return got

    home = '/' + node + '/user/pushed_' + uuid.uuid4().hex[:8]     # fresh each run: an identical write commits nothing
    write([{'path': home, 'slots': {'title': 'pushed'}}])

    # 1. a live subscriber: the open says where it starts; every write reaches it, timed from the write's send
    live = Stream(base, timeout=10)
    start = live.opened_at()
    expect('1 a live open says the epoch it starts at', start, top())
    write([{'path': home + '/warm', 'slots': {'n': 0}}])
    until(live, top())
    after_send, after_ack = [], []
    for i in range(40):
        t0 = time.perf_counter()
        epoch = write([{'path': home + '/w' + str(i), 'slots': {'n': i}}])
        t1 = time.perf_counter()
        e = live.event()
        t2 = time.perf_counter()
        assert e['epoch'] == epoch and home + '/w' + str(i) in e['touched'], e
        after_send.append(1000 * (t2 - t0))
        after_ack.append(1000 * max(0.0, t2 - t1))
    expect('1 forty writes, forty events, each the write\'s epoch, writer and path', len(after_send), 40)
    expect('1 the event carries who wrote it', e['who'], 'tester')

    # 2. a writer that is not MCP: the probe mount's make reaches the same stream
    t0 = time.perf_counter()
    probe_write(home + '/probed', n=7)
    e = live.event()
    probe_ms = 1000 * (time.perf_counter() - t0)
    expect('2 a probe make (not MCP) reaches the stream as one event naming its path', home + '/probed' in e['touched'], True)

    # 3. reconnect from an epoch while writes keep coming: no gap, no repeat
    seen = e['epoch']
    live.close()
    missed = [write([{'path': home + '/gap' + str(i), 'slots': {'n': i}}]) for i in range(10)]
    stop = threading.Event()
    during = []

    def writer():
        i = 0
        while not stop.is_set() and i < 60:
            during.append(write([{'path': home + '/during' + str(i), 'slots': {'n': i}}], who='writer'))
            i += 1
    thread = threading.Thread(target=writer)
    thread.start()
    t0 = time.perf_counter()
    again = Stream(base, after=seen, timeout=10)
    first = again.event()
    resume_ms = 1000 * (time.perf_counter() - t0)
    thread.join()
    stop.set()
    last = top()
    got = [first] + (until(again, last) if first['epoch'] < last else [])
    epochs = [x['epoch'] for x in got]
    expect('3 a reconnect after an epoch replays from the next epoch', epochs[0], seen + 1)
    expect('3 every epoch to the top once, in order, while sixty writes ran', epochs, list(range(seen + 1, last + 1)))
    expect('3 the ten written while away are among them', set(missed) <= set(epochs), True)
    again.close()

    # 4. woke: the cells reading what a commit changed, and only those, through the reverse index
    stdlib = {c['path'].rsplit('/', 1)[1]: {'type': 'reference', 'value': c['reference']} for c in tool('read', path='/' + node + '/weft/stdlib', care='y', limit=100)['children']}
    a, b = home + '/a', home + '/b'
    ca, cb, cc = home + '/views/count_a', home + '/views/count_b', home + '/views/picked_a'
    write([{'path': a, 'slots': {'title': 'a'}}, {'path': b, 'slots': {'title': 'b'}}] +
          [{'path': a + '/r' + str(i), 'slots': {'amount': i}} for i in range(3)] +
          [{'path': b + '/r' + str(i), 'slots': {'amount': i}} for i in range(3)])
    w = Stream(base, timeout=10)
    w.opened_at()
    write([{'path': ca, 'slots': {'sys/weft': stdlib['count'], 'sys/tack': ref(a)}},
           {'path': cb, 'slots': {'sys/weft': stdlib['count'], 'sys/tack': ref(b)}}])
    e = w.event()
    expect('4 writing two cells wakes both', sorted(e['woke']), sorted([ca, cb]))
    write([{'path': cc, 'slots': {'sys/weft': stdlib['pick'], 'sys/tack': ref('/x' + ca, 'x'), 'from': '/count', 'into': '/n'}}])
    expect('4 writing a cell over a cell wakes it alone', w.event()['woke'], [cc])
    write([{'path': a + '/r9', 'slots': {'amount': 9}}])
    e = w.event()
    expect('4 a write under a wakes the cell over a and the cell over that, not the cell over b', sorted(e['woke']), sorted([ca, cc]))
    write([{'path': b + '/r1', 'action': 'poke', 'slots': {'amount': 10}}])
    expect('4 a write under b wakes the cell over b alone', w.event()['woke'], [cb])
    write([{'path': home + '/elsewhere', 'slots': {'n': 1}}])
    expect('4 a write nobody reads wakes nothing', w.event()['woke'], [])
    write([{'path': a + '/r9/deep', 'slots': {'n': 1}}])
    deep = w.event()['woke']
    write([{'path': a, 'action': 'cull'}])
    culled = w.event()['woke']
    expect('4 a cull of a wakes its readers', sorted(culled), sorted([ca, cc]))
    w.close()

    # 5. the ask hand on the stream: re-asks only when a name its ask reads changes
    write([{'path': a, 'slots': {'title': 'a again'}}, {'path': a + '/r1', 'slots': {'amount': 100}}])
    hand = ask_hand.Hand(ask_hand.World(base, node, timeout), model='fake', fake=True, log=lambda *x: None)
    ask = home + '/views/verdict'
    opened = Stream(base, timeout=10)
    seen = opened.opened_at()
    opened.close()
    hand.tick()
    lines = stream_hand.follow(base, seen=seen, log=lambda *x: None)
    write([{'path': ask, 'slots': {'sys/weft': stdlib['ask'], 'sys/tack': ref(a), 'prompt': 'How much?', 'model': 'fake'}}])
    hand.wake(next(lines))
    expect('5 the hand answers a new ask from the event that wrote it', hand.answered, 1)
    while next(lines).get('who') != 'ask':
        pass                                           # the hand's own answer, which wakes the ask (and finds it answered)
    checked, answered = hand.checked, hand.answered
    write([{'path': b + '/r2', 'action': 'poke', 'slots': {'amount': 50}}])
    hand.wake(next(lines))
    expect('5 a write under b (unread by the ask) costs the hand nothing: no context read, no answer', (hand.checked, hand.answered), (checked, answered))
    t0 = time.perf_counter()
    write([{'path': a + '/r2', 'slots': {'amount': 7}}])
    hand.wake(next(lines))
    reask_ms = 1000 * (time.perf_counter() - t0)
    expect('5 a write under a re-asks once', hand.answered, answered + 1)
    expect('5 the new answer is stamped with the input\'s new case', tool('read', path='/x' + ask, care='x')['exists'], True)
    print(json.dumps({'checks': len(checks),
                      'write_to_event_ms': {'median': round(statistics.median(after_send), 2), 'p95': round(sorted(after_send)[37], 2), 'max': round(max(after_send), 2)},
                      'ack_to_event_ms': {'median': round(statistics.median(after_ack), 3), 'max': round(max(after_ack), 3)},
                      'probe_write_to_event_ms': round(probe_ms, 2),
                      'reconnect_first_event_ms': round(resume_ms, 2), 'replayed': len(epochs),
                      'deep_write_woke': deep,
                      'reask_write_to_answer_ms': round(reask_ms, 2)}), flush=True)
