"""The hands, end to end on one world: the clock writes the day once; the watch posts on change to a local endpoint;
the export writes a file and pokes the request; the import writes a csv as records with references made once and a
second run writes nothing new; and two hands on one world for a minute leave the event count flat.

Usage: python3 -I -c "import runpy; runpy.run_path('extras/mounts/mcp/tests/hands.py')['check']('http://127.0.0.1:8300', '0x11', 120)"
"""
import csv
import http.server
import importlib.util
import json
import os
import tempfile
import threading
import time
import urllib.request


def load(name):
    here = os.path.dirname(os.path.abspath(__file__))
    spec = importlib.util.spec_from_file_location('hand_' + name, os.path.join(here, '..', 'hands', name + '.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def check(base, node, timeout, quiet_seconds=60):
    hand, clock, watch, export, imp, ask, inbox = (load(n) for n in ('hand', 'clock', 'watch', 'export', 'import_', 'ask', 'inbox'))
    w = hand.World(base, node, timeout)
    checks = []
    quiet = lambda *a: None

    def expect(label, got, want):
        checks.append((label, got, want, got == want))
        assert got == want, (label, got, want)

    home = '/' + node + '/agent/hands'
    for folder in (home, '/' + node + '/user/handed'):
        try:
            w.tool('write', records=[{'path': folder, 'action': 'cull'}])
        except RuntimeError:
            pass
    w.tool('write', records=[{'path': home, 'slots': {'title': 'hands'}}, {'path': '/' + node + '/user/handed', 'slots': {'title': 'handed'}}])

    # clock: once a day, not twice
    c = clock.Clock(w, log=quiet, timezone='UTC')
    day1 = 1_700_000_000                                    # 2023-11-14 22:13 UTC
    expect('clock writes the day on its first tick', c.tick(day1), 1)
    expect('clock does not write the same day twice', c.tick(day1 + 3600), 0)
    expect('/clock holds the day and the timezone', (w.read('/clock').get('properties') or {}).get('/day'), '2023-11-14')
    expect('a new day is one more write', c.tick(day1 + 86400), 1)
    expect('the timezone moves the day: Tokyo is already the 15th at 22:13 UTC on the 14th', clock.today(day1, 'Asia/Tokyo'), '2023-11-15')

    # watch: a local endpoint that records what it got
    got = []

    class Sink(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            got.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
            self.send_response(200); self.end_headers()

        def log_message(self, *a):
            pass
    server = http.server.HTTPServer(('127.0.0.1', 0), Sink)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = 'http://127.0.0.1:%d/hook' % server.server_address[1]
    data = '/' + node + '/user/handed/deals'
    w.tool('write', records=[{'path': data, 'slots': {'title': 'deals'}}, {'path': data + '/d1', 'slots': {'amount': 5}}, {'path': data + '/d2', 'slots': {'amount': 7}}])
    stdlib = {ch['path'].rsplit('/', 1)[1]: {'type': 'reference', 'value': ch['reference']} for ch in w.read('/' + node + '/weft/stdlib', 'y', limit=100)['children']}
    cell = '/' + node + '/user/handed/total'
    w.tool('write', records=[{'path': cell, 'slots': {'sys/weft': stdlib['sum'], 'sys/tack': hand.live(data), 'slot': '/amount'}}])
    wt = watch.Watch(w, log=quiet, cells=cell, url=url)
    expect('watch: the first look keeps the value and posts nothing', (wt.once(), len(got)), (0, 0))
    w.tool('write', records=[{'path': data + '/d3', 'slots': {'amount': 10}}])
    expect('watch: a change posts once', (wt.once(), len(got)), (1, 1))
    expect('watch: the post carries the cell, before and after', (got[0]['cell'], got[0]['before'].get('/total'), got[0]['after'].get('/total')), (cell, '12', '22'))
    expect('watch: no change, no post', (wt.once(), len(got)), (0, 1))
    server.shutdown()

    # export: a request, a file, the poke
    out = tempfile.mkdtemp(prefix='shrine-export-')
    request = home + '/export/r1'
    w.tool('write', records=[{'path': request, 'slots': {'folder': data, 'format': 'csv', 'path': os.path.join(out, 'deals.csv')}}])
    ex = export.Export(w, log=quiet)
    expect('export serves the request', ex.once(), 1)
    with open(os.path.join(out, 'deals.csv'), newline='') as f:
        rows = list(csv.DictReader(f))
    expect('the file has every row with its slots', [(r['path'].rsplit('/', 1)[1], r['amount']) for r in rows], [('d1', '5'), ('d2', '7'), ('d3', '10')])
    done = w.read(request).get('properties') or {}
    expect('the request is poked with done, the path and the count', (done.get('/done'), done.get('/path'), done.get('/rows')), ('true', os.path.join(out, 'deals.csv'), '3'))
    expect('a served request is not served again', ex.once(), 0)

    # import: a csv, the records, the references, a second run writing nothing new
    src = os.path.join(out, 'people.csv')
    with open(src, 'w', newline='') as f:
        wr = csv.writer(f); wr.writerow(['id', 'full name', 'sku', 'zip']); wr.writerow(['p-1', 'Ann Lee', 'a', '02134']); wr.writerow(['p-2', 'Bo Ng', 'b', '10001']); wr.writerow(['p-3', 'Cy', 'zz', '94110'])
    prices = '/' + node + '/user/handed/prices'
    people = '/' + node + '/user/handed/people'
    w.tool('write', records=[{'path': prices, 'slots': {'title': 'prices'}}, {'path': prices + '/p1', 'slots': {'sku': 'a', 'price': 5}}, {'path': prices + '/p2', 'slots': {'sku': 'b', 'price': 7}},
                             {'path': people, 'slots': {'title': 'people'}},
                             {'path': home + '/import/csv', 'slots': {'kind': 'csv', 'source': src, 'folder': people, 'key': 'id', 'every': 0}},
                             {'path': home + '/import/csv/map', 'slots': {'full_name': 'name', 'sku': 'sku'}},      # a field maps through its name: full name is full_name
                             {'path': home + '/import/csv/refs/sku', 'slots': {'table': prices, 'match': 'sku'}}])
    im = imp.Import(w, log=quiet)
    written = im.tick(time.time())
    expect('import writes the rows as records', written >= 3, True)
    p1 = w.read(people + '/p_1').get('properties') or {}
    expect('the field-to-slot map named the slots, the key is a slot, the id kept', (p1.get('/name'), p1.get('/sku'), p1.get('/source_id')), ('Ann Lee', 'a', 'p-1'))
    expect('a zip code with a leading zero stays text', (p1.get('/zip'), (w.read(people + '/p_2').get('properties') or {}).get('/zip')), ('02134', '10001'))
    expect('references made once with the reference entry point at the price rows', (p1.get('/sku_ref'), (w.read(people + '/p_3').get('properties') or {}).get('/sku_ref')), ('/h/x/0/%d%s/p1' % (len(prices.strip('/').split('/')) + 1, prices), None))
    e0 = w.epoch()
    expect('a second run writes nothing new', im.tick(time.time() + 10), 0)       # a later clock, so the ran mark is a change
    later = w.tool('history', after=e0, who='all')
    mark = home + '/import/csv'          # touched lists the mark and the folders above it whose case moved with it
    expect('the second run left no event of its own but the ran mark', [sorted(t for t in e['touched'] if not mark.startswith(t)) for e in later['events']], [[]])
    with open(src, 'a', newline='') as f:
        csv.writer(f).writerow(['p-4', 'Di', 'a', '00501'])
    expect('a new row in the source is one new record, with its reference', (im.tick(time.time() + 20) >= 1, (w.read(people + '/p_4').get('properties') or {}).get('/sku_ref') is not None), (True, True))

    expect('segment_of makes a name from an id, a field or a path', (hand.segment_of('p-1'), hand.segment_of('full name'), hand.segment_of('/0x11/user/views/total'), hand.segment_of('2024')), ('p_1', 'full_name', 'user_views_total', 'c_2024'))
    # inbox: a note under an agent's inbox or a record with to: <name> nudges that agent through its plug; no plug, no nudge
    posted, ran = [], []
    w.tool('write', who='test', records=[{'path': home + '/inbox/to/alice', 'slots': {'url': 'http://127.0.0.1:1/nudge'}},
                                          {'path': home + '/inbox/to/bob', 'slots': {'command': 'true'}}])
    ib = inbox.Inbox(w, log=quiet, plugs={'post': lambda url, payload: posted.append((url, payload)), 'run': lambda cmd, payload: ran.append((cmd, payload))})
    note = {'epoch': 500, 'who': 'ian', 'touched': ['/0x11/agent/alice/inbox/q1', '/0x11/user/plan/step_3'],
            'with': {'/0x11/agent/alice/inbox/q1': {'properties': {'/text': 'how many?'}}, '/0x11/user/plan/step_3': {'properties': {'/to': 'bob', '/text': 'take this step'}}}}
    expect('inbox: a line nudges the inbox owner by url and the addressee by command, and writes nothing',
           (ib.line(note), posted, [c for c, _ in ran], ran[0][1]['paths']),
           (0, [('http://127.0.0.1:1/nudge', {'to': 'alice', 'from': 'ian', 'epoch': 500, 'paths': ['/0x11/agent/alice/inbox/q1']})], ['true'], ['/0x11/user/plan/step_3']))
    expect('inbox: a name with no plug is left waiting', (ib.line({'epoch': 501, 'who': 'ian', 'touched': ['/0x11/agent/nobody/inbox/q2'], 'with': {}}), len(posted) + len(ran)), (0, 2))
    expect('inbox: a hand\'s own line is quiet', ib.take({'epoch': 502, 'who': 'import', 'touched': ['/0x11/agent/alice/inbox/q3'], 'with': {}}), 0)

    # ask on the base still answers (its own test covers the rest)
    a = ask.Hand(w, model='fake', fake=True, log=quiet)
    expect('the ask hand on the base reports nothing to answer when nothing asks', a.tick(), 0)

    # two hands on one world for a minute: the event count stays flat
    e0 = w.epoch()
    stop = threading.Event()

    def live(h):
        gen = hand.stream_follow(base, node, seen=h.seen, interval=1.0, log=quiet)
        h.once(time.time())
        for item in gen:
            if stop.is_set():
                break
            did = h.take(item)
            if did:
                h.mark_seen()
    c2 = clock.Clock(w, log=quiet, timezone='UTC')
    w2 = watch.Watch(w, log=quiet, cells=cell, url='')
    threads = [threading.Thread(target=live, args=(h,), daemon=True) for h in (c2, w2)]
    for t in threads:
        t.start()
    time.sleep(5)
    e1 = w.epoch()
    time.sleep(quiet_seconds)
    e2 = w.epoch()
    stop.set()
    expect('two hands on one world for %d s: the event count is flat' % quiet_seconds, e2 - e1, 0)
    print(json.dumps({'checks': len(checks), 'hand_calls': w.seq, 'quiet_events': e2 - e1, 'startup_events': e1 - e0}), flush=True)


if __name__ == '__main__':
    import sys
    check(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else '0x11', 120)
