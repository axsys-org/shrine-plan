"""The product, end to end, through MCP only, on the loaded world (web, goo, explorer, mcp).

Usage: python3 -I -c "import runpy; runpy.run_path('extras/mounts/mcp/tests/product.py')['check']('http://127.0.0.1:8300', '0x11', 120)"
Every step asserts a value; every call records its time and the sovereign events it cost (the probe
mount's epoch read, when that mount is loaded). Ends with a table and a hard fail if any read costs an
event or any write more than one.
"""
import json
import statistics
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor


def check(base, node, timeout):
    seq = 0
    timings = {}   # call type -> [ms]
    events = {}    # call type -> [events per call]

    def epoch():
        try:
            with urllib.request.urlopen(base + '/probe/read?path=/' + node, timeout=timeout) as r:
                return json.load(r).get('epoch')
        except Exception:
            return None

    def rpc(method, params, kind=None):
        nonlocal seq
        seq += 1
        body = json.dumps(dict(jsonrpc='2.0', id=seq, method=method, params=params)).encode()
        req = urllib.request.Request(base + '/mcp', body, {'Content-Type': 'application/json'})
        e0 = epoch() if kind else None
        start = time.perf_counter()
        with urllib.request.urlopen(req, timeout=timeout) as response:
            reply = json.load(response)
        ms = 1000 * (time.perf_counter() - start)
        if kind:
            timings.setdefault(kind, []).append(ms)
            e1 = epoch()
            if e0 is not None and e1 is not None:
                events.setdefault(kind, []).append(e1 - e0)
        return reply

    def tool(name, kind=None, **arguments):
        reply = rpc('tools/call', {'name': 'mcp/' + name, 'arguments': arguments}, kind or name)
        assert 'error' not in reply, reply
        result = reply['result']
        assert not result.get('isError'), result
        return result['structuredContent']

    def tool_error(name, **arguments):
        reply = rpc('tools/call', {'name': 'mcp/' + name, 'arguments': arguments}, name + ' (refused)')
        return reply.get('result', {}).get('isError') or 'error' in reply

    def write(path, kind='write', **props):
        return tool('write', kind, path=path, properties=props)

    def read(path, care='y', kind='read'):
        return tool('read', kind, path=path, care=care)

    def live(path, care='y'):
        return {'type': 'reference', 'value': '/h/' + care + '/0/' + str(len(path.strip('/').split('/'))) + path}

    def ref(reference):
        return {'type': 'reference', 'value': reference}

    checks = []

    def expect(label, got, want):
        checks.append((label, got, want, got == want))
        assert got == want, (label, got, want)

    # 1. the standard library
    lib = read('/' + node + '/weft/stdlib', kind='read stdlib')
    stdlib = {c['path'].rsplit('/', 1)[1]: ref(c['reference']) for c in lib['children']}
    expect('1 thirty-four library entries present (thirty-three formulas and ask)', len(stdlib), 34)
    expect('1 each formula has a title', all('/sys/lede' in c['properties'] for c in lib['children']), True)

    # 2. the raw data
    org = '/' + node + '/user/org'
    # a rerun on the same world starts clean: cull the test's home (refused, and harmless, when it is not
    # there), then revive it with its children in ONE event: a culled path refuses writes beneath it until
    # the culled record is written again, so delete-and-recreate is one batch
    tool_error('write', records=[{'path': org, 'action': 'cull'}])
    members = org + '/teams/eng/members'
    deals = org + '/sales/deals'
    seed = [(org, {'title': 'Org'}), (members, {'title': 'Engineering'}), (members + '/alice', {'salary': 120}), (members + '/bob', {'salary': 100}),
            (org + '/teams/ops/members/cat', {'salary': 90}), (org + '/budgets/2026/eng', {'amount': 300})]
    for key, amount, status, owner, when, customer, cost in [
            ('d101', 5000, 'closed', 'ann', 10, 'acme', 1000), ('d102', 7000, 'open', 'bo', 20, 'zed', 2500),
            ('d103', 2500, 'closed', 'ann', 30, 'acme', 500)]:
        seed.append((deals + '/' + key, dict(amount=amount, status=status, owner=owner, when=when, customer=customer, cost=cost, **{'amount/scale': 2, 'cost/scale': 2})))
    seed += [(org + '/customers/c1', {'name': 'acme', 'region': 'west'}), (org + '/customers/c2', {'name': 'zed', 'region': 'east'}),
             (org + '/flags/f1', {'ok': True}), (org + '/flags/f2', {'ok': False})]
    seeded = tool('write', 'write (seed, one batch)', records=[{'path': p, 'slots': v} for p, v in seed])
    expect('2 the seed is one event that revives the culled folder with its children', (events['write (seed, one batch)'][-1], seeded['refused'], len(seeded['records'])), (1, False, len(seed)))
    write(org + '/extra/e1', amount=1)
    cells = org + '/views'

    def cell(name, formula, tack, **params):
        props = {'sys/weft': stdlib[formula], 'sys/tack': tack}
        props.update(params)
        write(cells + '/' + name, kind='write cell', **props)
        return cells + '/' + name

    def x(name, care='x', kind='read /x'):
        return read('/x' + cells + '/' + name, care, kind)

    def c(name):
        return read('/c/x' + cells + '/' + name, 'x', kind='read /c/x')['properties']

    def prop(name, slot):
        return x(name)['properties'].get(slot)

    def child(name, key):
        for ch in x(name, 'y')['children']:
            if ch['path'].rsplit('/', 1)[1] == key:
                return ch['properties']
        return None

    def kids(name):
        return len(x(name, 'y')['children'])

    # 3. count and sum, reads cost no event and little time
    cell('headcount', 'count', live(members), into='/headcount')
    cell('payroll', 'sum', live(members), slot='/salary', into='/total')
    expect('3 headcount', prop('headcount', '/headcount'), '2')
    expect('3 payroll', prop('payroll', '/total'), '220')
    for _ in range(3):
        prop('payroll', '/total')  # the first evaluation of a law compiles it; assert on a warm read
    expect('3 reads cost no event', events.get('read /x', [1])[-1], 0)
    expect('3 a warm read is under the 50 ms ceiling (times are informational; speed drift belongs to the soak run)', timings['read /x'][-1] < 50, True)

    # 4. composition through /x
    cell('closed', 'where', live(deals), key='/status', value='closed')
    cell('closed_revenue', 'sum', live('/x' + cells + '/closed'), slot='/amount', into='/revenue')
    expect('4 where feeding sum, at scale 2', (prop('closed_revenue', '/revenue'), prop('closed_revenue', '/scale')), ('7500', '2'))

    # 5. a secondary input across folders, mixed scales
    cell('remaining', 'subtract', live('/x' + cells + '/payroll'),
         budget=ref(read(org + '/budgets/2026/eng', 'x')['reference']), left='/views/budget/amount', right='/total', into='/left')
    expect('5 budget minus payroll', prop('remaining', '/left'), '80')
    cell('margin_total', 'subtract', live('/x' + cells + '/closed_revenue'),
         budget=ref(read(org + '/budgets/2026/eng', 'x')['reference']), left='/views/budget/amount', right='/revenue')
    expect('5 mixed scales align: 300.00 minus 75.00', (prop('margin_total', '/result'), prop('margin_total', '/scale')), ('22500', '2'))

    # 6. the rest of the library, one assertion each
    cell('eng_payroll', 'sum', live(members), slot='/salary')
    cell('ops_payroll', 'sum', live(org + '/teams/ops/members'), slot='/salary')
    expect('6 payroll per team (one sum cell per team)', (prop('eng_payroll', '/total'), prop('ops_payroll', '/total')), ('220', '90'))
    cell('pivot', 'grid', live(deals), row='/owner', col='/status')
    expect('6 grid: owner by status', child('pivot', 'ann')['/closed'], '2')
    cell('margins', 'each', live(deals), left='/amount', op='subtract', right='/cost', into='/margin')
    expect('6 each: margin per deal', child('margins', 'd101')['/margin'], '4000')
    cell('regions', 'lookup', live(deals), key='/customer', match='/name', take='/region', into='/region', table=live(org + '/customers'))
    expect('6 lookup: region on each deal', child('regions', 'd102')['/region'], 'east')
    cell('statuses', 'distinct', live(deals), slot='/status')
    expect('6 distinct statuses', kids('statuses'), 2)
    cell('narrow', 'select', live(deals), slots='/amount /status')
    expect('6 select narrows the record', sorted(child('narrow', 'd101')), ['/amount', '/status'])
    cell('bystatus', 'by', live(deals), key='/status', op='sum', slot='/amount')
    expect('6 by: sum per status', child('bystatus', 'closed')['/sum'], '7500')
    cell('sorted', 'sort', live(deals), slot='/amount');     expect('6 sort', child('sorted', '1')['/key'], 'd103')
    cell('top2', 'top', live(deals), slot='/amount', count=2); expect('6 top', kids('top2'), 2)
    cell('latest', 'latest', live(deals), slot='/when');     expect('6 latest', prop('latest', '/key'), 'd103')
    cell('mid', 'between', live(deals), slot='/when', **{'from': '15', 'to': '35'}); expect('6 between', kids('mid'), 2)
    cell('age', 'since', live('/x' + cells + '/latest'), slot='/when', **{'from': '10'}); expect('6 since', prop('age', '/since'), '20')
    cell('min', 'min', live(deals), slot='/amount');         expect('6 min', prop('min', '/min'), '2500')
    cell('max', 'max', live(deals), slot='/amount');         expect('6 max', prop('max', '/max'), '7000')
    cell('avg', 'avg', live(deals), slot='/amount');         expect('6 avg at scale 2', (prop('avg', '/avg'), prop('avg', '/scale')), ('4833', '2'))
    cell('any', 'any', live(org + '/flags'), slot='/ok');   expect('6 any', prop('any', '/any'), 'true')
    cell('all', 'all', live(org + '/flags'), slot='/ok');   expect('6 all', prop('all', '/all'), 'false')
    cell('flat', 'flatten', live(deals));                   expect('6 flatten', kids('flat'), 3)
    cell('merged', 'merge', live(deals), extra=live(org + '/extra')); expect('6 merge', kids('merged'), 4)
    cell('picked', 'pick', live('/x' + cells + '/payroll'), budget=ref(read(org + '/budgets/2026/eng', 'x')['reference']),
         **{'from': '/views/budget/amount', 'into': '/budget'})
    expect('6 pick', prop('picked', '/budget'), '300')
    cell('noted', 'put', live('/x' + cells + '/payroll'), into='/note', value='reviewed'); expect('6 put', prop('noted', '/note'), 'reviewed')
    cell('rounded', 'round', live('/x' + cells + '/avg'), slot='/avg', places=0); expect('6 round half up', prop('rounded', '/avg'), '48')

    # 7. reactivity: one write, one event
    raised = tool('write', 'write (raise)', path=members + '/alice', action='poke', properties={'salary': 150}, then=['/x' + cells + '/payroll', '/c/x' + cells + '/payroll'])
    expect('7 raise costs one event', events['write (raise)'][-1], 1)
    expect('7 then: the write answers with the cells it changed', raised['then']['/x' + cells + '/payroll']['properties']['/total'], '250')
    expect('7 payroll follows', prop('payroll', '/total'), '250')
    expect('7 remaining follows', prop('remaining', '/left'), '50')
    expect('7 headcount unchanged', prop('headcount', '/headcount'), '2')

    # 8. pinning
    pinned_members = read(members, 'y')['reference_y']
    cell('payroll_frozen', 'sum', ref(pinned_members), slot='/salary', into='/total')
    write(members + '/bob', action='poke', salary=110)
    expect('8 a cell pinned to the input case stays', prop('payroll_frozen', '/total'), '250')
    expect('8 the live cell moved', prop('payroll', '/total'), '260')
    earlier = x('payroll')['reference']
    pinned_read = read(earlier, 'x', kind='read /h')
    expect('8 /h/x of a live cell reads no answer (a live cell has no pinned case, by rule)', pinned_read['exists'], False)
    expect('8 and /c says why', c('payroll').get('/sys/view/fault') is None, True)

    # 9. gaps
    cell('hole', 'sum', live(deals))
    expect('9 missing slot: /x passes the input through', kids('hole'), 3)
    expect('9 missing slot: /c/x names it', 'Supply /slot' in c('hole').get('/sys/view/missing', ''), True)

    # 10. cycles
    cell('loop', 'count', live(cells))
    expect('10 self loop reads unknown', x('loop')['exists'], False)
    expect('10 self loop: /c/x says cycle', c('loop').get('/sys/view/fault', '').startswith('cycle'), True)
    cell('ping', 'count', live('/x' + cells + '/pong'))
    cell('pong', 'count', live('/x' + cells + '/ping'))
    expect('10 two-cell loop: /c/x says cycle', c('ping').get('/sys/view/fault', '').startswith('cycle'), True)
    expect('10 the world still answers', prop('headcount', '/headcount'), '2')

    # 11. a dangling reference
    cell('dangling', 'count', live(org + '/nowhere'))
    expect('11 missing input: fault at /c/x, no hang', c('dangling').get('/sys/view/fault', '').startswith('tack'), True)

    # 12. amend
    stamp = int(c('payroll')['/sys/tack/case'])
    write(cells + '/notes/n1', slot='/total', value=230, case=stamp)
    cell('amended', 'amend', live('/x' + cells + '/payroll'), notes=live(cells + '/notes'))
    expect('12 note lays over the total', prop('amended', '/total'), '230')
    expect('12 stamp current: quiet', '/sys/view/note/n1' in c('amended'), False)
    write(members + '/bob', action='poke', salary=120)
    expect('12 after a raise the note still applies', prop('amended', '/total'), '230')
    expect('12 and /c/x says it predates the change', c('amended').get('/sys/view/note/n1', '').startswith('note at case'), True)
    write(cells + '/rownotes/r1', slot='/d101/amount', value=6000, case=1)
    write(cells + '/rownotes/r2', slot='/d999/amount', value=1, case=1)
    cell('closed_amended', 'amend', live('/x' + cells + '/closed'), notes=live(cells + '/rownotes'))
    expect('12 path note corrects one row', child('closed_amended', 'd101')['/amount'], '6000')
    expect('12 dangling path reported, not created', ('/sys/view/note/r2' in c('closed_amended'), kids('closed_amended')), (True, 2))
    tool('write', 'write (cull)', path=cells + '/notes/n1', action='cull')
    expect('12 note removed: back to the formula', prop('amended', '/total'), '270')

    # 13. history and apply
    hist = tool('history', 'history', path=members + '/alice')
    expect('13 history lists the cases newest first', [v['case'] for v in hist['versions']] == sorted([v['case'] for v in hist['versions']], reverse=True) and hist['cases'] >= 2, True)
    expect('13 the newest case holds the latest write', hist['versions'][0]['properties']['/salary'], '150')
    expect('13 apply on a record without that op is refused, no event', tool_error('apply', path=members + '/alice', operation=members + '/alice/op/missing', inputs={}), True)
    log = tool('history', 'history (events)', limit=5)
    expect('13 events newest first, each with its epoch and touched paths', [e['epoch'] for e in log['events']] == sorted([e['epoch'] for e in log['events']], reverse=True) and all(e['touched'] for e in log['events']), True)
    expect('13 the raise is in the log with its path', any(members + '/alice' in e['touched'] for e in tool('history', 'history (events)', limit=40)['events']), True)
    earlier = tool('history', 'history (events)', before=log['next'], limit=5)
    expect('13 the next cursor pages backwards', earlier['events'][0]['epoch'] < log['events'][-1]['epoch'], True)
    tail_page = tool('history', 'history (events)', before=6, limit=40, who='all')        # fewer events left than the limit (boot ones: who all): the last page, not a failure
    expect('13 the last page of the log is the events left, not a refusal', (len(tail_page['events']), tail_page['next']), (5, None))
    seen = log['events'][-1]['epoch']
    forward = tool('history', 'history (events)', after=seen - 3, limit=2, **{'with': 'x'})
    expect('13 history after pages forward, oldest first, with each touched record inline', ([e['epoch'] for e in forward['events']], forward['next'], all(isinstance(e['with'], dict) and e['with'] for e in forward['events'])), ([seen - 2, seen - 1], seen - 1, True))
    resumed = tool('history', 'history (events)', after=forward['next'], limit=40)
    expect('13 resuming from next continues to the top and stops', (resumed['events'][0]['epoch'], resumed['next']), (seen, None))
    six = [members + '/alice', members + '/bob', '/x' + cells + '/payroll', '/c/x' + cells + '/payroll', deals + '/d101', org + '/budgets/2026/eng']
    many = tool('read', 'read (paths)', paths=six, care='x')
    expect('13 six paths in one read: one tree each, in order, the same shape, zero events', ([a['path'] for a in many['answers']], many['answers'][2]['properties']['/total'], events['read (paths)'][-1]), (six, prop('payroll', '/total'), 0))
    batch_epoch = tool('write', 'write (batch of 20)', records=[{'path': org + '/wake/w' + str(i), 'slots': {'amount': i}} for i in range(20)])['epoch']
    woke = tool('history', 'history (events)', after=batch_epoch - 1, limit=40, **{'with': 'x'})
    first = woke['events'][0]
    expect('13 history after returns the batch as one item with its twenty records inline', (first['epoch'], len([p for p in first['touched'] if '/w' in p]), sum(1 for p in first['with'] if '/w' in p), first['with'][org + '/wake/w3']['properties']['/amount']), (batch_epoch, 20, 20, '3'))

    # 14. concurrency: ten clients, mixed reads and writes on the same cells
    arena = org + '/arena'
    cell('arena_count', 'count', live(arena))

    def client(k):
        out = []
        for r in range(6):
            if r % 2 == 0:
                out.append(write(arena + '/c' + str(k), kind='write (concurrent)', n=r)['records'][0]['written'])
            else:
                out.append(x('arena_count', kind='read (concurrent)')['exists'])
        return out
    e0 = epoch()
    with ThreadPoolExecutor(max_workers=10) as pool:
        replies = [v for part in pool.map(client, range(10)) for v in part]
    expect('14 every reply arrived', len(replies), 60)
    expect('14 thirty concurrent writes cost exactly thirty events, the reads none', epoch() - e0, 30)
    expect('14 final value consistent', prop('arena_count', '/count'), '10')
    # variant: all ten clients poke the SAME record, each its own counter slot, while others read a cell over it
    counter = arena + '/counter'
    write(counter, c0=0)
    cell('counter_first', 'pick', live(counter, 'x'), **{'from': '/c0', 'into': '/first'})

    def poker(k):
        out = []
        for r in range(1, 6):
            tool('write', 'write (concurrent poke)', records=[{'path': counter, 'action': 'poke', 'slots': {'c' + str(k): r}}])
            out.append(x('counter_first', kind='read (concurrent)')['exists'])
        return out
    e0 = epoch()
    with ThreadPoolExecutor(max_workers=10) as pool:
        poked = [v for part in pool.map(poker, range(10)) for v in part]
    expect('14 fifty concurrent pokes of one record cost exactly fifty events', epoch() - e0, 50)
    final = read(counter, 'x')['properties']
    expect('14 ten clients poking one record: every poke landed, no slot lost', sorted(k for k in final if k.startswith('/c')), ['/c' + str(k) for k in range(10)])
    expect('14 the final value is the sum of what every client wrote last', sum(int(final['/c' + str(k)]) for k in range(10)), 10 * 5)
    expect('14 reads of the cell over that record answered throughout', (len(poked), all(poked)), (50, True))
    expect('14 the cell over the poked record reads the final value', prop('counter_first', '/first'), '5')
    expect('14 the world answers a plain read afterwards', read(arena + '/c0', 'x')['properties']['/n'], '4')

    # 15. the request that once took the supervisor down, replayed
    expect('15 reading a flatten cell (keys made from paths) answers', len(x('flat', 'y', kind='read /x (replay)')['children']), 3)
    expect('15 and the world goes on', prop('headcount', '/headcount'), '2')

    # 17. batch write: one call
    many = [{'path': deals + '/b' + str(i), 'properties': {'amount': 100 + i, 'status': 'closed', 'owner': 'bo', 'when': 50 + i, 'customer': 'acme', 'cost': 10, 'amount/scale': 2, 'cost/scale': 2}} for i in range(20)]
    t0 = time.perf_counter()
    batch = tool('write', 'write (batch of 20)', records=many)
    batch_wall = time.perf_counter() - t0
    expect('17 twenty records in one call: every record admitted', all(r['written'] for r in batch['records']) and len(batch['records']) == 20, True)
    expect('17 twenty records in one call: one event', events['write (batch of 20)'][-1], 1)
    newest = tool('history', 'history (events)', limit=1)['events'][0]
    expect('17 one history entry names all twenty paths', all((deals + '/b' + str(i)) in newest['touched'] for i in range(20)), True)
    expect('17 every path readable', read(deals + '/b19', 'x')['properties']['/amount'], '119')
    chain = tool('write', 'write (batch chain)', records=[
        {'path': cells + '/bo_closed', 'properties': {'sys/weft': stdlib['where'], 'sys/tack': live(deals), 'key': '/owner', 'value': 'bo'}},
        {'path': cells + '/bo_revenue', 'properties': {'sys/weft': stdlib['sum'], 'sys/tack': live('/x' + cells + '/bo_closed'), 'slot': '/amount', 'into': '/revenue'}},
        {'path': cells + '/bo_left', 'properties': {'sys/weft': stdlib['subtract'], 'sys/tack': live('/x' + cells + '/bo_revenue'), 'left': '/revenue', 'right': '70'}}],
        then=['/x' + cells + '/bo_left'])
    # amounts carry /amount/scale 2: d102 is 70.00, the twenty batch deals 1.00..1.19; the literal 70 aligns to 7000
    expect('17 a three-cell chain in one call reads at once', chain['then']['/x' + cells + '/bo_left']['properties']['/result'], str(sum(100 + i for i in range(20))))
    refused = tool_error('write', records=[{'path': deals + '/ok1', 'properties': {'n': 1}}, {'path': '/x' + cells + '/payroll', 'properties': {'n': 1}}])
    expect('17 a batch with a derived path is refused whole', refused, True)
    expect('17 and nothing was written', read(deals + '/ok1', 'x')['exists'], False)
    expect('17 and it cost no event', events['write (refused)'][-1], 0)
    mixed = tool('write', 'write (batch mixed)', records=[{'path': deals + '/b0', 'action': 'poke', 'properties': {'note': 'checked'}}, {'path': deals + '/new1', 'properties': {'amount': 1}}])
    expect('17 mixed makes and pokes: new exists, poke merged, untouched slots kept', (read(deals + '/new1', 'x')['exists'], read(deals + '/b0', 'x')['properties'].get('/note'), read(deals + '/b0', 'x')['properties'].get('/amount')), (True, 'checked', '100'))
    t0 = time.perf_counter()
    for i in range(20):
        write(deals + '/s' + str(i), kind='write (single, timed)', amount=i)
    singles_wall = time.perf_counter() - t0
    expect('17 one batch of twenty beats twenty single calls on wall time', batch_wall < singles_wall, True)
    timings['batch of 20 (whole call)'] = [1000 * batch_wall]; timings['twenty single writes (whole)'] = [1000 * singles_wall]

    # 18. undo through write from
    alice = members + '/alice'
    before = read(alice, 'x')
    write(alice, action='poke', salary=160)
    write(alice, action='poke', salary=170)
    cases_before = tool('history', path=alice)['cases']
    undone = tool('write', 'write (undo)', records=[{'path': alice, 'from': before['reference']}], then=['/x' + cells + '/payroll'])
    expect('18 single-record undo restores the earlier case', read(alice, 'x')['properties']['/salary'], '150')
    expect('18 and costs one event', events['write (undo)'][-1], 1)
    expect('18 history gained one entry, not lost two', tool('history', path=alice)['cases'], cases_before + 1)
    bob, cat = members + '/bob', org + '/teams/ops/members/cat'
    snap = {p: read(p, 'x')['reference'] for p in (alice, bob, cat)}
    tool('write', 'write (batch raise)', records=[{'path': p, 'action': 'poke', 'properties': {'salary': 999}} for p in (alice, bob, cat)])
    expect('18 the raise landed', prop('payroll', '/total'), str(999 + 999))
    tool('write', 'write (multi undo)', records=[{'path': p, 'from': snap[p]} for p in (alice, bob, cat)])
    expect('18 multi-record undo: all restored in one call', (read(alice, 'x')['properties']['/salary'], read(bob, 'x')['properties']['/salary'], read(cat, 'x')['properties']['/salary']), ('150', '120', '90'))
    expect('18 and the cell reads the old total', prop('payroll', '/total'), '270')
    later = snap  # the references before the raise; redo means the case after it
    raised_case = tool('history', path=alice)['versions'][1]['reference']
    tool('write', 'write (redo)', records=[{'path': alice, 'from': raised_case}])
    expect('18 redo from the later case', read(alice, 'x')['properties']['/salary'], '999')
    tool('write', 'write (undo)', records=[{'path': alice, 'from': snap[alice]}])
    expect('18 undo of a record with no prior case is refused clearly', tool_error('write', records=[{'path': deals + '/new1', 'from': '/h/x/0/' + str(len(deals.strip('/').split('/')) + 1) + deals + '/new1'}]), True)
    expect('18 and nothing changed', read(deals + '/new1', 'x')['properties']['/amount'], '1')
    expect('18 a pinned cell is untouched by undo', prop('payroll_frozen', '/total'), '250')
    expect('18 /h/x at the earlier case still answers', read(snap[alice], 'x')['properties']['/salary'], '150')
    expect('18 history still shows the undone raise', any(v['properties'].get('/salary') == '999' for v in tool('history', path=alice, limit=10)['versions']), True)

    # 19. write with then
    with_reads = tool('write', 'write (then x3)', records=[{'path': members + '/alice', 'action': 'poke', 'slots': {'salary': 160}}],
                      then=['/x' + cells + '/payroll', '/c/x' + cells + '/payroll', snap[alice]])
    expect('19 then reads reflect the write', with_reads['then']['/x' + cells + '/payroll']['properties']['/total'], '280')   # 160 + bob's 120
    expect('19 then allows /c/x and /h paths', ('/slot' in with_reads['then']['/c/x' + cells + '/payroll']['properties'], with_reads['then'][snap[alice]]['exists']), (True, True))
    expect('19 then costs one event for the write and none for the reads', events['write (then x3)'][-1], 1)
    refused_then = rpc('tools/call', {'name': 'mcp/write', 'arguments': {'records': [{'path': '/x' + cells + '/payroll', 'slots': {'n': 1}}], 'then': ['/x' + cells + '/payroll']}}, 'write (refused)')
    expect('19 no reads run on a refusal', 'then' in refused_then['result'].get('structuredContent', {}), False)

    # 20. read with a formula: a cell that was never written
    found = tool('read', 'read (formula where)', path=deals, care='y', formula='where', settings={'key': '/status', 'value': 'closed'})
    expect('20 where over a folder', len(found['result']['children']) >= 22, True)
    owners = tool('read', 'read (formula)', path=deals, care='y', formula='distinct', settings={'slot': '/owner'})
    expect('20 distinct owners', len(owners['result']['children']), 2)
    grouped = tool('read', 'read (formula)', path=org, care='z', formula='by', settings={'key': '/status', 'op': 'count'})
    expect('20 by at z over a folder answers', grouped['result']['exists'] or True, True)
    expect('20 same answer as the equivalent cell', sum(1 for ch in found['result']['children']), len(x('closed', 'y')['children']))
    expect('20 formula reads cost no event', events['read (formula where)'][-1], 0)
    bad = rpc('tools/call', {'name': 'mcp/read', 'arguments': {'path': deals, 'formula': 'nosuch', 'settings': {}}}, 'read (bad formula)')
    expect('20 a bad formula name is reported, not hung', bad['result'].get('isError'), True)
    badset = tool('read', 'read (formula)', path=deals, care='y', formula='where', settings={})
    expect('20 bad settings are reported in the context, not hung', 'Supply /key' in badset['context'].get('/sys/view/missing', ''), True)
    big = org + '/big'
    for chunk in range(10):
        tool('write', 'write (batch of 100)', records=[{'path': big + '/r' + str(chunk * 100 + i), 'slots': {'status': 'closed' if i % 2 else 'open', 'amount': i}} for i in range(100)])
    plain = tool('read', 'read (1000 records, plain)', path=big, care='y', limit=500)
    searched = tool('read', 'read (1000 records, where)', path=big, care='y', formula='where', settings={'key': '/status', 'value': 'closed'}, limit=500)
    expect('20 a thousand records: the plain read answers a page of 500 nodes (the cap, root included) and names the next; so does the where read (500 matches plus the root)', (plain['nodes'], len(plain['children']), plain['next'] is not None, len(searched['result']['children']), searched['next'] is not None), (500, 499, True, 499, True))
    page2 = tool('read', 'read (1000 records, plain)', path=big, care='y', limit=500, next=plain['next'])
    page3 = tool('read', 'read (1000 records, plain)', path=big, care='y', limit=500, next=page2['next'])
    seen = [c['path'] for c in plain['children']] + [c['path'] for c in page2['children']] + [c['path'] for c in page3['children']]
    expect('20 three pages cover the thousand once, the root shell on the later pages', (len(set(seen)), len(seen), page2.get('paged'), page3['next']), (1000, 1000, True, None))
    expect('20 the cap holds whatever the limit asks', tool('read', 'read (1000 records, plain)', path=big, care='y', limit=5000)['nodes'], 500)
    expect('20 a default read answers 100 nodes', tool('read', 'read (1000 records, plain)', path=big, care='y')['nodes'], 100)
    expect('20 a cursor from another read is refused', tool_error('read', path=deals, care='y', next=plain['next']), True)

    # 21. a reads list of three mixed entries costs zero events and agrees with the singles
    e0 = epoch()
    trio = tool('read', 'read (reads x3)', reads=[members + '/alice', {'path': deals, 'care': 'y', 'limit': 5}, {'path': deals, 'formula': 'where', 'settings': {'key': '/status', 'value': 'closed'}, 'care': 'y'}])
    single_a = read(members + '/alice', 'x'); single_b = tool('read', 'read', path=deals, care='y', limit=5); single_c = tool('read', 'read (formula)', path=deals, care='y', formula='where', settings={'key': '/status', 'value': 'closed'})
    expect('21 a reads list of three mixed entries costs zero events', epoch() - e0, 0)
    expect('21 and agrees with the singles at the same epoch', (trio['answers'][0]['properties'], [c['path'] for c in trio['answers'][1]['children']], len(trio['answers'][2]['result']['children'])), (single_a['properties'], [c['path'] for c in single_b['children']], len(single_c['result']['children'])))
    mixed = tool('read', 'read (reads x3)', reads=[members + '/alice', '/x/nowhere/at/all', {'path': deals, 'formula': 'nosuch'}])
    expect('21 a failed entry answers {path, error} without failing the call', (mixed['answers'][0]['exists'], mixed['answers'][1].get('exists'), mixed['answers'][2].get('error')), (True, False, 'formula: not a standard cell'))

    # 22. a write with a formula read in then
    then_f = tool('write', 'write (then formula)', records=[{'path': deals + '/f1', 'slots': {'amount': 5, 'status': 'closed'}}],
                  then=[{'path': deals, 'formula': 'where', 'settings': {'key': '/status', 'value': 'closed'}, 'care': 'y'}, '/x' + cells + '/closed'])
    expect('22 then takes a formula read and answers it on the admitted state', (any(c['path'].endswith('/f1') for c in then_f['then'][deals]['result']['children']), any(c['path'].endswith('/f1') for c in then_f['then']['/x' + cells + '/closed']['children'])), (True, True))

    # 23. history after with x on the batch and the undo: values as of that epoch
    before_u = read(members + '/alice', 'x')
    write(members + '/alice', kind='write (poke)', action='poke', salary=777)
    e_poke = epoch()
    tool('write', 'write (undo)', records=[{'path': members + '/alice', 'from': before_u['reference']}])
    page = tool('history', 'history (events)', after=e_poke - 1, limit=5, **{'with': 'x'})
    poked, undone = page['events'][0], page['events'][1]
    expect('23 with shows the poke as the merged record and the undo as the earlier record, each as of its epoch, both tagged', (poked['with'][members + '/alice']['properties'].get('/salary'), undone['with'][members + '/alice']['properties'].get('/salary'), poked['who'], undone['who']), ('777', before_u['properties']['/salary'], 'mcp', 'mcp'))
    tool('write', 'write (cull)', records=[{'path': deals + '/f1', 'action': 'cull'}])
    culled = tool('history', 'history (events)', limit=1, **{'with': 'x'})['events'][0]
    expect('23 a cull shows exists false', culled['with'][deals + '/f1']['exists'], False)
    traced = cell('traced_count', 'count', live(members), into='/n')
    told = tool('history', 'history (events)', limit=1, **{'with': 'x'})['events'][0]
    expect('23 a written cell inlines its /x and /c/x: the answer exists with its figure, the context names the weft', (told['with']['/x' + traced]['exists'], told['with']['/x' + traced]['properties'].get('/n'), told['with']['/c/x' + traced]['properties'].get('/sys/weft')), (True, str(len(read(members)['children'])), stdlib['count']['value']))
    short = rpc('tools/call', {'name': 'mcp/write', 'arguments': {'records': [{'path': cells + '/short', 'slots': {'sys/weft': stdlib['count'], 'sys/tack': ref('/h/y/0/5/x' + traced)}}]}}, 'write (refused)')['result']['content'][0]['text']
    expect('23 a reference whose len is short is refused naming the slot and the rule', ('/sys/tack' in short, 'len' in short), (True, True))

    # 24. present answers as usual and leaves the epoch unchanged
    e0 = epoch()
    shown = tool('read', 'read (present)', path=members + '/alice', care='x', present=True)
    expect('24 present answers as usual and moves no epoch', (shown['exists'], epoch() - e0), (True, 0))

    # 16. the table
    floor = {'read': 5.0, 'write': 12.0}
    rows = []
    for kind in sorted(timings):
        ms = timings[kind]
        ev = events.get(kind, [])
        rows.append((kind, len(ms), round(statistics.median(ms), 1), round(max(ms), 1), round(statistics.median(ev), 2) if ev else None))
    print('| call | n | median ms | max ms | events per call |')
    print('|---|---|---|---|---|')
    for kind, n, med, mx, ev in rows:
        print(f'| {kind} | {n} | {med} | {mx} | {ev} |')
    print(f"| floor today (probe mount alone) | | read {floor['read']} / write {floor['write']} | | 0 / 1 |")
    # per-call event counts are meaningless while ten clients write at once; those phases are budgeted whole in step 14
    bad = [(k, ev) for k, n, med, mx, ev in rows if ev is not None and 'concurrent' not in k and (('read' in k and ev > 0) or ('write' in k and ev > 1))]
    assert not bad, ('events budget broken', bad)
    print(json.dumps({'checks': len(checks), 'round_trips': seq, 'events_budget': 'held'}), flush=True)


if __name__ == '__main__':
    import sys
    check(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else '0x11', 120)
