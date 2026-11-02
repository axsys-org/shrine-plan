"""The hands, end to end on one world: the clock writes the day once; the source hand binds a csv (eager rows: every
row a region, typed, a second pass writing nothing, a changed row rewritten alone, a removed row culled, the post plug
told once, an edit written back to its row only with write on the artifact, a conflict left alone) and a markdown file (lazy headings: the skeleton first, a region when a cell waits at its path, a rewrite
only where the digest moved); and two hands on one world for a minute leave the event count flat.

Usage: python3 -I -c "import runpy; runpy.run_path('extras/mounts/mcp/tests/hands.py')['check']('http://127.0.0.1:8300', '0x11', 120)"
"""
import csv
import importlib.util
import json
import os
import tempfile
import threading
import time


def load(name):
    here = os.path.dirname(os.path.abspath(__file__))
    spec = importlib.util.spec_from_file_location('hand_' + name.replace('/', '_'), os.path.join(here, '..', 'hands', name + '.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def check(base, node, timeout, quiet_seconds=60):
    hand, clock, source, rows = (load(n) for n in ('hand', 'clock', 'source', 'sources/rows'))
    w = hand.World(base, node, timeout)
    checks = []
    quiet = lambda *a: None

    def expect(label, got, want):
        checks.append((label, got, want, got == want))
        assert got == want, (label, got, want)

    def props(path):
        return {k.lstrip('/'): v for k, v in (w.read(path, 'x').get('properties') or {}).items()}

    def case(path):
        return hand.case_of(w.read(path, 'x').get('reference'))

    home = '/' + node + '/agent/hands'
    scope = '/' + node + '/user/handed'
    for folder in (home, scope):
        try:
            w.tool('write', records=[{'path': folder, 'action': 'cull'}])
        except RuntimeError:
            pass
    w.tool('write', records=[{'path': home, 'slots': {'title': 'hands'}}, {'path': scope, 'slots': {'title': 'handed'}}])

    # clock: once a day, not twice
    c = clock.Clock(w, log=quiet, timezone='UTC')
    day1 = 1_700_000_000                                    # 2023-11-14 22:13 UTC
    expect('clock writes the day on its first tick', c.tick(day1), 1)
    expect('clock does not write the same day twice', c.tick(day1 + 3600), 0)
    expect('/clock holds the day and the timezone', (w.read('/clock').get('properties') or {}).get('/day'), '2023-11-14')
    expect('a new day is one more write', c.tick(day1 + 86400), 1)
    expect('the timezone moves the day: Tokyo is already the 15th at 22:13 UTC on the 14th', clock.today(day1, 'Asia/Tokyo'), '2023-11-15')

    # source, eager rows: a csv is its rows, typed, each a region with the hand's three slots
    out = tempfile.mkdtemp(prefix='shrine-source-')
    src = os.path.join(out, 'people.csv')
    def write_csv(lines):
        with open(src, 'w', newline='') as f:
            wr = csv.writer(f); wr.writerow(['id', 'full name', 'amount', 'zip'])
            for line in lines:
                wr.writerow(line)
        os.utime(src, None)
    write_csv([['p-1', 'Ann Lee', '12', '02134'], ['p-2', 'Bo Ng', '7', '10001'], ['p-3', 'Cy', '3', '94110']])
    sources = scope + '/sources'
    people = sources + '/people'
    w.tool('write', records=[{'path': sources, 'slots': {'title': 'sources'}}, {'path': people, 'slots': {'where': src, 'script': 'rows', 'key': 'id'}}])
    posted = []
    s = source.Source(w, log=quiet, plug=lambda url, payload: posted.append(payload), folders=sources, url='http://sink.invalid/hook')
    t0 = time.time()
    expect('a first pass writes every row as a region and the marker', s.once(t0), 3)
    p1 = props(people + '/p_1')
    expect('a row is its columns in the header words, the key as text, a number as a number, the position as row',
           (p1.get('full_name'), p1.get('id'), p1.get('amount'), p1.get('row')), ('Ann Lee', 'p-1', '12', '2'))
    expect('a zip code with a leading zero stays text', (p1.get('zip'), props(people + '/p_2').get('zip')), ('02134', '10001'))
    expect('the hand owns source and digest and nothing else', (p1.get('source', '').startswith('/h/x/0/'), len(p1.get('digest', '')), sorted(p1)),
           (True, 16, ['amount', 'digest', 'full_name', 'id', 'row', 'source', 'zip']))
    expect('the artifact record carries the marker read', props(people).get('marker', '').startswith('mtime '), True)
    expect('the first contact is a change: the plug is told once', [(p['artifact'], p['written'], p['culled']) for p in posted], [(people, 3, 0)])
    e0 = w.epoch()
    expect('a second pass over an unchanged source writes nothing', (s.once(t0 + 1), w.epoch() - e0), (0, 0))
    c2 = case(people + '/p_2')
    time.sleep(1.1)                                         # a new mtime second, so the marker moves
    write_csv([['p-1', 'Ann Lee', '15', '02134'], ['p-2', 'Bo Ng', '7', '10001'], ['p-4', 'Di', '9', '00501']])
    e1 = w.epoch()
    expect('a changed source: the changed row rewritten, the new row written, the lost row culled', s.once(t0 + 2), 3)
    expect('all of it one event, signed source_<artifact>', [e['who'] for e in w.tool('history', after=e1, who='all')['events'] if e['who'] != 'source'], ['source_people'])
    expect('the rewritten row has its new figure', props(people + '/p_1').get('amount'), '15')
    expect('the untouched row did not move', case(people + '/p_2'), c2)
    expect('the lost row is gone and the new one is there with its leading zero', (w.read(people + '/p_3').get('exists'), props(people + '/p_4').get('zip')), (False, '00501'))
    expect('the plug is told of the change', len(posted), 2)

    # write-back: a region edited in the world goes back to its own row, only with write on the artifact
    def file_rows():
        with open(src, newline='') as f:
            return [(r['id'], r['amount']) for r in csv.DictReader(f)]
    w.tool('write', records=[{'path': people + '/p_2', 'action': 'poke', 'slots': {'amount': 8}}], who='tester')
    expect('an edit with no write on the artifact: nothing written, the file untouched, the edit kept', (s.once(t0 + 3), file_rows()[1], props(people + '/p_2').get('amount')), (0, ('p-2', '7'), '8'))
    w.tool('write', records=[{'path': people, 'action': 'poke', 'slots': {'write': True}}], who='tester')
    expect('with write on the artifact the edited region is written back and its digest and the marker follow', s.once(t0 + 4), 1)
    expect('the file has that one row changed and the others as they were', file_rows(), [('p-1', '15'), ('p-2', '8'), ('p-4', '9')])
    e3 = w.epoch()
    expect('after a write-back the next pass writes nothing', (s.once(t0 + 5), w.epoch() - e3), (0, 0))
    w.tool('write', records=[{'path': people + '/p_1', 'action': 'poke', 'slots': {'amount': 99}}], who='tester')
    time.sleep(1.1)
    write_csv([['p-1', 'Ann Lee', '16', '02134'], ['p-2', 'Bo Ng', '8', '10001'], ['p-4', 'Di', '10', '00501']])
    expect('a region edited here and in the source is a conflict: the other change lands, that region is left alone both ways',
           (s.once(t0 + 6), props(people + '/p_1').get('amount'), props(people + '/p_4').get('amount'), file_rows()[0]), (1, '99', '10', ('p-1', '16')))
    expect('and stays a conflict, nothing written, until one side is made to match', s.once(t0 + 7), 0)
    w.tool('write', records=[{'path': people + '/p_1', 'action': 'poke', 'slots': {'amount': 16}}], who='tester')
    expect('the world made to match the source: no conflict, the digest follows, the file untouched', (s.once(t0 + 8), file_rows()[0]), (1, ('p-1', '16')))
    expect('typed: the key is text, a leading zero is text, a whole number a number, a decimal a decimal',
           (rows.typed('7', key=True), rows.typed('007'), rows.typed('7'), rows.typed('7.5'), rows.typed('x')), ({'type': 'str', 'value': '7'}, {'type': 'str', 'value': '007'}, 7, 7.5, 'x'))

    # source, lazy headings: the skeleton first, a region when a cell waits at its path
    doc = os.path.join(out, 'notes.md')
    with open(doc, 'w') as f:
        f.write('# Holes\nA hole is a path with nothing at it.\n\n## First pending wins\nThe first stage that is pending stops the chain.\n\n## Culls\nA cull faults dependents.\n\n# Views\nViews compute.\n')
    notes = sources + '/notes'
    w.tool('write', records=[{'path': notes, 'slots': {'where': doc, 'script': 'headings'}}])
    expect('a first pass over a lazy source writes the skeleton: every heading as a path, nothing inside', s.once(t0 + 8), 4)
    fpw = notes + '/holes/first_pending_wins'
    expect('a skeleton node has the source reference and no content', sorted(props(fpw)), ['source'])
    e2 = w.epoch()
    expect('an unchanged lazy source with nothing waiting writes nothing', (s.once(t0 + 9), w.epoch() - e2), (0, 0))
    stdlib = {ch['path'].rsplit('/', 1)[1]: {'type': 'reference', 'value': ch['reference']} for ch in w.read('/' + node + '/weft/stdlib', 'y', limit=100)['children']}
    cell = scope + '/views/first_rule'
    w.tool('write', records=[{'path': cell, 'slots': {'sys/weft': stdlib['pick'], 'sys/tack': hand.live(fpw, 'x'), 'from': '/title', 'into': '/rule'}}])
    expect('a cell waiting at a heading path is the request: the region is written, and only it', s.once(t0 + 10), 1)
    region = props(fpw)
    expect('the region is the heading, its position, and the size and digest of what is under it; never the prose',
           (region.get('title'), region.get('level'), region.get('line'), region.get('words'), len(region.get('body', '')), 'text' in region),
           ('First pending wins', '2', '4', '9', 16, False))
    expect('the cell now reads the title', (w.read('/x' + cell, 'x').get('properties') or {}).get('/rule'), 'First pending wins')
    expect('the sibling heading stayed a skeleton node', sorted(props(notes + '/holes/culls')), ['source'])
    with open(doc, 'w') as f:
        f.write('# Holes\nA hole is a path with nothing at it.\n\n## First pending wins\nThe first pending stage stops the chain; the rest continue.\n\n## Culls\nA cull faults dependents.\n\n# Views\nViews compute.\n')
    fc = case(fpw)
    expect('a changed lazy source re-reads only the regions that exist: one rewrite, the skeleton untouched', s.once(t0 + 12), 1)
    expect('the region moved to its new case: the words and the digest of what is under it changed', (case(fpw) > fc, props(fpw).get('words')), (True, '10'))
    expect('the sibling is still a skeleton node', sorted(props(notes + '/holes/culls')), ['source'])
    w.tool('write', records=[{'path': notes, 'action': 'poke', 'slots': {'write': True}}, {'path': fpw, 'action': 'poke', 'slots': {'text': 'The first pending stage stops the chain.'}}], who='tester')
    expect('a text slot put on a heading region is written back under its heading, and the region re-read without it', s.once(t0 + 13), 1)
    with open(doc) as f:
        expect('the file has that section replaced and every other byte as it was', f.read(),
               '# Holes\nA hole is a path with nothing at it.\n\n## First pending wins\nThe first pending stage stops the chain.\n\n## Culls\nA cull faults dependents.\n\n# Views\nViews compute.\n')
    expect('the prose lives in the file, not the world', ('text' in props(fpw), props(fpw).get('words')), (False, '7'))

    expect('segment_of makes a name from an id, a field or a path', (hand.segment_of('p-1'), hand.segment_of('full name'), hand.segment_of('/0x11/user/views/total'), hand.segment_of('2024')), ('p_1', 'full_name', 'user_views_total', 'c_2024'))

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
    s2 = source.Source(w, log=quiet, plug=lambda url, payload: None, folders=sources)
    threads = [threading.Thread(target=live, args=(h,), daemon=True) for h in (c2, s2)]
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
