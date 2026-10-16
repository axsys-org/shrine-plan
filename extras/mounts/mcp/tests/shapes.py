"""Cells over every namespace shape at every care, through MCP, asserting whole trees.

Usage: python3 -I -c "import runpy; runpy.run_path('extras/mounts/mcp/tests/shapes.py')['check']('http://127.0.0.1:8300', '0x11', 120)"
Prints a matrix: care x shape x formula -> output shape, pass/fail, events and time per call.
"""
import json
import statistics
import time
import urllib.request


def check(base, node, timeout):
    seq = 0
    rows = []        # (care, shape, formula, output shape, ok, ms, events)
    timings = {}

    def epoch():
        try:
            with urllib.request.urlopen(base + '/probe/read?path=/' + node, timeout=timeout) as r:
                return json.load(r).get('epoch')
        except Exception:
            return None

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

    def write(path, **slots):
        return tool('write', records=[{'path': path, 'slots': slots}])

    def read(path, care='y'):
        return tool('read', path=path, care=care)

    def live(path, care='y'):
        return {'type': 'reference', 'value': '/h/' + care + '/0/' + str(len(path.strip('/').split('/'))) + path}

    def ref(reference):
        return {'type': 'reference', 'value': reference}

    def shape_of(view):
        """The whole tree as {props, kids}: every name, every level, every slot."""
        return {'props': view.get('properties', {}), 'kids': {ch['path'].rsplit('/', 1)[1]: shape_of(ch) for ch in view.get('children', [])}}

    def describe(view):
        depth = 0 if not view['kids'] else 1 + max(describe(k) for k in view['kids'].values())
        return depth

    stdlib = {c['path'].rsplit('/', 1)[1]: ref(c['reference']) for c in read('/' + node + '/weft/stdlib')['children']}
    home = '/' + node + '/user/shapes'
    try:
        tool('write', records=[{'path': home, 'action': 'cull'}])
    except AssertionError:
        pass
    seed = [(home, {'title': 'shapes'})]   # one event revives the culled home with every shape beneath it
    def put(path, **slots):
        seed.append((path, slots))

    # ---- the shapes
    rec, rec2 = home + '/rec', home + '/rec2'
    put(rec2, n=3)
    put(rec, n=7, t='hello', when=12, ok=True)   # the link to rec2 is added after the batch, once rec2 has a reference
    put(rec + '/a1', kind='pdf', size=3)      # attachments: children of a record
    put(rec + '/a2', kind='txt', size=1)
    lst = home + '/list'
    put(lst, title='list')
    for k, n, t in [('1', 10, 'a'), ('2', 20, 'b'), ('3', 30, 'a')]:
        put(lst + '/' + k, n=n, t=t)
    mp = home + '/map'
    put(mp, title='map')
    put(mp + '/acme', n=5, region='west')
    put(mp + '/zed', n=8, region='east')
    mixed = home + '/mixed'
    put(mixed + '/a', n=1, t='x')
    put(mixed + '/b', t='y', ok=True)
    put(mixed + '/c', n=3)
    tree = home + '/tree'
    put(tree, n=100)
    put(tree + '/a', n=1)
    put(tree + '/a/x', n=2)
    put(tree + '/a/x/deep', n=3, t='leaf')
    put(tree + '/b', n=4)
    put(tree + '/b/y', t='only')
    put(tree + '/empty', title='empty')
    put(home + '/codes/a', code='a', region='west')
    st = home + '/set'                           # a set: named members, no slots
    for k in ('alpha', 'beta', 'gamma'):
        put(st + '/' + k)
    tbl = home + '/table'                        # a table: uniform columns
    for k, region, status, amount in [('r1', 'west', 'open', 5), ('r2', 'west', 'closed', 7), ('r3', 'east', 'open', 2), ('r4', 'east', 'open', 4)]:
        put(tbl + '/' + k, region=region, status=status, amount=amount)
    bag = home + '/bag'                          # a bag: repeated values
    for k in ('1', '2', '3'):
        put(bag + '/' + k, t='a')
    grouped = home + '/grouped'                  # grouped data: records only at the leaves
    put(grouped + '/west/acme', n=5)
    put(grouped + '/west/zed', n=1)
    put(grouped + '/east/bob', n=2)
    matrix = home + '/matrix'                    # a matrix: row folders, column records
    for r in ('r1', 'r2'):
        for c in ('c1', 'c2'):
            put(matrix + '/' + r + '/' + c, r=r, c=c, v=(1 if r == 'r1' else 3) + (0 if c == 'c1' else 1))
    uneven = home + '/uneven'                    # uneven branches, folders without records
    put(uneven + '/hollow/leaf', n=1)
    put(uneven + '/top', n=2)
    put(uneven + '/top/mid/low', n=3)
    hier = home + '/hier'                        # a hierarchy with a value at every level
    put(hier, n=1)
    put(hier + '/d1', n=2)
    put(hier + '/d1/d2', n=4)
    put(hier + '/d1/d2/d3', n=8)
    put(hier + '/e', n=16)
    for k in ('1', '3', '9'):
        put(home + '/picked/' + k)
    tool('write', records=[{'path': p, 'slots': v} for p, v in seed])
    write(rec, n=7, t='hello', when=12, ok=True, link=ref(read(rec2, 'x')['reference']))
    cells = home + '/cells'
    n_cell = [0]

    def cell(formula, tack, care, **params):
        n_cell[0] += 1
        name = 'c' + str(n_cell[0])
        props = {'sys/weft': stdlib[formula], 'sys/tack': tack if isinstance(tack, dict) else live(tack, care)}
        props.update(params)
        write(cells + '/' + name, **props)
        return cells + '/' + name

    leaked = []     # (3) the invariant: no sys/view slot ever appears in a /x answer

    def sys_slots(view):
        return [k for k in view.get('properties', {}) if k.startswith('/sys/view')] + [k for ch in view.get('children', []) for k in sys_slots(ch)]

    def run(care, shape, formula, tack, expected, read_care='z', **params):
        """Make the cell, read /x at z (the whole output), compare the whole tree."""
        path = cell(formula, tack, care, **params)
        e0 = epoch(); samples = []
        for _ in range(3):          # three reads, the median: a lone runtime pause of hundreds of ms is not the formula's cost
            t0 = time.perf_counter()
            view = read('/x' + path, read_care)
            samples.append(1000 * (time.perf_counter() - t0))
        ms = statistics.median(samples); e1 = epoch()
        leaked.extend((formula, shape, k) for k in sys_slots(view))
        got = shape_of(view)
        ok = got == expected
        rows.append((care, shape, formula, 'depth ' + str(describe(got)), ok, round(ms, 1), (e1 - e0) if e0 is not None and e1 is not None else None))
        if not ok:
            print('MISMATCH', care, shape, formula, '\n got     ', json.dumps(got, sort_keys=True), '\n expected', json.dumps(expected, sort_keys=True))
        return path, got

    def t(props, kids=None):
        return {'props': props, 'kids': kids or {}}

    def fig(slot, n, s='0'):
        return t({slot: str(n), '/scale': s})

    # ---- reduce over y (list) and z (tree; interior records reached)
    L = {'1': t({'/n': '10', '/t': 'a'}), '2': t({'/n': '20', '/t': 'b'}), '3': t({'/n': '30', '/t': 'a'})}
    run('y', 'list', 'count', lst, t({'/count': '3'}))
    run('y', 'list', 'sum', lst, fig('/total', 60), slot='/n')
    run('y', 'list', 'min', lst, fig('/min', 10), slot='/n')
    run('y', 'list', 'max', lst, fig('/max', 30), slot='/n')
    run('y', 'list', 'avg', lst, fig('/avg', 20), slot='/n')
    run('y', 'mixed', 'any', mixed, t({'/any': 'true'}), slot='/ok')
    run('y', 'mixed', 'all', mixed, t({'/all': 'false'}), slot='/ok')
    run('z', 'tree', 'count', tree, t({'/count': '6'}))                       # a, a/x, a/x/deep, b, b/y, empty
    run('z', 'tree', 'sum', tree, fig('/total', 10), slot='/n')               # 1+2+3+4: interior records reached
    run('z', 'tree', 'min', tree, fig('/min', 1), slot='/n')
    run('z', 'tree', 'max', tree, fig('/max', 4), slot='/n')
    run('z', 'tree', 'avg', tree, fig('/avg', 3), slot='/n')                  # 10/4 = 2.5 -> 3 half up
    run('z', 'tree', 'any', tree, t({'/any': 'true'}), slot='/n')
    run('z', 'tree', 'all', tree, t({'/all': 'false'}), slot='/n')           # b/y and empty have no /n

    # ---- rows over y, and over z with flatten in front
    TREE_ROOT = {'/n': '100'}
    run('y', 'list', 'where', lst, t({'/title': 'list'}, {'1': L['1'], '3': L['3']}), key='/t', value='a')
    run('y', 'map', 'where', mp, t({'/title': 'map'}, {'zed': t({'/n': '8', '/region': 'east'})}), key='/n', op='over', value='6')
    run('y', 'list', 'sort', lst, t({'/title': 'list'}, {'1': t({'/n': '30', '/t': 'a', '/key': '3'}), '2': t({'/n': '20', '/t': 'b', '/key': '2'}), '3': t({'/n': '10', '/t': 'a', '/key': '1'})}), slot='/n', order='desc')
    run('y', 'list', 'top', lst, t({'/title': 'list'}, {'1': t({'/n': '30', '/t': 'a', '/key': '3'})}), slot='/n', count=1)
    run('y', 'list', 'latest', lst, t({'/n': '30', '/t': 'a', '/key': '3'}), slot='/n')
    run('y', 'list', 'earliest', lst, t({'/n': '10', '/t': 'a', '/key': '1'}), slot='/n')
    run('y', 'list', 'each', lst, t({'/title': 'list'}, {k: t(dict(v['props'], **{'/double': str(2 * int(v['props']['/n'])), '/scale': '0'})) for k, v in L.items()}), left='/n', op='multiply', right='2', into='/double')
    run('y', 'list', 'lookup', lst, t({'/title': 'list'}, {'1': t({'/n': '10', '/t': 'a', '/region': 'west'}), '2': L['2'], '3': t({'/n': '30', '/t': 'a', '/region': 'west'})}),
        key='/t', match='/code', take='/region', into='/region', table=live(home + '/codes'))
    run('y', 'list', 'distinct', lst, t({'/title': 'list'}, {'1': t({'/value': 'a', '/count': '2'}), '2': t({'/value': 'b', '/count': '1'})}), slot='/t')
    run('y', 'mixed', 'select', mixed, t({}, {'a': t({'/n': '1'}), 'b': t({}), 'c': t({'/n': '3'})}), slots='/n')
    flat, flat_got = run('z', 'tree', 'flatten', tree, t(TREE_ROOT, {'a': t({'/n': '1'}), 'a_x': t({'/n': '2'}), 'a_x_deep': t({'/n': '3', '/t': 'leaf'}), 'b': t({'/n': '4'}), 'b_y': t({'/t': 'only'}), 'empty': t({'/title': 'empty'})}))
    run('z', 'tree (flattened)', 'where', '/x' + flat, t(TREE_ROOT, {'a_x_deep': t({'/n': '3', '/t': 'leaf'})}), key='/t', value='leaf')
    run('z', 'tree (flattened)', 'sort', '/x' + flat, t(TREE_ROOT, {'1': t({'/n': '4', '/key': 'b'}), '2': t({'/n': '3', '/t': 'leaf', '/key': 'a_x_deep'}), '3': t({'/n': '2', '/key': 'a_x'}), '4': t({'/n': '1', '/key': 'a'})}), slot='/n', order='desc')
    run('z', 'tree (flattened)', 'top', '/x' + flat, t(TREE_ROOT, {'1': t({'/n': '4', '/key': 'b'}), '2': t({'/n': '3', '/t': 'leaf', '/key': 'a_x_deep'})}), slot='/n', count=2)
    run('z', 'tree (flattened)', 'latest', '/x' + flat, t({'/n': '4', '/key': 'b'}), slot='/n')
    run('z', 'tree', 'sort', tree, t(TREE_ROOT, {'1': t({'/n': '4', '/key': 'b'}), '2': t({'/n': '3', '/t': 'leaf', '/key': '/a/x/deep'}), '3': t({'/n': '2', '/key': '/a/x'}), '4': t({'/n': '1', '/key': 'a'})}), slot='/n', order='desc')
    run('z', 'tree (flattened)', 'distinct', '/x' + flat, t(TREE_ROOT, {'1': t({'/value': 'leaf', '/count': '1'}), '2': t({'/value': 'only', '/count': '1'})}), slot='/t')
    run('z', 'tree', 'where', tree, t(TREE_ROOT, {'a': t({}, {'x': t({}, {'deep': t({'/n': '3', '/t': 'leaf'})})})}), key='/t', value='leaf')
    run('z', 'tree', 'each', tree, t(TREE_ROOT, {'a': t({'/n': '1', '/plus': '2', '/scale': '0'}, {'x': t({'/n': '2', '/plus': '3', '/scale': '0'}, {'deep': t({'/n': '3', '/t': 'leaf', '/plus': '4', '/scale': '0'})})}), 'b': t({'/n': '4', '/plus': '5', '/scale': '0'}, {'y': t({'/t': 'only'})}), 'empty': t({'/title': 'empty'})}), left='/n', op='add', right='1', into='/plus')
    run('z', 'tree', 'select', tree, t({'/n': '100'}, {'a': t({'/n': '1'}, {'x': t({'/n': '2'}, {'deep': t({'/n': '3'})})}), 'b': t({'/n': '4'}, {'y': t({})}), 'empty': t({})}), slots='/n')

    # ---- shape
    run('y', 'list', 'by', lst, t({'/title': 'list'}, {'a': t({'/value': 'a', '/sum': '40', '/scale': '0'}), 'b': t({'/value': 'b', '/sum': '20', '/scale': '0'})}), key='/t', op='sum', slot='/n')
    run('z', 'tree', 'by', tree, t(TREE_ROOT, {'1': t({'/value': '1', '/count': '3', '/scale': '0'}), '2': t({'/value': '2', '/count': '2', '/scale': '0'}), '3': t({'/value': '3', '/count': '1', '/scale': '0'})}), key='depth', op='count')
    run('y', 'map', 'grid', mp, t({'/title': 'map'}, {'west': t({'/5': '1'}), 'east': t({'/8': '1'})}), row='/region', col='/n')
    run('y', 'table', 'grid', tbl, t({}, {'west': t({'/open': '5', '/closed': '7'}), 'east': t({'/open': '6'})}), row='/region', col='/status', op='sum', slot='/amount')
    run('y', 'table', 'by', tbl, t({}, {'open': t({'/value': 'open', '/sum': '11', '/scale': '0'}), 'closed': t({'/value': 'closed', '/sum': '7', '/scale': '0'})}), key='/status', op='sum', slot='/amount')
    run('y', 'bag', 'distinct', bag, t({}, {'1': t({'/value': 'a', '/count': '3'})}), slot='/t')
    run('y', 'bag', 'by', bag, t({}, {'a': t({'/value': 'a', '/count': '3', '/scale': '0'})}), key='/t')
    run('z', 'matrix', 'grid', matrix, t({}, {'r1': t({'/c1': '1', '/c2': '2'}), 'r2': t({'/c1': '3', '/c2': '4'})}), row='/r', col='/c', op='sum', slot='/v')
    run('z', 'matrix', 'by', matrix, t({}, {'r1': t({'/value': 'r1', '/sum': '3', '/scale': '0'}), 'r2': t({'/value': 'r2', '/sum': '7', '/scale': '0'})}), key='/r', op='sum', slot='/v')
    run('z', 'grouped', 'sum', grouped, fig('/total', 8), slot='/n')
    run('z', 'grouped', 'by', grouped, t({}, {'2': t({'/value': '2', '/count': '3', '/scale': '0'})}), key='depth')
    run('z', 'grouped', 'top', grouped, t({}, {'1': t({'/n': '5', '/key': '/west/acme'})}), slot='/n', count=1)
    run('z', 'uneven', 'count', uneven, t({'/count': '3'}))
    run('z', 'uneven', 'sum', uneven, fig('/total', 6), slot='/n')
    run('z', 'uneven', 'by', uneven, t({}, {'1': t({'/value': '1', '/count': '1', '/scale': '0'}), '2': t({'/value': '2', '/count': '1', '/scale': '0'}), '3': t({'/value': '3', '/count': '1', '/scale': '0'})}), key='depth')
    run('z', 'uneven', 'where', uneven, t({}, {'top': t({'/n': '2'}, {'mid': t({}, {'low': t({'/n': '3'})})})}), key='/n', op='over', value='1')
    run('z', 'hierarchy', 'sum', hier, fig('/total', 30), slot='/n')           # 2+4+8+16: interior records reached, the root is not a row
    run('z', 'hierarchy', 'count', hier, t({'/count': '4'}))
    run('z', 'hierarchy', 'max', hier, fig('/max', 16), slot='/n')
    run('z', 'hierarchy', 'by', hier, t({'/n': '1'}, {'1': t({'/value': '1', '/sum': '18', '/scale': '0'}), '2': t({'/value': '2', '/sum': '4', '/scale': '0'}), '3': t({'/value': '3', '/sum': '8', '/scale': '0'})}), key='depth', op='sum', slot='/n')
    run('z', 'hierarchy', 'where', hier, t({'/n': '1'}, {'d1': t({}, {'d2': t({'/n': '4'}, {'d3': t({'/n': '8'})})}), 'e': t({'/n': '16'})}), key='/n', op='over', value='3')
    run('y', 'table', 'where', tbl, t({}, {'r1': t({'/region': 'west', '/status': 'open', '/amount': '5'}), 'r2': t({'/region': 'west', '/status': 'closed', '/amount': '7'})}), key='/region', value='west')
    run('y', 'table', 'top', tbl, t({}, {'1': t({'/region': 'west', '/status': 'closed', '/amount': '7', '/key': 'r2'}), '2': t({'/region': 'west', '/status': 'open', '/amount': '5', '/key': 'r1'})}), slot='/amount', count=2)
    run('y', 'table', 'distinct', tbl, t({}, {'1': t({'/value': 'west', '/count': '2'}), '2': t({'/value': 'east', '/count': '2'})}), slot='/region')
    run('y', 'table', 'sum', tbl, fig('/total', 18), slot='/amount')
    run('y', 'bag', 'count', bag, t({'/count': '3'}))
    run('y', 'bag', 'where', bag, t({}, {'1': t({'/t': 'a'}), '2': t({'/t': 'a'}), '3': t({'/t': 'a'})}), key='/t', value='a')
    run('y', 'bag', 'select', bag, t({}, {'1': t({'/name': '1', '/t': 'a'}), '2': t({'/name': '2', '/t': 'a'}), '3': t({'/name': '3', '/t': 'a'})}), slots='/name /t')
    run('y', 'bag', 'any', bag, t({'/any': 'true'}), slot='/t')
    run('y', 'map', 'count', mp, t({'/count': '2'}))
    run('y', 'map', 'sort', mp, t({'/title': 'map'}, {'1': t({'/n': '8', '/region': 'east', '/key': 'zed'}), '2': t({'/n': '5', '/region': 'west', '/key': 'acme'})}), slot='/n', order='desc')
    run('y', 'map', 'by', mp, t({'/title': 'map'}, {'west': t({'/value': 'west', '/sum': '5', '/scale': '0'}), 'east': t({'/value': 'east', '/sum': '8', '/scale': '0'})}), key='/region', op='sum', slot='/n')
    run('y', 'map', 'each', mp, t({'/title': 'map'}, {'acme': t({'/n': '5', '/region': 'west', '/twice': '10', '/scale': '0'}), 'zed': t({'/n': '8', '/region': 'east', '/twice': '16', '/scale': '0'})}), left='/n', op='multiply', right='2', into='/twice')
    run('z', 'matrix', 'sum', matrix, fig('/total', 10), slot='/v')
    run('z', 'matrix', 'count', matrix, t({'/count': '4'}))
    run('z', 'matrix', 'flatten', matrix, t({}, {'r1_c1': t({'/r': 'r1', '/c': 'c1', '/v': '1'}), 'r1_c2': t({'/r': 'r1', '/c': 'c2', '/v': '2'}), 'r2_c1': t({'/r': 'r2', '/c': 'c1', '/v': '3'}), 'r2_c2': t({'/r': 'r2', '/c': 'c2', '/v': '4'})}))
    run('z', 'matrix', 'top', matrix, t({}, {'1': t({'/r': 'r2', '/c': 'c2', '/v': '4', '/key': '/r2/c2'})}), slot='/v', count=1)
    run('y', 'record + attachments', 'count', rec, t({'/count': '2'}))
    run('y', 'record + attachments', 'sum', rec, fig('/total', 4), slot='/size')
    run('y', 'record + attachments', 'select', rec, t({}, {'a1': t({'/kind': 'pdf'}), 'a2': t({'/kind': 'txt'})}), slots='/kind')

    # ---- the name convention: a child's name is the slot called name in any setting
    run('y', 'set', 'where', st, t({}, {'beta': t({})}), key='/name', value='beta')
    run('y', 'set', 'distinct', st, t({}, {'1': t({'/value': 'alpha', '/count': '1'}), '2': t({'/value': 'beta', '/count': '1'}), '3': t({'/value': 'gamma', '/count': '1'})}), slot='/name')
    run('y', 'set', 'select', st, t({}, {'alpha': t({'/name': 'alpha'}), 'beta': t({'/name': 'beta'}), 'gamma': t({'/name': 'gamma'})}), slots='/name')
    run('y', 'set', 'lookup', st, t({}, {'alpha': t({}), 'beta': t({}), 'gamma': t({})}), key='/name', match='/code', take='/region', table=live(home + '/codes'))
    run('y', 'map', 'lookup', home + '/codes', t({}, {'a': t({'/code': 'a', '/region': 'west', '/n': '1'})}), key='/code', match='/name', take='/n', table=live(mixed))
    run('z', 'matrix', 'where', matrix, t({}, {'r1': t({}, {'c1': t({'/r': 'r1', '/c': 'c1', '/v': '1'})}), 'r2': t({}, {'c1': t({'/r': 'r2', '/c': 'c1', '/v': '3'})})}), key='/name', value='c1')
    run('z', 'grouped', 'by', grouped, t({}, {'acme': t({'/value': 'acme', '/count': '1', '/scale': '0'}), 'bob': t({'/value': 'bob', '/count': '1', '/scale': '0'}), 'zed': t({'/value': 'zed', '/count': '1', '/scale': '0'})}), key='/name')
    merged, _ = run('y', 'list + tree view', 'merge', lst, t({'/title': 'list'}, dict(L, **{'a': t({'/n': '1'}, {'x': t({'/n': '2'}, {'deep': t({'/n': '3', '/t': 'leaf'})})}), 'b': t({'/n': '4'}, {'y': t({'/t': 'only'})}), 'empty': t({'/title': 'empty'})})), extra=live(tree, 'z'))
    run('x', 'record + list view', 'merge', rec, t({'/n': '7', '/t': 'hello', '/when': '12', '/ok': 'true', '/link': read(rec2, 'x')['reference']}, L), extra=live(lst))

    # ---- figures across a record and a view of a different shape
    run('x', 'record', 'add', rec, fig('/result', 10), left='/n', right='3')
    run('x', 'record', 'subtract', rec, fig('/result', 4), left='/n', right='3')
    run('x', 'record + list view', 'multiply', rec, fig('/result', 70), left='/n', right='/views/row/n', row=ref(read(lst + '/1', 'x')['reference']))
    run('x', 'record + map view', 'divide', rec, fig('/result', 1), left='/n', right='/views/entry/n', entry=ref(read(mp + '/zed', 'x')['reference']))
    run('x', 'record', 'pick', rec, t({'/n': '7', '/t': 'hello', '/when': '12', '/ok': 'true', '/link': read(rec2, 'x')['reference'], '/copy': 'hello'}), **{'from': '/t', 'into': '/copy'})
    run('x', 'record + tree view', 'pick', rec, t({'/n': '7', '/t': 'hello', '/when': '12', '/ok': 'true', '/link': read(rec2, 'x')['reference'], '/root_n': '100'}), **{'from': '/views/deep/n', 'into': '/root_n', 'deep': live(tree, 'z')})
    run('x', 'record', 'put', rec, t({'/n': '7', '/t': 'hello', '/when': '12', '/ok': 'true', '/link': read(rec2, 'x')['reference'], '/flag': 'yes'}), into='/flag', value='yes')
    run('x', 'record', 'round', rec, fig('/n', 70, '1'), slot='/n', places=1)
    run('z', 'tree + two record views', 'subtract', tree, fig('/result', 4), left='/views/one/n', right='/views/two/n', one=ref(read(rec, 'x')['reference']), two=ref(read(rec2, 'x')['reference']))

    # ---- time
    run('x', 'record', 'since', rec, fig('/since', 2), slot='/when', **{'from': '10'})
    run('y', 'list', 'between', lst, t({'/title': 'list'}, {'2': L['2'], '3': L['3']}), slot='/n', **{'from': '15', 'to': '35'})
    run('z', 'tree', 'between', tree, t(TREE_ROOT, {'a': t({}, {'x': t({'/n': '2'}, {'deep': t({'/n': '3', '/t': 'leaf'})})})}), slot='/n', **{'from': '2', 'to': '3'})

    # ---- the chain that changes shape at every step: z -> where -> by -> top -> sum
    w1 = cell('where', tree, 'z', key='/n', op='over', value='1')
    b1 = cell('by', '/x' + w1, 'z', key='depth', op='count')
    t1 = cell('top', '/x' + b1, 'y', slot='/count', count=2)
    s1 = cell('sum', '/x' + t1, 'y', slot='/count')
    chain = shape_of(read('/x' + s1, 'z'))
    ok = chain == fig('/total', 2)
    rows.append(('z->y', 'chain where, by depth, top, sum', 'chain', 'depth 0', ok, 0, 0))
    if not ok:
        print('MISMATCH chain', json.dumps(chain))

    # ---- amend over every shape (notes beside each cell), stale after the input changes
    def amended(name, formula_cell, notes, care='y'):
        for key, spec in notes.items():
            write(cells + '/' + name + 'notes/' + key, **spec)
        a = cell('amend', '/x' + formula_cell, care, notes=live(cells + '/' + name + 'notes'))
        return a
    stamp = lambda c: int(read('/c/x' + c, 'x')['properties']['/sys/tack/case'])
    p1 = cell('pick', rec, 'x', **{'from': '/t', 'into': '/copy'})
    a1 = amended('rec', p1, {'n1': {'slot': '/copy', 'value': 'edited', 'case': stamp(p1)}}, 'x')
    g = shape_of(read('/x' + a1, 'z')); ok = g['props']['/copy'] == 'edited' and g['props']['/n'] == '7'
    rows.append(('x', 'record', 'amend root slot', 'depth 0', ok, 0, 0))
    p2 = cell('where', lst, 'y', key='/t', value='a')
    a2 = amended('list', p2, {'r': {'slot': '/3/n', 'value': 99, 'case': stamp(p2)}})
    g = shape_of(read('/x' + a2, 'z')); ok = g['kids']['3']['props']['/n'] == '99' and g['kids']['1']['props']['/n'] == '10'
    rows.append(('y', 'list', 'amend one row', 'depth 1', ok, 0, 0))
    p3 = cell('select', mp, 'y', slots='/n /region')
    a3 = amended('map', p3, {'m': {'slot': '/acme/region', 'value': 'north', 'case': stamp(p3)}})
    g = shape_of(read('/x' + a3, 'z')); ok = g['kids']['acme']['props'] == {'/n': '5', '/region': 'north'} and g['kids']['zed']['props']['/region'] == 'east'
    rows.append(('y', 'map', 'amend named entry, other slots kept', 'depth 1', ok, 0, 0))
    p4 = cell('select', tree, 'z', slots='/n /t')
    a4 = amended('tree', p4, {'d': {'slot': '/a/x/deep/t', 'value': 'fixed', 'case': stamp(p4)}, 'dangling': {'slot': '/a/nowhere/t', 'value': 'x', 'case': stamp(p4)}}, 'z')
    g = shape_of(read('/x' + a4, 'z')); ctx = read('/c/x' + a4, 'x')['properties']
    ok = g['kids']['a']['kids']['x']['kids']['deep']['props'] == {'/n': '3', '/t': 'fixed'} and 'nowhere' not in g['kids']['a']['kids'] and ctx.get('/sys/view/note/dangling', '').startswith('no record')
    rows.append(('z', 'tree', 'amend deep leaf; dangling reported not created', 'depth 3', ok, 0, 0))
    write(tree + '/a/x/deep', n=3, t='leaf', extra='changed')
    ctx = read('/c/x' + a4, 'x')['properties']
    ok = ctx.get('/sys/view/note/d', '').startswith('note at case')
    rows.append(('z', 'tree', 'amend stale after input change', 'depth 3', ok, 0, 0))
    write(lst + '/1', n=11, t='a')
    ok = read('/c/x' + a2, 'x')['properties'].get('/sys/view/note/r', '').startswith('note at case')
    rows.append(('y', 'list', 'amend stale after input change', 'depth 1', ok, 0, 0))

    # ---- except, intersect, diff: the input against a /h view of the same path
    before = read(lst, 'y')['reference_y']
    write(lst + '/4', n=40, t='c')
    tool('write', records=[{'path': lst + '/2', 'action': 'cull'}])
    write(lst + '/1', n=12, t='a')
    now_rows = {'1': t({'/n': '12', '/t': 'a'}), '3': t({'/n': '30', '/t': 'a'}), '4': t({'/n': '40', '/t': 'c'})}
    run('y', 'list vs /h of itself', 'except', lst, t({'/title': 'list'}, {'4': now_rows['4']}), other=ref(before))
    run('y', 'list vs /h of itself', 'intersect', lst, t({'/title': 'list'}, {'1': now_rows['1'], '3': now_rows['3']}), other=ref(before))
    run('y', 'list vs /h of itself', 'diff', lst, t({'/added': '1', '/removed': '1', '/changed': '1'}, {'added': t({}, {'4': now_rows['4']}), 'removed': t({}, {'2': t({'/n': '20', '/t': 'b'})}), 'changed': t({}, {'1': t({'/n/from': '11', '/n/to': '12'})})}), other=ref(before))
    run('y', 'list vs /h of itself', 'diff', lst, t({'/added': '0', '/removed': '0', '/changed': '0'}), other=ref(read(lst, 'y')['reference_y']))
    tree_before = read(tree, 'z')['reference_z']
    write(tree + '/b/z', n=9)
    run('z', 'tree vs /h of itself', 'diff', tree, t({'/added': '1', '/removed': '0', '/changed': '0'}, {'added': t({}, {'b': t({}, {'z': t({'/n': '9'})})})}), other=ref(tree_before))
    run('z', 'tree vs /h of itself', 'except', tree, t({'/n': '100'}, {'b': t({}, {'z': t({'/n': '9'})})}), other=ref(tree_before))
    run('z', '/h view of the tree (pinned)', 'count', ref(tree_before), t({'/count': '6'}))
    run('y', 'list vs set, by name', 'intersect', lst, t({'/title': 'list'}, {'1': now_rows['1'], '3': now_rows['3']}), key='/name', other=live(home + '/picked'))
    run('y', 'set vs list, by name', 'except', home + '/picked', t({}, {'9': t({})}), key='/name', other=live(lst))

    # ---- the matrix
    print('| care | shape | formula | output | ok | ms | events |')
    print('|---|---|---|---|---|---|---|')
    for care, shape, formula, out, ok, ms, ev in rows:
        print(f'| {care} | {shape} | {formula} | {out} | {"pass" if ok else "FAIL"} | {ms} | {ev} |')
    failed = [r for r in rows if not r[4]]
    over_events = [r for r in rows if r[6] not in (None, 0)]
    over_ceiling = [r for r in rows if r[5] > 50]
    print(json.dumps({'cells': len(rows), 'failed': len(failed), 'sys_view_leaks': len(leaked), 'reads_with_events': len(over_events), 'over_50ms': len(over_ceiling), 'round_trips': seq}), flush=True)
    assert not failed, [(r[0], r[1], r[2]) for r in failed]
    assert not leaked, leaked
    assert not over_events, [(r[0], r[1], r[2], r[6]) for r in over_events]      # the events budget: a read costs nothing
    assert not over_ceiling, [(r[0], r[1], r[2], r[5]) for r in over_ceiling]    # times are informational below a 50 ms ceiling


if __name__ == '__main__':
    import sys
    check(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else '0x11', 120)
