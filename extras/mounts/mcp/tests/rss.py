"""A world's memory under the sidecar's reads: the shrine-mesa service lists /<node>/net/publications (care y, limit
500) every poll and the host lists the relationships folder; this replays both at RSS_RATE reads a second (default
7.5, five times one pilot world's rate) for RSS_SECONDS (default 600), samples the runtime's resident set every
RSS_SAMPLE seconds from /proc, and prints the samples and the growth in MB a minute fitted after the first two
minutes. RSS_PID names the wisp process (Linux only); RSS_EXPECT_MB_PER_MIN fails the check above that growth;
RSS_DEEP=<path> replaces the reads with a deep z read of that folder (fast allocation, to reach a store collection).

Usage: RSS_PID=<wisp pid> python3 -I -c "import runpy; runpy.run_path('extras/mounts/mcp/tests/rss.py')['check']('http://127.0.0.1:8300', '0x11', 120)"
"""
import json
import os
import time
import urllib.request


def rss_mb(pid):
    with open('/proc/%d/status' % pid) as f:
        for line in f:
            if line.startswith('VmRSS:'):
                return int(line.split()[1]) / 1024
    return 0.0


def check(base, node, timeout):
    pid = int(os.environ['RSS_PID'])
    rate = float(os.environ.get('RSS_RATE', '7.5'))
    seconds = float(os.environ.get('RSS_SECONDS', '600'))
    every = float(os.environ.get('RSS_SAMPLE', '30'))
    seq = [0]

    def tool(name, **arguments):
        seq[0] += 1
        body = json.dumps(dict(jsonrpc='2.0', id=seq[0], method='tools/call', params={'name': 'mcp/' + name, 'arguments': arguments})).encode()
        req = urllib.request.Request(base + '/mcp', body, {'Content-Type': 'application/json'})
        result = json.load(urllib.request.urlopen(req, timeout=timeout))['result']
        assert not result.get('isError'), json.dumps(result)[:300]
        return result['structuredContent']

    publications = '/' + node + '/net/publications'
    relationships = '/' + node + '/relationships'
    if not tool('read', path=publications + '/p0', care='x').get('exists'):
        tool('write', records=[{'path': publications + '/p' + str(i), 'slots': {'path': '/' + node + '/user/shared/item' + str(i), 'to': '0x1f'}} for i in range(20)] +
             [{'path': relationships + '/0x' + format(32 + i, 'x'), 'slots': {'name': 'peer ' + str(i), 'status': 'active'}} for i in range(13)])
    reads = [dict(path=publications, care='y', limit=500), dict(path=relationships, care='y', limit=500)]
    if os.environ.get('RSS_DEEP'):
        # the deep read of tests/reads.py's folder: megabytes allocated per read, so the store reaches its
        # collection budget (its live size) within minutes and a collection shows in the samples
        reads = [dict(path=os.environ['RSS_DEEP'], care='z', limit=500)] * 2
    samples = []
    start = time.monotonic()
    next_sample = start
    n = 0
    while True:
        now = time.monotonic()
        if now >= next_sample:
            samples.append((round(now - start, 1), round(rss_mb(pid), 1)))
            next_sample += every
        if now - start >= seconds:
            break
        tool('read', **reads[n % 2])
        n += 1
        time.sleep(max(0.0, start + n / rate - time.monotonic()))
    late = [(t, m) for t, m in samples if t >= 120]
    slope = None
    if len(late) >= 2:
        mt = sum(t for t, _ in late) / len(late)
        mm = sum(m for _, m in late) / len(late)
        slope = 60 * sum((t - mt) * (m - mm) for t, m in late) / sum((t - mt) ** 2 for t, _ in late)
    bound = os.environ.get('RSS_EXPECT_MB_PER_MIN')
    if bound is not None:
        assert slope is not None and slope < float(bound), ('the world grows under reads', slope, samples)
    print(json.dumps({'reads': n, 'rate': rate, 'seconds': seconds, 'mb_per_minute_after_2min': None if slope is None else round(slope, 2),
                      'samples': samples}), flush=True)
