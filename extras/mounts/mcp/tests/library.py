"""Every standard cell, driven through MCP the way an agent would.

Usage: python3 -I -c "import runpy; runpy.run_path('extras/mounts/mcp/tests/library.py')['check']('http://127.0.0.1:8300', '0x11', 120)"
Writes a small dataset under /<node>/user/demo, makes one cell per formula, reads /x and /c/x,
and checks the values, the error paths, pinning and amend with a real case stamp.
"""
import json
import urllib.request


def check(base, node, timeout):
    seq = 0

    def rpc(method, params):
        nonlocal seq
        seq += 1
        body = json.dumps(dict(jsonrpc='2.0', id=seq, method=method, params=params)).encode()
        req = urllib.request.Request(base + '/mcp', body, {'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.load(response)

    def tool(name, **arguments):
        reply = rpc('tools/call', {'name': 'mcp/' + name, 'arguments': arguments})
        assert 'error' not in reply, reply
        result = reply['result']
        assert not result.get('isError'), result
        return result['structuredContent']

    def write(path, **props):
        return tool('write', path=path, properties=props)

    def read(path, care='y'):
        return tool('read', path=path, care=care)

    def live(path):
        return {'type': 'reference', 'value': '/h/y/0/' + str(len(path.strip('/').split('/'))) + path}

    def pinned_x(path):
        return {'type': 'reference', 'value': read(path, 'x')['reference']}

    stdlib = {c['path'].rsplit('/', 1)[1]: {'type': 'reference', 'value': c['reference']}
              for c in read('/' + node + '/weft/stdlib')['children']}
    assert len(stdlib) == 34, sorted(stdlib)

    home = '/' + node + '/user/demo'
    deals = home + '/deals'
    # a rerun on the same world starts clean: cull the home, then revive it with everything beneath it in one event
    try:
        tool('write', records=[{'path': home, 'action': 'cull'}])
    except AssertionError:
        pass
    seed = [(home, {'title': 'demo'})]
    def put(path, **slots):
        seed.append((path, slots))
    put(deals, title='Deals')     # cases belong to records: the folder's record is what a cell's stamp tracks
    for key, amount, status, when, owner in [('d1', 50, 'closed', 10, 'ann'), ('d2', 70, 'open', 20, 'bo'), ('d3', 25, 'closed', 30, 'ann')]:
        put(deals + '/' + key, amount=amount, status=status, when=when, owner=owner)
    put(home + '/prices/p1', sku='a', price=5)
    put(home + '/prices/p2', sku='b', price=7)
    put(home + '/items/i1', sku='a', qty=2)
    put(home + '/items/i2', sku='b', qty=3)
    put(home + '/money/m1', amount=1250, scale=2)
    put(home + '/money/m2', amount=75, scale=1)
    put(home + '/flags/f1', ok=True)
    put(home + '/flags/f2', ok=False)
    put(home + '/extra/e1', amount=1)
    put(home + '/budget', amount=300)
    tool('write', records=[{'path': p, 'slots': v} for p, v in seed])

    cells = home + '/cells'

    def cell(name, formula, tack, **params):
        props = {'sys/weft': stdlib[formula], 'sys/tack': tack}
        props.update(params)
        write(cells + '/' + name, **props)
        return cells + '/' + name

    def x(name, care='x'):
        return read('/x' + cells + '/' + name, care)

    def c(name):
        return read('/c/x' + cells + '/' + name, 'x')['properties']

    def prop(name, slot, care='x'):
        return x(name, care)['properties'].get(slot)

    def child(name, key):
        for ch in x(name, 'y')['children']:
            if ch['path'].rsplit('/', 1)[1] == key:
                return ch['properties']
        return None

    def kids(name):
        return len(x(name, 'y')['children'])

    results = {}

    def expect(label, got, want):
        results[label] = (got, want)
        assert got == want, (label, got, want)

    cell('count', 'count', live(deals))
    expect('count', prop('count', '/count'), '3')
    cell('revenue', 'sum', live(deals), slot='/amount', into='/revenue')
    expect('sum', prop('revenue', '/revenue'), '145')
    cell('min', 'min', live(deals), slot='/amount');            expect('min', prop('min', '/min'), '25')
    cell('max', 'max', live(deals), slot='/amount');            expect('max', prop('max', '/max'), '70')
    cell('avg', 'avg', live(deals), slot='/amount');            expect('avg', prop('avg', '/avg'), '48')
    cell('any', 'any', live(home + '/flags'), slot='/ok');      expect('any', prop('any', '/any'), 'true')
    cell('all', 'all', live(home + '/flags'), slot='/ok');      expect('all', prop('all', '/all'), 'false')
    cell('closed', 'where', live(deals), key='/status', value='closed');          expect('where', kids('closed'), 2)
    cell('big', 'where', live(deals), key='/amount', op='over', value='40');      expect('where over', kids('big'), 2)
    cell('anns', 'where', live(deals), key='/owner', op='contains', value='n');   expect('where contains', kids('anns'), 2)
    cell('sorted', 'sort', live(deals), slot='/amount');        expect('sort', child('sorted', '1')['/key'], 'd3')
    cell('top2', 'top', live(deals), slot='/amount', count=2);  expect('top', (kids('top2'), child('top2', '1')['/key']), (2, 'd2'))
    cell('last', 'latest', live(deals), slot='/when');          expect('latest', prop('last', '/key'), 'd3')
    cell('first', 'earliest', live(deals), slot='/when');       expect('earliest', prop('first', '/key'), 'd1')
    cell('doubled', 'each', live(deals), left='/amount', op='multiply', right='2', into='/double')
    expect('each', child('doubled', 'd1')['/double'], '100')
    cell('priced', 'lookup', live(home + '/items'), key='/sku', take='/price', table=live(home + '/prices'))
    expect('lookup', child('priced', 'i2')['/price'], '7')
    cell('statuses', 'distinct', live(deals), slot='/status');  expect('distinct', kids('statuses'), 2)
    cell('amounts', 'select', live(deals), slots='/amount');    expect('select', sorted(child('amounts', 'd1')), ['/amount'])
    cell('bystatus', 'by', live(deals), key='/status', op='sum', slot='/amount')
    expect('by', child('bystatus', 'closed')['/sum'], '75')
    cell('gridded', 'grid', live(deals), row='/status', col='/owner')
    expect('grid', child('gridded', 'closed')['/ann'], '2')
    cell('flat', 'flatten', live(deals));                       expect('flatten', kids('flat'), 3)
    cell('merged', 'merge', live(deals), extra=live(home + '/extra')); expect('merge', kids('merged'), 4)
    cell('closed_revenue', 'sum', live('/x' + cells + '/closed'), slot='/amount', into='/revenue')
    expect('cell of a cell', prop('closed_revenue', '/revenue'), '75')
    cell('twice', 'multiply', live('/x' + cells + '/closed_revenue'), left='2', right='/revenue')
    expect('multiply', prop('twice', '/result'), '150')
    cell('quarter', 'divide', live('/x' + cells + '/closed_revenue'), left='300', right='/revenue')
    expect('divide', prop('quarter', '/result'), '4')
    cell('left', 'subtract', live('/x' + cells + '/closed_revenue'), budget=pinned_x(home + '/budget'),
         left='/views/budget/amount', right='/revenue')
    expect('subtract with a secondary input', prop('left', '/result'), '225')
    cell('added', 'add', live('/x' + cells + '/closed_revenue'), left='/revenue', right='0.5')
    expect('add with a decimal literal', (prop('added', '/result'), prop('added', '/scale')), ('755', '1'))
    write(cells + '/picked', **{'sys/weft': stdlib['pick'], 'sys/tack': live('/x' + cells + '/closed_revenue'),
                                'budget': pinned_x(home + '/budget'), 'from': '/views/budget/amount', 'into': '/budget'})
    expect('pick', prop('picked', '/budget'), '300')
    cell('noted', 'put', live('/x' + cells + '/closed_revenue'), into='/note', value='hello')
    expect('put', prop('noted', '/note'), 'hello')
    cell('cash', 'sum', live(home + '/money'), slot='/amount')
    expect('decimal sum', (prop('cash', '/total'), prop('cash', '/scale')), ('2000', '2'))
    cell('meancash', 'avg', live(home + '/money'), slot='/amount')
    expect('decimal avg', prop('meancash', '/avg'), '1000')
    cell('rounded', 'round', live('/x' + cells + '/cash'), slot='/total', places=1)
    expect('round', (prop('rounded', '/total'), prop('rounded', '/scale')), ('200', '1'))
    cell('age', 'since', live('/x' + cells + '/last'), slot='/when', **{'from': '10'})
    expect('since', prop('age', '/since'), '20')
    cell('mid', 'between', live(deals), slot='/when', **{'from': '15', 'to': '35'})
    expect('between', kids('mid'), 2)

    # Error paths read, in the context.
    cell('hole', 'sum', live(deals))
    expect('missing parameter passes the input through', kids('hole'), 3)
    assert 'Supply /slot' in c('hole')['/sys/view/missing'], c('hole')
    cell('loop', 'count', live(cells))
    expect('cycle reads unknown', x('loop')['exists'], False)
    assert c('loop')['/sys/view/fault'].startswith('cycle'), c('loop')

    # Live versus pinned: a frozen copy keeps its answer after a write.
    write(deals + '/d4', amount=10, status='closed', when=40, owner='bo')
    expect('live cell follows a write', prop('count', '/count'), '4')
    expect('chain follows a write', prop('closed_revenue', '/revenue'), '85')
    pinned = read('/x' + cells + '/count', 'x')['reference']
    expect('a pinned read of a live cell reads unknown', read(pinned, 'x')['exists'], False)

    # amend: a note stamped with the input's current case, and a stale one.
    stamp = int(read('/c/x' + cells + '/closed_revenue', 'x')['properties']['/sys/tack/case'])
    write(cells + '/notes/n1', slot='/revenue', value=80, case=stamp)
    write(cells + '/notes/n2', slot='/extra', value='x', case=0)
    cell('amended', 'amend', live('/x' + cells + '/closed_revenue'), notes=live(cells + '/notes'))
    expect('amend lays the note over the answer', prop('amended', '/revenue'), '80')
    ctx = c('amended')
    expect('a note at the current case is quiet', '/sys/view/note/n1' in ctx, False)
    expect('a stale note is reported', ctx.get('/sys/view/note/n2', '').startswith('note at case 0'), True)
    expect('amended counts the notes', ctx.get('/sys/view/amended'), '2')
    expect('history has the cases', tool('history', path=deals + '/d1')['cases'] >= 1, True)

    print(json.dumps({'checks': len(results), 'formulas': len(stdlib), 'round_trips': seq}), flush=True)


if __name__ == '__main__':
    import sys
    check(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else '0x11', 120)
