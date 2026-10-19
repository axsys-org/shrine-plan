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
    assert len(stdlib) == 68, sorted(stdlib)

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

    # signed and decimal numbers: a difference below zero, a negative slot summed, a decimal written and shown back
    cell('owed', 'subtract', live(home + '/budget'), left='/amount', right='400')
    expect('subtract below zero gives a signed figure', prop('owed', '/result'), '-100')
    write(home + '/dec/d1', amount=4.5)
    write(home + '/dec/d2', amount=-1.25)
    expect('a decimal reads back as it was written, with its scale beside it', (read(home + '/dec/d1', 'x')['properties'].get('/amount'), read(home + '/dec/d1', 'x')['properties'].get('/amount/scale')), ('4.5', '1'))
    expect('a negative decimal too', read(home + '/dec/d2', 'x')['properties'].get('/amount'), '-1.25')
    cell('decsum', 'sum', live(home + '/dec'), slot='/amount')
    expect('a sum over decimals and a negative aligns the scales and keeps the sign', (prop('decsum', '/total'), prop('decsum', '/scale')), ('325', '2'))
    cell('decmin', 'min', live(home + '/dec'), slot='/amount')
    expect('min finds the negative', prop('decmin', '/min'), '-125')
    # text: join, match, split, date, each the shape of each or where
    write(home + '/people/p1', first='Ann', last='Lee', tags='red-blue', born='1990-04-07')
    write(home + '/people/p2', first='Bo', last='Ng', tags='green', born='1985-12-30')
    cell('named', 'join', live(home + '/people'), slots='/first /last', into='/full')
    expect('join concatenates slots with a space into a new slot', [c['properties'].get('/full') for c in x('named', 'y')['children']], ['Ann Lee', 'Bo Ng'])
    cell('named_dash', 'join', live(home + '/people'), slots='/last /first', into='/full', **{'with': ', '})
    expect('join takes its separator from /with', x('named_dash', 'y')['children'][0]['properties'].get('/full'), 'Lee, Ann')
    cell('starts_b', 'match', live(home + '/people'), key='/first', value='B', op='starts')
    expect('match keeps the rows whose slot starts with the text', [c['path'].rsplit('/', 1)[1] for c in x('starts_b', 'y')['children']], ['p2'])
    cell('has_e', 'match', live(home + '/people'), key='/last', value='e')
    expect('match defaults to contains', [c['path'].rsplit('/', 1)[1] for c in x('has_e', 'y')['children']], ['p1'])
    cell('tagged', 'split', live(home + '/people'), slot='/tags', **{'with': '-'}, into='/tag')
    expect('split lands the parts at /into/1, /into/2', (x('tagged', 'y')['children'][0]['properties'].get('/tag/1'), x('tagged', 'y')['children'][0]['properties'].get('/tag/2'), x('tagged', 'y')['children'][1]['properties'].get('/tag/2')), ('red', 'blue', None))
    cell('bornday', 'date', live(home + '/people'), slot='/born', into='/day')
    expect('date turns a text date into a natural YYYYMMDD that sorts', [c['properties'].get('/day') for c in x('bornday', 'y')['children']], ['19900407', '19851230'])
    cell('eldest', 'earliest', live('/x' + cells + '/bornday'), slot='/day')
    expect('and a ranking over it works', x('eldest', 'x')['properties'].get('/key'), 'p2')
    # gather: each secondary input nested whole under its slot name
    cell('gathered', 'gather', live(deals), extra=live(home + '/extra'))
    expect('gather nests the view as one more child', kids('gathered'), len(read(deals)['children']) + 1)
    gz = x('gathered', 'z')
    nested = next(c for c in gz['children'] if c['path'].endswith('/extra'))
    expect('gather keeps the view\'s rows under its name', [k['path'].rsplit('/', 1)[1] for k in nested['children']], ['e1'])
    # diff: the roots compare too, as a /root row under changed, hand computed here from the two root records
    cell('rootdiff', 'diff', live(deals), other=live(home + '/extra'))
    deals_root, extra_root = read(deals, 'x')['properties'], read(home + '/extra', 'x')['properties']
    want_root = {} if deals_root == extra_root else {k + '/to': v for k, v in deals_root.items() if extra_root.get(k) != v} | {k + '/from': v for k, v in extra_root.items() if deals_root.get(k) != v}
    expect('diff counts the rows only one side has, and the roots as one changed row', (prop('rootdiff', '/added'), prop('rootdiff', '/removed'), prop('rootdiff', '/changed')), (str(len(read(deals)['children'])), '1', '1' if want_root else '0'))
    if want_root:
        dz = x('rootdiff', 'z')
        changed = next(c for c in dz['children'] if c['path'].endswith('/changed'))
        root_row = next(c for c in changed['children'] if c['path'].endswith('/root'))
        expect('and the root row carries each differing slot as from and to', root_row['properties'], want_root)
    # the extensions: conditional, dates, cross-row, text, references, statistics, grouping, shape, checks
    def rowprop(name, key, slot):
        ch = child(name, key)
        return None if ch is None else ch.get(slot)
    cell('flagged', 'when', live(deals), key='/status', value='closed', then='yes', into='/flag', **{'else': 'no'})
    expect('when: then on a match, else otherwise', (rowprop('flagged', 'd1', '/flag'), rowprop('flagged', 'd2', '/flag')), ('yes', 'no'))
    cell('defaulted', 'coalesce', live(deals), slot='/note', value='none')
    expect('coalesce fills a missing slot', rowprop('defaulted', 'd2', '/note'), 'none')
    write(home + '/days/x1', day=20260407)
    write(home + '/days/x2', day='2025-12-31')
    cell('weekdays', 'part', live(home + '/days'), slot='/day', unit='weekday')
    expect('part: weekday from a day number and from a text date', (rowprop('weekdays', 'x1', '/weekday'), rowprop('weekdays', 'x2', '/weekday')), ('2', '3'))
    cell('shifted', 'shift', live(home + '/days'), slot='/day', by='-7')
    expect('shift: a week back crosses a month', rowprop('shifted', 'x1', '/day'), '20260331')
    cell('monthed', 'shift', live(home + '/days'), slot='/day', by='2', unit='month', into='/later')
    expect('shift by months clamps the day', rowprop('monthed', 'x2', '/later'), '20260228')
    cell('totals', 'running', live(deals), slot='/amount')
    expect('running total in row order', rowprop('totals', 'd3', '/running'), '145')
    cell('ranks', 'rank', live(deals))
    expect('rank is the position', rowprop('ranks', 'd3', '/rank'), '3')
    cell('changes', 'change', live(deals), slot='/amount')
    expect('change from the previous row, signed', (rowprop('changes', 'd1', '/change'), rowprop('changes', 'd2', '/change'), rowprop('changes', 'd3', '/change')), (None, '20', '-45'))
    cell('moved', 'moving', live(deals), slot='/amount', window=2)
    expect('moving mean over the last two, half up', rowprop('moved', 'd3', '/moving'), '48')
    cell('shares', 'percent', live(deals), slot='/amount')
    expect('percent as a share of the total, two places (50 of 155)', rowprop('shares', 'd1', '/percent'), '32.26')
    cell('decrunning', 'running', live(home + '/dec'), slot='/amount')
    expect('a derived number keeps the slot scale: 4.5 then 4.5 - 1.25', (rowprop('decrunning', 'd1', '/running'), rowprop('decrunning', 'd2', '/running')), ('4.50', '3.25'))
    write(home + '/txt/t1', s='  Ann  ', u='ab-cd-ab')
    cell('trimmed', 'trim', live(home + '/txt'), slot='/s');                       expect('trim', rowprop('trimmed', 't1', '/s'), 'Ann')
    cell('upper', 'case', live(home + '/txt'), slot='/s', to='upper');            expect('case upper', rowprop('upper', 't1', '/s'), '  ANN  ')
    cell('replaced', 'replace', live(home + '/txt'), slot='/u', find='ab', **{'with': 'x'}); expect('replace every occurrence', rowprop('replaced', 't1', '/u'), 'x-cd-x')
    cell('lengths', 'length', live(home + '/txt'), slot='/u');                     expect('length in bytes', rowprop('lengths', 't1', '/length'), '8')
    cell('starting', 'starts', live(home + '/txt'), slot='/u', value='ab');        expect('starts', rowprop('starting', 't1', '/starts'), 'true')
    cell('ending', 'ends', live(home + '/txt'), slot='/u', value='cd');            expect('ends', rowprop('ending', 't1', '/ends'), 'false')
    cell('refd', 'reference', live(home + '/items'), key='/sku', table=live(home + '/prices'), into='/price_ref')
    expect('reference points at the table row', rowprop('refd', 'i2', '/price_ref'), '/h/x/0/' + str(len((home + '/prices/p2').strip('/').split('/'))) + home + '/prices/p2')
    cell('followed', 'follow', live('/x' + cells + '/refd'), slot='/price_ref', prices=live(home + '/prices'))
    expect('follow brings the pointed record under the slot', rowprop('followed', 'i2', '/price_ref/price'), '7')
    cell('middle', 'median', live(deals), slot='/amount');                        expect('median of 10, 25, 50, 70: the mean of the middles, half up', prop('middle', '/median'), '38')
    cell('topmost', 'percentile', live(deals), slot='/amount', at=100);           expect('percentile 100 is the largest', prop('topmost', '/percentile'), '70')
    cell('spread', 'variance', live(deals), slot='/amount');                      expect('variance of 10, 25, 50, 70', prop('spread', '/variance'), '530')
    cell('dev', 'stddev', live(deals), slot='/amount');                           expect('stddev of 10, 25, 50, 70', prop('dev', '/stddev'), '23')
    cell('common', 'mode', live(deals), slot='/status');                          expect('mode', prop('common', '/mode'), 'closed')
    expect('distinct counts its values on the root', prop('statuses', '/count'), '2')
    cell('bytwo', 'by', live(deals), key='/status /owner')
    expect('by two keys', rowprop('bytwo', 'closed_ann', '/count'), '2')
    write(home + '/ties/a', g=1, v=5)
    write(home + '/ties/b', g=1, v=3)
    write(home + '/ties/c', g=0, v=9)
    cell('sort2', 'sort', live(home + '/ties'), slot='/g /v')
    expect('sort by two slots breaks ties by the second', [c['properties'].get('/key') for c in x('sort2', 'y')['children']], ['c', 'b', 'a'])
    cell('grouped', 'group', live(deals), key='/status')
    expect('group keeps the rows under their value', sorted(c['path'].rsplit('/', 1)[1] for c in next(c for c in x('grouped', 'z')['children'] if c['path'].endswith('/closed'))['children']), ['d1', 'd3', 'd4'])
    cell('renamed', 'rename', live(deals), **{'from': '/amount', 'to': '/value'})
    expect('rename', (rowprop('renamed', 'd1', '/value'), rowprop('renamed', 'd1', '/amount')), ('50', None))
    cell('dropped', 'drop', live(deals), slots='/amount /status')
    expect('drop', sorted(child('dropped', 'd1')), ['/owner', '/when'])
    write(home + '/flatkeys/a_x', n=1)
    write(home + '/flatkeys/b', n=2)
    cell('deepened', 'unflatten', live(home + '/flatkeys'))
    expect('unflatten', [c['path'].rsplit('/', 1)[1] for c in x('deepened', 'z')['children']], ['a', 'b'])
    cell('exploded', 'explode', live(home + '/txt'), slot='/u', **{'with': '-'})
    expect('explode: the pieces as rows 1, 2, 3 under the row', [(c['path'].rsplit('/', 1)[1], c['properties'].get('/u')) for c in next(c for c in x('exploded', 'z')['children'] if c['path'].endswith('/t1'))['children']], [('1', 'ab'), ('2', 'cd'), ('3', 'ab')])
    cell('invalid', 'validate', live(deals), key='/amount', op='over', value='40')
    expect('validate keeps the failing rows with the rule as the reason', [(c['path'].rsplit('/', 1)[1], c['properties'].get('/reason')) for c in x('invalid', 'y')['children']], [('d3', '/amount is not over 40'), ('d4', '/amount is not over 40')])
    cell('dupes', 'unique', live(deals), key='/owner')
    expect('unique keeps the repeated rows with their count', [(c['path'].rsplit('/', 1)[1], c['properties'].get('/count')) for c in x('dupes', 'y')['children']], [('d1', '2'), ('d2', '2'), ('d3', '2'), ('d4', '2')])
    # expressions: a rule a chain cannot say, in a slot
    cell('x_arith', 'each', live(deals), expr='amount * 2 + 1', into='/v')
    expect('expr: arithmetic with precedence', rowprop('x_arith', 'd1', '/v'), '101')
    cell('x_where', 'where', live(deals), expr="status = 'closed' and amount > 30")
    expect('expr: a boolean rule keeps the rows it is true for', [c['path'].rsplit('/', 1)[1] for c in x('x_where', 'y')['children']], ['d1'])
    cell('x_when', 'when', live(deals), expr='amount >= 50', then='big', into='/size', **{'else': 'small'})
    expect('expr: when', (rowprop('x_when', 'd1', '/size'), rowprop('x_when', 'd4', '/size')), ('big', 'small'))
    cell('x_validate', 'validate', live(deals), expr='amount > 40')
    expect('expr: validate names the rule as the reason', [(c['path'].rsplit('/', 1)[1], c['properties'].get('/reason')) for c in x('x_validate', 'y')['children']], [('d3', 'amount > 40'), ('d4', 'amount > 40')])
    cell('x_scale', 'each', live(home + '/money'), expr='amount + 1', into='/v')
    expect('expr: a scaled slot keeps its scale', rowprop('x_scale', 'm1', '/v'), '13.50')
    cell('x_text', 'each', live(home + '/people'), expr="upper(first) + ' ' + last", into='/full')
    expect('expr: a text plus a text faults, text is joined with join', '/sys/view/fault' in c('x_text'), True)
    cell('x_fn', 'each', live(home + '/people'), expr='len(trim(first))', into='/n')
    expect('expr: functions compose', rowprop('x_fn', 'p1', '/n'), '3')
    cell('x_bad', 'where', live(deals), expr='amount +')
    expect('expr: a bad expression is one fault with its position', c('x_bad').get('/sys/view/fault', '').endswith('at 8'), True)
    cell('x_hole', 'where', live(home + '/people'), expr="tags = 'green'")
    write(home + '/people/p3', first='Cy')
    expect('expr: a missing slot is a hole on that row, the row dropped by where', ([c['path'].rsplit('/', 1)[1] for c in x('x_hole', 'y')['children']], c('x_hole').get('/sys/view/hole/p3')), (['p2'], 'tags is absent'))
    expect('expr: a formula read takes it', len(tool('read', path=deals, formula='where', settings={'expr': 'amount > 40'})['result']['children']), 2)
    print(json.dumps({'checks': len(results), 'formulas': len(stdlib), 'round_trips': seq}), flush=True)


if __name__ == '__main__':
    import sys
    check(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else '0x11', 120)
