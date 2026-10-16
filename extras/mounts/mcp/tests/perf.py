"""Performance on a realistic world, through MCP only: one seeded world, a fixed shuffled mix of calls, run cold then warm.

Usage: python3 -I -c "import runpy; runpy.run_path('extras/mounts/mcp/tests/perf.py')['check']('http://127.0.0.1:8302', '0x11', 120)"
check(base, node, timeout, seed=None, calls=2000) seeds 10,000 records across 40 folders (deals, people, invoices with lines,
notes), 340 cells (single steps, chains of two to four, secondary inputs across folders, grouped and grid outputs, amended
with notes, faulted) and ten cases of history on a hundred records; then runs the same shuffled mix twice (the second run
is the warm one; the difference is the cost of a cold law cache) and prints a table per run: n, p50, p95, p99, max, events
per call, nodes read (the reply for a plain read, the input for a cell or formula read) and microseconds per node.
Hard fail, checked after both tables are printed: a read costing an event, a write costing more than one, p99 of a record
read over 20 ms, p99 of a four-step chain read over 60 ms (the warm run).
"""
import json
import random
import statistics
import subprocess
import time
import urllib.parse
import urllib.request

SIZES = [500, 400, 300, 250, 200, 150, 100, 50, 40, 10]     # children per folder, ten folders per kind: 2,000 records a kind
KINDS = ['deals', 'people', 'invoices', 'notes']
STATUS = {'deals': ['open', 'closed', 'lost'], 'people': ['active', 'left'], 'invoices': ['paid', 'due', 'void'], 'notes': ['todo', 'done']}
OWNERS = ['ann', 'bo', 'cy', 'di', 'ed', 'flo', 'gus', 'hal']
REGIONS = ['west', 'east', 'north', 'south']
TEAMS = ['eng', 'ops', 'sales', 'legal', 'design', 'support']


def check(base, node, timeout, seed=None, calls=2000):
    seed = random.randrange(1 << 32) if seed is None else seed
    rng = random.Random(seed)
    port = urllib.parse.urlparse(base).port
    print(f'perf: base={base} node={node} seed={seed} calls={calls}')
    seq = 0
    samples = []      # the current run's (kind, ms, events, nodes)

    def epoch():
        try:
            with urllib.request.urlopen(base + '/probe/read?path=/' + node, timeout=timeout) as r:
                return json.load(r).get('epoch')
        except Exception:
            return None

    def rpc(method, params, kind=None, nodes=None):
        """One JSON-RPC call; when kind is given, its time and the events it cost (probe epoch before and after) are sampled."""
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
            e1 = epoch()
            samples.append((kind, ms, (e1 - e0) if e0 is not None and e1 is not None else None, nodes))
        return reply

    def tool(name, kind=None, nodes=None, **arguments):
        reply = rpc('tools/call', {'name': 'mcp/' + name, 'arguments': arguments}, kind, nodes)
        assert 'error' not in reply, reply
        result = reply['result']
        assert not result.get('isError'), result
        return result['structuredContent']

    def tool_refused(name, kind, **arguments):
        reply = rpc('tools/call', {'name': 'mcp/' + name, 'arguments': arguments}, kind)
        return reply.get('result', {}).get('isError') or 'error' in reply

    def read(path, care='y', kind=None, nodes=None):
        return tool('read', kind, nodes, path=path, care=care)

    def live(path, care='y'):
        return {'type': 'reference', 'value': '/h/' + care + '/0/' + str(len(path.strip('/').split('/'))) + path}

    def ref(reference):
        return {'type': 'reference', 'value': reference}

    def count_nodes(view):
        return 1 + sum(count_nodes(ch) for ch in view.get('children', []))

    def timed_read(path, care, kind):
        """A plain read whose node count is the reply's size."""
        view = read(path, care)
        samples_kind = samples  # read() above was untimed; redo it timed now that the size is known? No: time it once.
        return view

    stdlib = {c['path'].rsplit('/', 1)[1]: ref(c['reference']) for c in read('/' + node + '/weft/stdlib')['children']}

    # ---- the world: 10,000 records across 40 folders, seeded in batches of 300
    home = '/' + node + '/user/perf'
    try:
        tool('write', records=[{'path': home, 'action': 'cull'}])   # a rerun starts clean; refused and harmless the first time
    except AssertionError:
        pass
    pending = [(home, {'title': 'perf world'})]
    seeded = 0

    def put(path, **slots):
        pending.append((path, slots))

    def flush(force=False):
        nonlocal seeded
        if pending and (force or len(pending) >= 300):
            tool('write', records=[{'path': p, 'slots': s} for p, s in pending])
            seeded += len(pending)
            del pending[:]

    folders = {}          # folder path -> (kind, children)
    records = []          # every leaf record path, for reads at x
    for kind in KINDS:
        put(home + '/' + kind, title=kind)
        for f, size in enumerate(SIZES):
            folder = home + '/' + kind + '/' + kind + '_' + str(f)
            put(folder, title=kind + ' ' + str(f))
            folders[folder] = (kind, size)
            for i in range(size):
                path = folder + '/r' + str(i)
                status = STATUS[kind][i % len(STATUS[kind])]
                if kind == 'deals':
                    put(path, status=status, amount=rng.randrange(1000, 900000), owner=rng.choice(OWNERS), region=rng.choice(REGIONS),
                        when=rng.randrange(1, 366), customer='c' + str(rng.randrange(50)), **{'amount/scale': 2})
                elif kind == 'people':
                    put(path, status=status, amount=rng.randrange(60, 220) * 1000, name=rng.choice(OWNERS) if i < 8 else 'p' + str(i),
                        team=rng.choice(TEAMS), age=rng.randrange(20, 65))
                elif kind == 'invoices':
                    put(path, status=status, amount=rng.randrange(100, 50000), customer='c' + str(rng.randrange(50)), owner=rng.choice(OWNERS),
                        when=rng.randrange(1, 366), **{'amount/scale': 2})
                    if i % 2 == 0:      # every other invoice carries two lines: 2,000 nested records
                        for line in (1, 2):
                            put(path + '/l' + str(line), qty=rng.randrange(1, 9), price=rng.randrange(100, 9000), **{'price/scale': 2})
                else:
                    put(path, status=status, amount=rng.randrange(5, 400), author=rng.choice(OWNERS), kind=rng.choice(['call', 'mail', 'meeting']),
                        when=rng.randrange(1, 366))
                records.append(path)
                flush()
    scratch = [home + '/scratch/s' + str(i) for i in range(60)]     # for cull-and-revive: 60 folders of 20
    put(home + '/scratch', title='scratch')
    for folder in scratch:
        put(folder, title='scratch')
        for i in range(20):
            put(folder + '/r' + str(i), n=i, status='x')
            flush()
    flush(True)
    by_kind = {kind: [f for f in folders if folders[f][0] == kind] for kind in KINDS}
    print(f'seeded {seeded} records ({len(records)} leaves in {len(folders)} folders, 2,000 invoice lines, 1,260 scratch) in {seq} calls')

    # ---- the cells: 100 single steps, 100 in chains, 50 with secondary inputs, 50 grouped, 10 faulted; then 30 amended
    cells = home + '/cells'
    put(cells, title='cells')
    made = {}             # cell path -> input nodes (the folder it ultimately reads)

    def cell(name, formula, tack_path, care='y', nodes=0, **params):
        props = {'sys/weft': stdlib[formula], 'sys/tack': tack_path if isinstance(tack_path, dict) else live(tack_path, care)}
        props.update(params)
        put(cells + '/' + name, **props)
        made[cells + '/' + name] = nodes
        return cells + '/' + name

    singles, counts, sums = [], {}, {}
    folder_list = list(folders)
    for i, folder in enumerate(folder_list):
        kind, size = folders[folder]
        counts[folder] = cell('count_' + str(i), 'count', folder, nodes=size)
        sums[folder] = cell('sum_' + str(i), 'sum', folder, nodes=size, slot='/amount', into='/total')
        singles += [counts[folder], sums[folder]]
    others = [('where', dict(key='/status', value='closed')), ('distinct', dict(slot='/status')), ('sort', dict(slot='/amount', order='desc')),
              ('top', dict(slot='/amount', count=5)), ('avg', dict(slot='/amount')), ('min', dict(slot='/amount')), ('max', dict(slot='/amount')),
              ('select', dict(slots='/amount /status')), ('latest', dict(slot='/when')), ('between', {'slot': '/amount', 'from': '1000', 'to': '400000'})]
    for i in range(20):
        formula, params = others[i % len(others)]
        folder = rng.choice(folder_list)
        singles.append(cell('one_' + str(i), formula, folder, nodes=folders[folder][1], **params))
    chains = {2: [], 3: [], 4: []}       # depth -> the cell at that depth of each chain
    n_chain = 0
    while sum(len(v) for v in chains.values()) + 33 <= 100 or n_chain < 33:
        length = 2 + n_chain % 3
        folder = rng.choice(folder_list)
        kind, size = folders[folder]
        first = cell(f'ch{n_chain}_1', 'where', folder, nodes=size, key='/status', value=STATUS[kind][1])
        if length == 2:
            chains[2].append(cell(f'ch{n_chain}_2', 'sum', '/x' + first, nodes=size, slot='/amount', into='/total'))
        else:
            each = cell(f'ch{n_chain}_2', 'each', '/x' + first, nodes=size, left='/amount', op='multiply', right='2', into='/double')
            if length == 3:
                chains[3].append(cell(f'ch{n_chain}_3', 'sum', '/x' + each, nodes=size, slot='/double', into='/total'))
            else:
                srt = cell(f'ch{n_chain}_3', 'sort', '/x' + each, nodes=size, slot='/double', order='desc')
                chains[4].append(cell(f'ch{n_chain}_4', 'sum', '/x' + srt, nodes=size, slot='/double', into='/total'))
        n_chain += 1
        if n_chain == 33:
            break
    n_chain_cells = sum(len(v) for v in chains.values()) + 33 + len(chains[3]) + 2 * len(chains[4])
    secondary = []
    for i in range(50):
        deals = rng.choice(by_kind['deals'])
        other = rng.choice(by_kind['deals'])
        people = rng.choice(by_kind['people'])
        size = folders[deals][1] + folders[other if i % 5 else people][1]
        if i % 5 == 0:
            secondary.append(cell('sec_' + str(i), 'lookup', deals, nodes=size, key='/owner', match='/name', take='/team', into='/team', table=live(people)))
        elif i % 5 == 1:
            secondary.append(cell('sec_' + str(i), 'merge', deals, nodes=size, extra=live(other)))
        elif i % 5 == 2:
            secondary.append(cell('sec_' + str(i), 'except', deals, nodes=size, key='/customer', other=live(other)))
        elif i % 5 == 3:
            secondary.append(cell('sec_' + str(i), 'intersect', deals, nodes=size, key='/customer', other=live(other)))
        else:
            secondary.append(cell('sec_' + str(i), 'subtract', '/x' + sums[deals], nodes=size, left='/total', right='/views/other/total', other=live('/x' + sums[other], 'x')))
    grouped = []
    for i in range(50):
        folder = rng.choice(by_kind['deals'] + by_kind['invoices'])
        kind, size = folders[folder]
        if i % 5 < 2:
            grouped.append(cell('grp_' + str(i), 'by', folder, nodes=size, key='/status', op='sum', slot='/amount'))
        elif i % 5 < 4:
            grouped.append(cell('grp_' + str(i), 'grid', folder, nodes=size, row='/owner', col='/status', op='sum', slot='/amount'))
        else:
            inv = rng.choice(by_kind['invoices'])      # a matrix at z: invoices with their lines beneath
            grouped.append(cell('grp_' + str(i), 'grid', inv, 'z', nodes=2 * folders[inv][1], row='/customer', col='/status', op='count'))
    faulted = [cell('fault_' + str(i), 'count', home + '/nowhere_' + str(i), nodes=0) for i in range(5)]
    faulted += [cell('loop_' + str(i), 'count', cells, nodes=0) for i in range(3)]
    faulted += [cell('ping', 'count', '/x' + cells + '/pong', nodes=0), cell('pong', 'count', '/x' + cells + '/ping', nodes=0)]
    flush(True)
    amended = []
    for i in range(30):
        base_cell = sums[folder_list[i]]
        stamp = read('/c/x' + base_cell, 'x')['properties']['/sys/tack/case']
        put(home + '/amend_notes/' + str(i), title='notes')
        put(home + '/amend_notes/' + str(i) + '/n1', slot='/total', value=1, case=stamp)
        if i % 3 == 0:
            put(home + '/amend_notes/' + str(i) + '/n2', slot='/r0/amount', value=1, case=stamp)    # dangling on a sum result: reported
        amended.append(cell('amended_' + str(i), 'amend', '/x' + base_cell, 'x', nodes=folders[folder_list[i]][1], notes=live(home + '/amend_notes/' + str(i))))
    flush(True)
    print(f'cells: {len(made)} ({len(singles)} single, {n_chain_cells} in {n_chain} chains, {len(secondary)} secondary, {len(grouped)} grouped, {len(faulted)} faulted, {len(amended)} amended)')

    # ---- history: ten cases on a hundred records (deals_0/r0..r99), which also makes the first amended cells stale
    deep = [folder_list[0] + '/r' + str(i) for i in range(100)]
    for case in range(10):
        tool('write', records=[{'path': p, 'action': 'poke', 'slots': {'touched': case}} for p in deep])
    tool('write', records=[{'path': folder_list[i] + '/r1', 'action': 'poke', 'slots': {'touched': 1}} for i in range(1, 15)])
    undo_refs = [tool('history', path=p, limit=10)['versions'][rng.randrange(2, 8)]['reference'] for p in deep[:50]]
    print(f'history: ten cases on {len(deep)} records; seeding took {seq} calls')

    # ---- apply: an op card is planted by a mount, never written over MCP; use one if the world has any, else measure the refusal
    ops = []
    for name in ('app', 'io', 'weft'):      # never the node root at y: that renders the whole world
        try:
            for child in read('/' + node + '/' + name, 'y').get('children', []):
                if child['path'].endswith('/op'):
                    ops += [('/' + node + '/' + name, c['path']) for c in read(child['path'], 'y').get('children', [])]
        except Exception:
            pass
    print(f'apply: {len(ops)} op cards in the world' + ('' if ops else ' (the apply rows measure the refused call)'))

    # ---- the mix, built once in a fixed shuffled order and run twice
    big = [f for f in folder_list if folders[f][1] >= 250]
    zs = [(f, folders[f][1] + 1 + (folders[f][1] if folders[f][0] == 'invoices' else 0)) for f in folder_list] + \
         [(home + '/' + k, 2011) for k in ('deals', 'people', 'notes')]
    cursor = [None]

    def read_at(path, care, kind):
        view = read(path, care)
        samples.append(samples.pop()[:3] + (count_nodes(view),)) if False else None
        return view

    def plain(path, care, kind):
        def go():
            e0 = epoch(); t0 = time.perf_counter()
            view = tool('read', path=path, care=care, limit=500)       # the cap: an answer is at most 500 nodes
            ms = 1000 * (time.perf_counter() - t0); e1 = epoch()
            samples.append((kind, ms, (e1 - e0) if e0 is not None and e1 is not None else None, count_nodes(view)))
        return go

    def cellread(kind, pool, prefix='/x', care='y'):
        def go(path=rng.choice(pool)):
            tool('read', kind, made[path], path=prefix + path, care=care)
        return go

    def formula(kind, name, settings):
        def go(folder=rng.choice(big)):
            tool('read', kind, folders[folder][1], path=folder, care='y', formula=name, settings=settings)
        return go

    def poke(i):
        p = rng.choice(records)
        return lambda: tool('write', 'write poke', path=p, action='poke', properties={'status': 'closed', 'touched': i})

    def make(i):
        return lambda: tool('write', 'write make', path=home + '/made/m' + str(i), properties={'amount': i, 'status': 'open'})

    def cull_revive(i):
        folder = scratch[i % len(scratch)]
        revive = [{'path': folder, 'slots': {'title': 'scratch'}}] + [{'path': folder + '/r' + str(k), 'slots': {'n': k, 'status': 'x'}} for k in range(20)]

        def go():
            tool('write', 'write cull', records=[{'path': folder, 'action': 'cull'}])
            tool('write', 'write revive (batch of 21)', records=revive)
        return go

    def batch20(i):
        recs = [{'path': home + '/batch/b' + str(i) + '_' + str(k), 'slots': {'amount': k, 'status': 'open'}} for k in range(20)]
        return lambda: tool('write', 'write batch of 20', records=recs)

    def with_then(i):
        folder = rng.choice(folder_list)
        p = folder + '/r' + str(rng.randrange(folders[folder][1]))
        return lambda: tool('write', 'write with then (x2)', records=[{'path': p, 'action': 'poke', 'slots': {'amount': 1000 + i}}],
                            then=['/x' + sums[folder], '/c/x' + sums[folder]])

    def undo(i):
        return lambda: tool('write', 'write undo (from)', records=[{'path': deep[i % 50], 'from': undo_refs[i % 50]}])

    def history(i):
        def go():
            page = tool('history', 'history page of 40', limit=40, **({'before': cursor[0]} if i % 2 and cursor[0] else {}))
            cursor[0] = page.get('next')
        return go

    def apply(i):
        if ops:
            path, op = ops[i % len(ops)]
            return lambda: tool('apply', 'apply', path=path, operation=op, inputs={'d': 1})
        p = rng.choice(records)
        return lambda: tool_refused('apply', 'apply (refused: no op card)', path=p, operation=p + '/op/missing', inputs={})

    share = lambda fraction: max(1, round(fraction * calls))
    plan = []
    plan += [plain(rng.choice(records), 'x', 'read record x') for _ in range(share(0.135))]
    plan += [plain(rng.choice(folder_list), 'y', 'read folder y') for _ in range(share(0.1325))]
    plan += [plain(rng.choice(zs)[0], 'z', 'read subtree z') for _ in range(share(0.1325))]
    plan += [cellread('cell /x single', singles) for _ in range(share(0.06))]
    for depth in (2, 3, 4):
        plan += [cellread(f'cell /x chain d{depth}', chains[depth]) for _ in range(share(0.03))]
    plan += [cellread('cell /x secondary', secondary) for _ in range(share(0.025))]
    plan += [cellread('cell /x grouped', grouped) for _ in range(share(0.025))]
    plan += [cellread('cell /x amended', amended) for _ in range(share(0.015))]
    plan += [cellread('cell /c/x amended', amended, '/c/x', 'x') for _ in range(share(0.02))]
    plan += [cellread('cell /c/x faulted', faulted, '/c/x', 'x') for _ in range(share(0.015))]
    plan += [formula('formula where', 'where', {'key': '/status', 'value': 'closed'}) for _ in range(share(0.035))]
    plan += [formula('formula by', 'by', {'key': '/status', 'op': 'sum', 'slot': '/amount'}) for _ in range(share(0.0325))]
    plan += [formula('formula distinct', 'distinct', {'slot': '/owner'}) for _ in range(share(0.0325))]
    for factory in (poke, make, cull_revive, batch20, with_then):
        plan += [factory(i) for i in range(share(0.03))]
    plan += [undo(i) for i in range(share(0.025))]
    plan += [history(i) for i in range(share(0.025))]
    plan += [apply(i) for i in range(share(0.05))]
    rng.shuffle(plan)

    def rss_kb():
        try:
            for pid in subprocess.check_output(['lsof', '-nP', f'-iTCP:{port}', '-sTCP:LISTEN', '-t']).split():
                if b'shrine-eden' in subprocess.check_output(['ps', '-o', 'command=', '-p', pid]):
                    return int(subprocess.check_output(['ps', '-o', 'rss=', '-p', pid]))
        except Exception:
            return None

    def journal():
        return len(read('/' + node + '/log', 'y').get('children', []))

    def pct(values, q):
        s = sorted(values)
        return s[min(len(s) - 1, max(0, int(round(q * len(s) + 0.5)) - 1))]

    def table(label, run):
        kinds = sorted({k for k, _, _, _ in run})
        print(f'\n{label}: {len(run)} calls')
        print('| call | n | p50 ms | p95 ms | p99 ms | max ms | events/call | nodes (median) | us/node |')
        print('|---|---|---|---|---|---|---|---|---|')
        stats = {}
        for kind in kinds:
            ms = [m for k, m, _, _ in run if k == kind]
            ev = [e for k, _, e, _ in run if k == kind and e is not None]
            nodes = [n for k, _, _, n in run if k == kind and n]
            med_nodes = statistics.median(nodes) if nodes else None
            per_node = round(1000 * statistics.median(ms) / med_nodes, 1) if med_nodes else ''
            stats[kind] = dict(n=len(ms), p50=pct(ms, 0.5), p95=pct(ms, 0.95), p99=pct(ms, 0.99), max=max(ms), events=max(ev) if ev else None,
                               ev_mean=round(statistics.mean(ev), 3) if ev else None, nodes=med_nodes)
            s = stats[kind]
            print(f"| {kind} | {s['n']} | {s['p50']:.1f} | {s['p95']:.1f} | {s['p99']:.1f} | {s['max']:.1f} | {s['ev_mean']} | {med_nodes if med_nodes is not None else ''} | {per_node} |")
        return stats

    rss0, journal0 = rss_kb(), journal()
    runs = []
    for label in ('cold run', 'warm run'):
        samples.clear()
        t0 = time.perf_counter()
        for step in plan:
            step()
        wall = time.perf_counter() - t0
        runs.append((label, list(samples), wall))
    rss1, journal1 = rss_kb(), journal()
    stats = [table(f'{label} ({wall:.1f} s wall)', run) for label, run, wall in runs]
    print(f'\nwisp RSS before {rss0} KB, after {rss1} KB ({(rss1 - rss0) if rss0 and rss1 else "n/a"} KB for two runs); '
          f'journal {journal0} events before, {journal1} after ({journal1 - journal0} for two runs)')

    # ---- the budget: events on both runs, times on the warm run
    broken = []
    for (label, run, _), st in zip(runs, stats):
        for kind, s in st.items():
            reads = kind.startswith(('read', 'cell', 'formula', 'history'))
            if s['events'] is not None and ((reads and s['events'] > 0) or (kind.startswith('write') and s['events'] > 1)):
                broken.append((label, kind, 'events', s['events']))
    warm = stats[-1]
    if warm['read record x']['p99'] > 20:
        broken.append(('warm run', 'read record x', 'p99 over 20 ms', warm['read record x']['p99']))
    if warm['cell /x chain d4']['p99'] > 60:
        broken.append(('warm run', 'cell /x chain d4', 'p99 over 60 ms', warm['cell /x chain d4']['p99']))
    print(json.dumps({'seed': seed, 'calls_per_run': len(runs[0][1]), 'round_trips': seq, 'cold_wall_s': round(runs[0][2], 1), 'warm_wall_s': round(runs[1][2], 1),
                      'budget': 'held' if not broken else broken}), flush=True)
    assert not broken, broken


if __name__ == '__main__':
    import sys
    check(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else '0x11', 120, int(sys.argv[3]) if len(sys.argv) > 3 else None)
