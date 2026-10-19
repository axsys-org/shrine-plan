"""The two safety rules, proved cheaply on one fresh world: code and large atoms never inline, and a reply past the
byte ceiling is refused before it is built.

Usage: python3 -I -c "import runpy; runpy.run_path('extras/mounts/mcp/tests/safety.py')['check']('http://127.0.0.1:8300', '0x11', 120)"
"""
import json
import os
import time
import urllib.request


def check(base, node, timeout):
    seq = [0]
    checks = []

    def rpc(name, **arguments):
        seq[0] += 1
        body = json.dumps(dict(jsonrpc='2.0', id=seq[0], method='tools/call', params={'name': 'mcp/' + name, 'arguments': arguments})).encode()
        req = urllib.request.Request(base + '/mcp', body, {'Content-Type': 'application/json'})
        t0 = time.perf_counter()
        reply = json.load(urllib.request.urlopen(req, timeout=timeout))
        return reply['result'], 1000 * (time.perf_counter() - t0)

    def expect(label, got, want):
        checks.append((label, got, want, got == want))
        assert got == want, (label, got, want)

    def epoch():
        with urllib.request.urlopen(base + '/probe/read?path=/' + node, timeout=timeout) as r:
            return json.load(r)['epoch']

    def walk(view):
        yield view
        for ch in view.get('children') or []:
            yield from walk(ch)

    # 0. before this test writes anything: the boot events with everything inlined, under the cap, in well under 100 ms
    e0 = epoch()
    hist, ms = rpc('history', after=0, limit=40, **{'with': 'x'})
    log = hist['structuredContent']
    inlined = sum(len(list(walk(v))) for e in log['events'] for v in (e.get('with') or {}).values())
    expect('3 history after 0 with x over the boot events answers under the cap, no event (took %.0f ms; the bar is 100)' % ms, (len(log['events']) <= 40, inlined <= 40 * 500, epoch() - e0), (True, True, 0))
    expect('3 under 100 ms', ms < 100, True) if os.environ.get('SAFETY_STRICT') else print('3 boot page: %.0f ms (bar 100 ms)' % ms, flush=True)
    expect('3 boot events are system and hidden by default: the page is empty', log['events'], [])
    everyone, ms_all = rpc('history', after=0, limit=40, who='all', **{'with': 'x'})
    boot = everyone['structuredContent']['events']
    expect('3 asked for all, the boot events come back as who: system with no records inlined, under the cap', (len(boot) > 0, sorted(set(e['who'] for e in boot)), all(e['with'] is None for e in boot), ms_all < 1000), (True, ['system'], True, True))
    sizes = [len(json.dumps(e)) for e in log['events']]
    expect('3 no event carries a compiled law inline', max(sizes, default=0) < 200000, True)

    # 1. a law record reads as references, never its text
    weft, _ = rpc('read', path='/' + node + '/weft', care='y', limit=100)
    law = None
    for module in weft['structuredContent']['children']:        # a published module's compiled content, or a law at /weft/<module>/<len>/<name>
        sub, _ = rpc('read', path=module['path'], care='z', limit=200)
        if 'structuredContent' not in sub:
            continue
        for v in walk(sub['structuredContent']):
            if any(isinstance(x, dict) and x.get('type') == 'code' for x in (v.get('properties') or {}).values()):
                law = v['path']; break
        if law:
            break
    assert law, 'no compiled module or law found under /weft'
    law, ms = rpc('read', path=law, care='x')
    props = law['structuredContent']['properties']
    forms = [v for v in props.values() if isinstance(v, dict)]
    expect('1 a published module or law record answers in milliseconds', ms < 100, True)
    expect('1 its compiled value is a reference form, not text', (len(forms) >= 1, all(set(f) == {'type', 'size', 'reference'} for f in forms), all(f['type'] == 'code' for f in forms), all(f['reference'] == law['structuredContent']['reference'] for f in forms)), (True, True, True, True))
    expect('1 no rendered value is longer than 8 KB', max([len(v) for v in props.values() if isinstance(v, str)], default=0) <= 8192, True)

    # 2. a 9 KB text reads as a reference form; an 8 KB one inlines
    home = '/' + node + '/user/safety'
    written, _ = rpc('write', records=[{'path': home, 'slots': {'title': 'safety'}}, {'path': home + '/big', 'slots': {'blob': 'x' * 9000, 'small': 'y' * 8000}}])
    big, _ = rpc('read', path=home + '/big', care='x')
    bp = big['structuredContent']['properties']
    expect('2 a record with a 9 KB and an 8 KB text is admitted', (bool(written.get('isError')), sorted(bp)), (False, ['/blob', '/small']))
    expect('2 a 9 KB text is {type, size, reference}; an 8 KB one is inline', (bp['/blob']['type'], bp['/blob']['size'], bp['/blob']['reference'] == big['structuredContent']['reference'], set(bp['/blob']), len(bp['/small'])), ('text', 9000, True, {'type', 'size', 'reference'}, 8000))

    # 4. a page that would pass 2 MB is refused before it is built; a smaller page of the same folder answers
    fat = home + '/fat'
    for chunk in range(3):
        rpc('write', records=[{'path': fat + '/r' + str(chunk * 100 + i), 'slots': {'text': 't' * 7000, 'n': i}} for i in range(100)])
    refused, ms = rpc('read', path=fat, care='y', limit=500)
    expect('4 a reply that would pass 2 MB is refused with "too large, page it", quickly', (refused.get('isError'), 'too large, page it' in refused['content'][0]['text'], ms < 2000), (True, True, True))
    smaller, _ = rpc('read', path=fat, care='y', limit=100)
    expect('4 a page of 100 of the same folder answers, with a next', (smaller['structuredContent']['nodes'], smaller['structuredContent']['next'] is not None), (100, True))
    many, _ = rpc('read', paths=[fat, home + '/big'], care='y', limit=500)
    expect('4 in a reads list the oversized entry answers {path, error} and the call goes on', (many['structuredContent']['answers'][0].get('error'), many['structuredContent']['answers'][1]['exists']), ('too large, page it', True))
    print(json.dumps({'checks': len(checks), 'round_trips': seq[0]}), flush=True)
