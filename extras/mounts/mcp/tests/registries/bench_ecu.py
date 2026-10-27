"""The standing benchmark: the 5-ton military ECU workspace, run the way a person runs it, then scored on what the
world became. It writes what the page writes (the inputs, the world cell over the standings) and waits for the
workspace hand to finish a round and compose its reading; the hand must be running against the same world.

    python3 bench_ecu.py http://127.0.0.1:8150 [--node 0x11] [--name bench] [--wait 600]

Six questions, each a number, each read off the records, never off the hand's log:
    things     named things the round landed at shared names under /user/<kind>/ (stable names, not sentences)
    relations  relation records written beneath things, each with a source (the one shape: slot, note, source)
    sourced    the share of those relations that carry a source (one click from any statement to where it was said)
    joined     components and islands of the workspace's world: did the standings meet, and through what
    direct     entries in the reading's first section (direct evidence) against entries under Related
    settled    asks done against asks left working: did the process stop when the evidence ran out
"""
import argparse
import json
import re
import sys
import time
import urllib.request

KINDS = ('places', 'products', 'materials', 'companies', 'people', 'parts', 'applications', 'customers', 'items')


def rpc(base, name, **args):
    body = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'mcp/' + name, 'arguments': args}}).encode()
    reply = json.load(urllib.request.urlopen(urllib.request.Request(base + '/mcp', body, {'Content-Type': 'application/json'}), timeout=600))
    result = reply.get('result') or {}
    if 'error' in reply or result.get('isError'):
        raise RuntimeError(json.dumps(reply)[:300])
    return result['structuredContent']


def ref(path, care='x'):
    return {'type': 'reference', 'value': '/h/%s/0/%d%s' % (care, len(path.split('/')) - 1, path)}


def kids(base, path, care='y'):
    return rpc(base, 'read', path=path, care=care, limit=500).get('children') or []


def walk(base, path):
    out = []
    nxt = None
    for _ in range(4):
        r = rpc(base, 'read', path=path, care='z', limit=500, **({'next': nxt} if nxt else {}))
        def visit(n):
            out.append((n.get('path', ''), {k.lstrip('/'): v for k, v in (n.get('properties') or {}).items()}))
            for c in n.get('children') or []:
                visit(c)
        visit(r)
        nxt = r.get('next')
        if not nxt:
            break
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument('base'); p.add_argument('--node', default='0x11'); p.add_argument('--name', default='bench_%d' % int(time.time()) % 100000); p.add_argument('--wait', type=int, default=600)
    a = p.parse_args()
    node, base, ws = a.node, a.base, '/' + a.node + '/user/workspaces/' + a.name
    before = {k: len(kids(base, '/' + node + '/user/' + k)) for k in KINDS}
    request = '/' + node + '/user/registries/mep/opportunities/n2026_536'
    recipients = '/' + node + '/user/registries/usaspending/recipients'
    question = ('Which of these recipients can build a 5-ton military environmental control unit by Friday? Rank them by evidence: '
                'awards that paid for ECUs, a plant judged theirs in EPA ECHO, customs imports, and patents. Say what is still unknown for each.')
    pages = [('https://www.mainstream-engr.com/', '/' + node + '/user/web/pages/mainstream_engr_com/index'), ('https://www.hdtglobal.com/', '/' + node + '/user/web/pages/hdtglobal_com/index')]
    defn = rpc(base, 'read', path='/' + node + '/weft/graph/overlay', care='x')
    case = re.match(r'^/h/x/(\d+)/', str(defn.get('reference') or '')).group(1)
    t0 = time.time()
    # what the page writes, in the order a person pastes: the workspace, the text, the pages, then the cell over all of it
    rpc(base, 'write', who='person', records=[{'path': ws, 'slots': {'name': a.name}}, {'path': ws + '/inputs/i1', 'slots': {'name': question[:80], 'text': question}}]
        + [{'path': path, 'slots': {'name': url.replace('https://', ''), 'url': url}} for url, path in pages if not rpc(base, 'read', path=path, care='x').get('exists')])
    standings = [(request, 'x'), (recipients, 'y'), (ws + '/inputs/i1', 'x')] + [(path, 'x') for _, path in pages]
    slots = {'sys/weft': {'type': 'reference', 'value': '/h/x/%s/4/%s/weft/graph/overlay' % (case, node)}, 'sys/tack': ref(standings[0][0], standings[0][1]), 'depth': 3, 'nodes': 120, 'cap': 16, 'deeper': 4}
    for i, (path, care) in enumerate(standings[1:]):
        slots['standing/' + chr(98 + i)] = ref(path, care)
    rpc(base, 'write', who='person', records=[{'path': ws + '/world', 'slots': slots, 'action': 'set'}])
    print('workspace', ws, 'written; waiting for the hand')
    reading = None
    while time.time() - t0 < a.wait:
        versions = kids(base, ws + '/views/reading')
        asks = [(c.get('properties') or {}) for c in kids(base, ws + '/asks')]
        if versions and asks and all(x.get('/state') == 'done' for x in asks):
            reading = sorted((c['path'] for c in versions), key=lambda q: int(q.rsplit('v', 1)[-1]))[-1]
            break
        time.sleep(5)
    took = time.time() - t0
    asks = [(c.get('properties') or {}) for c in kids(base, ws + '/asks')]
    done = sum(1 for x in asks if x.get('/state') == 'done'); working = len(asks) - done
    after = {k: len(kids(base, '/' + node + '/user/' + k)) for k in KINDS}
    things = sum(after[k] - before[k] for k in KINDS)
    # relation records: beneath the standings and the things landed this run, a record whose slots hold a reference
    # under a relation name, a note and a source
    relations, sourced = 0, 0
    seen = set()
    for path, _ in standings:
        if path.endswith('/recipients'):
            continue
        for q, props in walk(base, path):
            if q in seen or q == path:
                continue
            seen.add(q)
            refs = [k for k, v in props.items() if k not in ('source', 'sources', 'same', 'sys') and isinstance(v, str) and v.startswith('/h/')]
            if refs and props.get('note'):
                relations += 1; sourced += 1 if props.get('source') else 0
    for k in KINDS:
        for c in kids(base, '/' + node + '/user/' + k)[before[k]:]:
            for q, props in walk(base, c['path']):
                if q == c['path'] or q in seen:
                    continue
                seen.add(q)
                refs = [kk for kk, v in props.items() if kk not in ('source', 'sources', 'same', 'sys') and isinstance(v, str) and v.startswith('/h/')]
                if refs and props.get('note'):
                    relations += 1; sourced += 1 if props.get('source') else 0
    world = rpc(base, 'read', path='/x' + ws + '/world', care='x').get('properties') or {}
    first, related, sections = 0, 0, []
    if reading:
        secs = kids(base, reading)
        for i, sec in enumerate(sorted(secs, key=lambda c: int((c.get('properties') or {}).get('/order') or 0))):
            name = (sec.get('properties') or {}).get('/name') or ''
            n = len(kids(base, sec['path']))
            sections.append((name, n))
            if i == 0:
                first = n
            if name.lower().startswith('related'):
                related += n
    print()
    print('%-10s %s' % ('took', '%.0f s to the reading' % took if reading else 'no reading within %d s' % a.wait))
    print('%-10s %d  (%s)' % ('things', things, ', '.join('%s +%d' % (k, after[k] - before[k]) for k in KINDS if after[k] - before[k])))
    print('%-10s %d relation records beneath things' % ('relations', relations))
    print('%-10s %s' % ('sourced', ('%d of %d carry a source' % (sourced, relations)) if relations else 'none'))
    print('%-10s %s components, %s islands over %s standings' % ('joined', world.get('/components'), world.get('/islands'), world.get('/standings')))
    print('%-10s %d direct, %d related  (%s)' % ('direct', first, related, '; '.join('%s %d' % s for s in sections)))
    print('%-10s %d asks done, %d still working' % ('settled', done, working))
    return 0 if reading else 1


if __name__ == '__main__':
    sys.exit(main())
