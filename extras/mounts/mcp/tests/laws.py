"""Laws the standard cells obey by meaning, checked on random data in the world with no Python twin to agree with.

A twin written by the same hand shares its author's assumptions; a law does not. Each law below is a relation between
cells that holds whatever the data: it is read from the world and compared with itself.

Usage: python3 -I -c "import runpy; runpy.run_path('extras/mounts/mcp/tests/laws.py')['check']('http://127.0.0.1:8300', '0x11', 120)"
check(base, node, timeout, seed=None, shapes=24): prints the seed; writes `shapes` random shapes and checks every law on
each, at care y and z.
"""
import json
import random
import runpy
import time
import urllib.request
from fractions import Fraction
from pathlib import Path

sig = runpy.run_path(str(Path(__file__).with_name('signature.py')))
Gen, records, rows, cut, num_of, scale_of, is_num, DEC = (sig[k] for k in ('Gen', 'records', 'rows', 'cut', 'num_of', 'scale_of', 'is_num', 'DEC'))


def check(base, node, timeout, seed=None, shapes=24):
    seed = seed if seed is not None else random.randrange(1 << 30)
    print('laws seed', seed, flush=True)
    rng = random.Random(seed)
    g = Gen(rng, node)
    seq = [0]
    passed = {}

    def rpc(method, params):
        seq[0] += 1
        body = json.dumps(dict(jsonrpc='2.0', id=seq[0], method=method, params=params)).encode()
        req = urllib.request.Request(base + '/mcp', body, {'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.load(response)

    def tool(name, **arguments):
        reply = rpc('tools/call', {'name': 'mcp/' + name, 'arguments': arguments})
        assert 'error' not in reply, reply
        result = reply['result']
        assert not result.get('isError'), result
        return result['structuredContent']

    def read(path, care):
        return tool('read', path=path, care=care)

    def live(path, care):
        return {'type': 'reference', 'value': '/h/' + care + '/0/' + str(len(path.strip('/').split('/'))) + path}

    stdlib = {c['path'].rsplit('/', 1)[1]: {'type': 'reference', 'value': c['reference']} for c in read('/' + node + '/weft/stdlib', 'y')['children']}
    home = '/' + node + '/user/laws'
    try:
        tool('write', records=[{'path': home, 'action': 'cull'}])
    except AssertionError:
        pass
    tool('write', records=[{'path': home, 'slots': {'seed': seed}}])

    def value(props, slot):
        """A number as the read shows it: a decimal, or a natural at the record's scale."""
        v = props.get(slot)
        if v is None:
            return None
        if DEC.match(v):
            return Fraction(v)
        if not is_num(v):
            return None
        s = props.get(slot + '/scale', props.get('/scale', '0'))
        return Fraction(int(v), 10 ** int(s))

    def tree_rows(view):
        """Every record below the root of a read, as (name path, props), folders looked through."""
        out = []

        def walk(n, rel):
            for ch in n.get('children', []):
                name = ch['path'].rsplit('/', 1)[1]
                if ch['exists']:
                    out.append((rel + (name,), ch.get('properties', {})))
                walk(ch, rel + (name,))
        walk(view, ())
        return out

    def shape_of(view):
        return {'props': view.get('properties', {}), 'kids': {ch['path'].rsplit('/', 1)[1]: shape_of(ch) for ch in view.get('children', [])}}

    def law(name, ok, detail=''):
        passed.setdefault(name, [0, 0])[0 if ok else 1] += 1
        assert ok, (name, detail)

    for i in range(shapes):
        kind = rng.choice(['list', 'map', 'table', 'bag', 'tree', 'hier', 'grouped', 'matrix', 'attach'])
        shape = g.build(kind)
        if not shape['rec']:
            shape['props'] = {'/title': kind}
            shape['rec'] = True
        path = home + '/d' + str(i)
        tool('write', records=records(shape, path))
        cells = home + '/c' + str(i)
        for care in 'yz':
            R = rows(cut(shape, care), care)
            if not R:
                continue
            numeric = sorted({k for _, r in R for k, v in r['props'].items() if is_num(v) and not k.endswith('/scale') and k != '/scale'})
            textual = sorted({k for _, r in R for k, v in r['props'].items() if not is_num(v) and v not in ('true', 'false') and not k.endswith('/scale')})
            slot = rng.choice(numeric) if numeric else '/n'
            key = rng.choice(textual) if textual else '/t'
            key_values = [r['props'][key] for _, r in R if key in r['props']]
            kv = rng.choice(key_values) if key_values else 'none'
            c = cells + '/' + care
            tack = live(path, care)

            def cell(name, formula, tack_, **params):
                slots = {'sys/weft': stdlib[formula], 'sys/tack': tack_}
                slots.update(params)
                tool('write', records=[{'path': c + '/' + name, 'slots': slots}])
                return '/x' + c + '/' + name

            n_all = int(read(cell('count', 'count', tack), 'x')['properties']['/count'])
            # 1. a view against itself differs in nothing
            d = read(cell('self', 'diff', tack, other=tack), 'x')['properties']
            law('diff of a view against itself is zero', (d.get('/added'), d.get('/removed'), d.get('/changed')) == ('0', '0', '0'), d)
            # 2. where keeps what validate rejects: together they are every row
            kept = cell('kept', 'where', tack, key=key, value=kv)
            broken = cell('broken', 'validate', tack, key=key, value=kv)
            n_kept = int(read(cell('nkept', 'count', live(kept, care)), 'x')['properties']['/count'])
            n_broken = int(read(cell('nbroken', 'count', live(broken, care)), 'x')['properties']['/count'])
            law('count of where plus count of its complement is count', n_kept + n_broken == n_all, (n_kept, n_broken, n_all, key, kv))
            # 3. sort keeps count (of the rows with a number there)
            sorted_ = cell('sorted', 'sort', tack, slot=slot)
            ranged = cell('ranged', 'between', tack, slot=slot, **{'from': '-100000000', 'to': '100000000'})
            n_sorted = int(read(cell('nsorted', 'count', live(sorted_, care)), 'x')['properties']['/count'])
            n_ranged = int(read(cell('nranged', 'count', live(ranged, care)), 'x')['properties']['/count'])
            law('sort keeps count', n_sorted == n_ranged, (n_sorted, n_ranged))
            # 4. sum over group equals sum
            total = read(cell('total', 'sum', tack, slot=slot), 'x')['properties']
            grouped = cell('grouped', 'group', tack, key=key)
            regrouped = read(cell('gsum', 'sum', live(grouped, 'z'), slot=slot), 'x')['properties']
            with_key = [r for _, r in R if key in r['props']]
            law('sum over group equals sum of the grouped rows', value(regrouped, '/total') == sum((num_of(r, slot) for r in with_key if num_of(r, slot) is not None), Fraction(0)), (regrouped, total))
            # 5. a formula read over a kept cell equals the kept chain (the composition law on this surface; /b is not on it)
            chained = read(cell('chained', 'sum', live(kept, care), slot=slot), 'x')['properties']
            formula = tool('read', path=kept, care=care, formula='sum', settings={'slot': slot})['result'].get('properties', {})
            law('a formula read over a kept cell equals the kept chain', chained == formula, (chained, formula))
            # 6. flatten then unflatten is identity
            flat = cell('flat', 'flatten', live(path, 'z'))
            deep = cell('deep', 'unflatten', live(flat, 'y'))
            law('flatten then unflatten is identity', shape_of(read(deep, 'z')) == shape_of(read(path, 'z')), kind)
            # 7. select then drop of the same slots leaves nothing on any record
            picked = cell('picked', 'select', tack, slots=slot + ' ' + key)
            bare = read(cell('bare', 'drop', live(picked, care), slots=slot + ' ' + key), 'z')
            law('select then drop of the same slots leaves the records bare', not bare['properties'] and all(not p for _, p in tree_rows(bare)), bare['properties'])
            # 8. running's last value equals sum
            running = read(cell('running', 'running', tack, slot=slot), 'z')
            lasts = [value(p, '/running') for _, p in tree_rows(running) if '/running' in p]
            if lasts:
                law("running's last value equals sum", lasts[-1] == value(total, '/total'), (lasts[-1], total))
            # 9. rank of sorted is 1..n
            ranked = read(cell('ranked', 'rank', live(sorted_, 'y')), 'y')
            law('rank of sorted is 1..n', all(p.get('/rank') == rel[-1] for rel, p in tree_rows(ranked)), [(rel, p.get('/rank')) for rel, p in tree_rows(ranked)])
            # 10. percent sums to 100 at scale
            shares = read(cell('shares', 'percent', tack, slot=slot), 'z')
            parts = [value(p, '/percent') for _, p in tree_rows(shares) if '/percent' in p]
            total_v = value(total, '/total')
            if parts and total_v:
                law('percent sums to 100 at scale', abs(sum(parts) - 100) <= Fraction(1, 100) * len(parts), (float(sum(parts)), len(parts)))
            # expressions
            name = slot.lstrip('/')
            # 11. each "x" is a copy of x on every row
            copied = read(cell('copied', 'each', tack, expr=name, into='/copy'), 'z')
            law('each of a slot name copies the slot', all(value(p, '/copy') == value(p, slot) for _, p in tree_rows(copied) if slot in p),
                [(p.get('/copy'), p.get(slot)) for _, p in tree_rows(copied) if slot in p])
            # 12. where "true" is identity, where "false" is empty
            n_true = int(read(cell('ntrue', 'count', live(cell('always', 'where', tack, expr='true'), care)), 'x')['properties']['/count'])
            n_false = int(read(cell('nfalse', 'count', live(cell('never', 'where', tack, expr='false'), care)), 'x')['properties']['/count'])
            law('where true is identity and where false is empty', (n_true, n_false) == (n_all, 0), (n_true, n_false, n_all))
            # 13. when c then a else b: a on the rows where c keeps, b on the rows where not c keeps
            cond = name + ' > ' + str(int(rng.choice([v for v in (num_of(r, slot) for _, r in R) if v is not None] or [Fraction(0)])))
            chosen = read(cell('chosen', 'when', tack, expr=cond, then='yes', into='/k', **{'else': 'no'}), 'z')
            yes = {rel for rel, _ in tree_rows(read(cell('yes', 'where', tack, expr=cond), 'z'))}
            no = {rel for rel, _ in tree_rows(read(cell('no', 'where', tack, expr='not (' + cond + ')'), 'z'))}
            law('when c then a else b is a on where c and b on where not c',
                all((p.get('/k') == 'yes') == (rel in yes) and (p.get('/k') == 'no') == (rel in no) for rel, p in tree_rows(chosen) if rel in yes or rel in no), cond)
            # 14. round(x, 0) in an expression is the round entry
            rounded = read(cell('rounded', 'each', tack, expr='round(' + name + ', 0)', into='/r'), 'z')
            for rel, p in tree_rows(rounded):
                if '/r' in p:
                    entry = tool('read', path=path + '/' + '/'.join(rel), care='x', formula='round', settings={'slot': slot, 'places': '0'})['result'].get('properties', {})
                    law('round(x, 0) is the round entry', value(p, '/r') == value(entry, slot), (p.get('/r'), entry))
            # 15. each "a + b" is each left a add right b
            summed = read(cell('summed', 'each', tack, expr=name + ' + ' + name, into='/s'), 'z')
            added = read(cell('added', 'each', tack, left=slot, op='add', right=slot, into='/s'), 'z')
            law('each a + b is each left a add right b', [(rel, value(p, '/s')) for rel, p in tree_rows(summed)] == [(rel, value(p, '/s')) for rel, p in tree_rows(added)], kind)
    print(json.dumps({'seed': seed, 'shapes': shapes, 'laws': {k: v[0] for k, v in passed.items()}, 'round_trips': seq[0]}), flush=True)
    return passed


if __name__ == '__main__':
    import sys
    check(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else '0x11', 120, int(sys.argv[3]) if len(sys.argv) > 3 else None)
