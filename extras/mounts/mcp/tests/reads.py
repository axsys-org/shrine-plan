"""Reads beside reads and writes: does a slow read hold up anything else? Seeds one folder big enough that a deep read
of it takes about a second or more, then times, directly on the world's port: the slow read alone; two slow reads at
once; one slow read with a trivial read sent while it runs; one slow read with a write sent while it runs. Prints one
JSON line. Overlap means two slow reads take about as long as one, and the trivial read and the write answer in their
usual time while the slow read is still running.

Usage: python3 -I -c "import runpy; runpy.run_path('extras/mounts/mcp/tests/reads.py')['check']('http://127.0.0.1:8300', '0x11', 300)"
Environment: READS_RECORDS (default 4000) sizes the folder; READS_CARE (default z) the deep read's care;
READS_EXPECT=overlap asserts it (two slow reads under 1.5 times the slowest alone; the trivial read and the write
answered before the slow read, in under ten times their time alone).
"""
import json
import os
import statistics
import threading
import time
import urllib.request


def check(base, node, timeout):
    seq = [0]
    lock = threading.Lock()

    def tool(name, **arguments):
        with lock:
            seq[0] += 1
            n = seq[0]
        body = json.dumps(dict(jsonrpc='2.0', id=n, method='tools/call', params={'name': 'mcp/' + name, 'arguments': arguments})).encode()
        req = urllib.request.Request(base + '/mcp', body, {'Content-Type': 'application/json'})
        t0 = time.perf_counter()
        reply = json.load(urllib.request.urlopen(req, timeout=timeout))
        ms = 1000 * (time.perf_counter() - t0)
        result = reply['result']
        assert not result.get('isError'), json.dumps(result)[:300]
        return result['structuredContent'], ms

    records = int(os.environ.get('READS_RECORDS', '4000'))
    care = os.environ.get('READS_CARE', 'z')
    home = '/' + node + '/user/reads'
    folder = home + '/big'
    have = tool('read', path=folder, care='x')[0]
    if not have.get('exists') or (have.get('properties') or {}).get('/records') != str(records):
        t0 = time.perf_counter()
        tool('write', records=[{'path': home, 'slots': {'title': 'reads'}}, {'path': folder, 'slots': {'title': 'big'}}])
        for start in range(0, records, 250):
            tool('write', records=[{'path': folder + '/g' + str(i // 50) + '/r' + str(i),
                                    'slots': {'amount': i, 'status': 'open' if i % 3 else 'closed', 'note': 'record number ' + str(i)}}
                                   for i in range(start, min(records, start + 250))])
        tool('write', records=[{'path': folder, 'action': 'poke', 'slots': {'records': str(records)}}])
        seeded_s = round(time.perf_counter() - t0, 1)
    else:
        seeded_s = 0
    tool('write', records=[{'path': home + '/small', 'slots': {'n': 0}}])

    def slow():
        return tool('read', path=folder, care=care, limit=500)[1]

    def trivial():
        return tool('read', path=home + '/small', care='x')[1]

    counter = [0]

    def write():
        counter[0] += 1
        return tool('write', records=[{'path': home + '/small', 'slots': {'n': counter[0]}}])[1]

    def beside(background, foreground, delay=0.15):
        """Start background, send foreground after delay; (background ms, foreground ms, foreground answered first)."""
        out = {}
        done = {}

        def run(key, f):
            out[key] = f()
            done[key] = time.perf_counter()
        t = threading.Thread(target=run, args=('bg', background))
        t.start()
        time.sleep(delay)
        run('fg', foreground)
        t.join()
        return out['bg'], out['fg'], done['fg'] < done['bg']

    def pair():
        got = {}
        t0 = time.perf_counter()
        threads = [threading.Thread(target=lambda k=k: got.__setitem__(k, slow())) for k in ('a', 'b')]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        return 1000 * (time.perf_counter() - t0), got

    slow(); trivial(); write()                                   # warm
    # The first pair may start a reader whose heap is still small and grows through the read (once per reader the
    # world ever needs); it is reported, and the measured pair below is the steady state.
    cold_pair, _ = pair()
    alone = [slow() for _ in range(3)]
    trivial_alone = statistics.median([trivial() for _ in range(5)])
    write_alone = statistics.median([write() for _ in range(5)])
    two_wall, each = pair()
    s1, t1, t_first = beside(slow, trivial)
    s2, w2, w_first = beside(slow, write)
    r = lambda x: round(x, 1)
    if os.environ.get('READS_EXPECT') == 'overlap':
        slowest = max(alone)
        assert two_wall < 1.5 * slowest, ('two slow reads ran one after the other', two_wall, alone)
        assert t_first and t1 < max(250.0, 10 * trivial_alone), ('a trivial read waited behind a slow one', t1, s1)
        assert w_first and w2 < max(500.0, 10 * write_alone), ('a write waited behind a slow read', w2, s2)
    print(json.dumps({'records': records, 'care': care, 'seeded_s': seeded_s,
                      'slow_alone_ms': [r(x) for x in alone], 'trivial_alone_ms': r(trivial_alone), 'write_alone_ms': r(write_alone),
                      'first_pair_wall_ms': r(cold_pair), 'two_slow_wall_ms': r(two_wall), 'two_slow_each_ms': [r(each['a']), r(each['b'])],
                      'slow_with_trivial': {'slow_ms': r(s1), 'trivial_ms': r(t1), 'trivial_answered_first': t_first},
                      'slow_with_write': {'slow_ms': r(s2), 'write_ms': r(w2), 'write_answered_first': w_first}}), flush=True)
