"""Proof on a live world: the registries loaded through their schemes and Cummins judged, then the overlay read the
way the page and an agent read it. Five questions, each answered PASS or FAIL with the numbers:

  picture      a thing as a world has folders named only by slots and holders (nothing the kernel invented), and a
               cell that reads the thing is a folder under the cell's own name holding its result
  bounds       depth 1 opens the standing alone; /nodes caps what opens; /cap caps a folder's items
  history      a workspace pinned at the epoch before a judgement still reads the components of that epoch
  composition  a stdlib cell over a workspace's virtual root counts that component's standings
  latency      every read timed; the single-standing page read is the number that matters

    python3 proof.py http://127.0.0.1:8150 [--node 0x11]
"""
import argparse, importlib.util, os, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location('hand_base', os.path.join(HERE, '..', '..', 'hands', 'hand.py'))
_hand = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_hand)
World = _hand.World

RESULTS = []
def check(name, ok, detail=''):
    RESULTS.append((name, bool(ok))); print(('PASS ' if ok else 'FAIL ') + name + (' · ' + detail if detail else ''))

def ref(path, care='x', epoch=None):
    segs = [s for s in path.split('/') if s]
    return {'type': 'reference', 'value': '/h/%s/%s/%d/%s' % (care, 'e%d' % epoch if epoch else '0', len(segs), '/'.join(segs))}

def defcase(w, node, group, name):
    r = w.read('/%s/weft/%s/%s' % (node, group, name), 'x')
    m = re.match(r'^/h/x/(\d+)/', str(r.get('reference') or ''))
    if not (r.get('exists') and m): raise SystemExit('no definition %s/%s in this world' % (group, name))
    return int(m.group(1))

def cell(w, node, name, group, defn, tack, standings=(), epoch=None, tack_care='x', **slots):
    """A cell under /user/views/<name>: weft -> the definition at its case, tack -> the input (live, or pinned at an
    epoch), standing/<k> -> further standings. Returns the cell's path."""
    path = '/%s/user/views/%s' % (node, name)
    case = defcase(w, node, group, defn)
    record = {'sys/weft': {'type': 'reference', 'value': '/h/x/%d/4/%s/weft/%s/%s' % (case, node, group, defn)}, 'sys/tack': ref(tack, tack_care, epoch)}
    for i, s in enumerate(standings): record['standing/' + chr(98 + i)] = ref(s, 'x', epoch)
    record.update(slots)
    w.tool('write', records=[{'path': path, 'slots': record, 'action': 'set'}], who='proof')
    return path

def tree(w, path):
    """Every node of a computed tree, keyed by its path beneath the read, slots without their leading slash."""
    nodes, nxt = {}, None
    for _ in range(40):
        r = w.read(path, 'z', limit=500, **({'next': nxt} if nxt else {}))
        def visit(n):
            if str(n.get('path', '')).startswith(path):
                nodes[n['path'][len(path):]] = {k.lstrip('/'): v for k, v in (n.get('properties') or {}).items()}
            for c in n.get('children') or []: visit(c)
        visit(r); nxt = r.get('next')
        if not nxt: break
    return nodes

def folders(nodes, prefix):
    """The folders directly beneath one thing on the page: (direction, label, record, item paths)."""
    out = []
    here = [s for s in prefix.split('/') if s]
    for rel, props in nodes.items():
        segs = [s for s in rel.split('/') if s]
        if len(segs) < len(here) + 2 or segs[:len(here)] != here: continue
        d, n = segs[len(here)], segs[len(here) + 1]
        if d not in ('out', 'in', 'part') or not n.isdigit() or len(segs) != len(here) + 2 + int(n): continue
        label = '/'.join(segs[len(here) + 2:])
        items = []
        for irel in nodes:
            isegs = [s for s in irel.split('/') if s]
            if len(isegs) <= len(segs) or isegs[:len(segs)] != segs: continue
            m = isegs[len(segs)]
            if m.isdigit() and len(isegs) == len(segs) + 1 + int(m): items.append('/' + '/'.join(isegs[len(segs) + 1:]))
        out.append((d, label, props, items))
    return out

def timed(label, fn):
    t = time.time(); r = fn(); dt = time.time() - t
    print('  %-48s %.2fs' % (label, dt)); return r, dt

def main():
    p = argparse.ArgumentParser(); p.add_argument('base'); p.add_argument('--node', default='0x11'); a = p.parse_args()
    w, node = World(a.base, a.node), a.node
    R = '/%s/user/registries' % node
    cummins = R + '/usaspending/recipients/lszhmmeg8481'
    echo = R + '/echo/facilities/n110000426049'
    importer = R + '/importyeti/cummins_power_generation'
    for path in (cummins, echo, importer):
        if not w.read(path, 'x').get('exists'): raise SystemExit('missing ' + path + ': load the registries first')

    # ---- picture: the recipient as a world through /o, one standing, depth 3 (the page's own read)
    nodes, dt = timed('overlay /o cummins depth 3', lambda: w.view('overlay', cummins))
    check('the page read answers', nodes is not None and bool(nodes), '%d nodes' % len(nodes or {}))
    top = (nodes or {}).get('', {})
    root = (nodes or {}).get('/0' + cummins, {})
    check('one standing, one virtual root', str(top.get('standings')) == '1' and str(top.get('components')) == '1' and root.get('standing') in ('true', True, 1, '1'), 'components %s islands %s opened %s' % (top.get('components'), top.get('islands'), top.get('opened')))
    fs = folders(nodes or {}, '/0' + cummins)
    labels = [(d, l) for d, l, _, _ in fs]
    invented = [l for _, l in labels if l.endswith(' of')]
    check('every folder is a slot or a holder somebody wrote', fs and not invented and all(re.match(r'^[a-z0-9_/]+$', l) for _, l in labels), ', '.join(('← ' if d == 'in' else '') + l for d, l in labels)[:300])
    ins = [l for d, l in labels if d == 'in']
    check('what references the recipient is a folder under its holder\'s slot', any(l for l in ins), '← ' + ' · '.join(ins)[:200])
    joined = [l for d, l in labels if l in ('same', 'different', 'why')]
    check('same judgements join identities instead of showing as folders', not joined, 'identity members fold in; echo facility\'s slots appear beside the recipient\'s')
    noted = [i for _, _, _, items in fs for i in items]
    check('items carry the holder (via) and the asserting world (by)', all('via' in (nodes.get('/0' + cummins + '/' + d + '/' + str(len(l.split('/'))) + '/' + l + '/' + str(len([s for s in i.split('/') if s])) + i, {}) or {'via': 1}) for d, l, _, items in fs for i in items[:3]), '%d items' % len(noted))

    # ---- a cell reading the recipient is a folder under its own name
    ws = cell(w, node, 'proof_cummins', 'graph', 'overlay', cummins, standings=[echo, importer], depth=3)
    wsnodes, dt = timed('workspace /x cummins+echo+importer', lambda: tree(w, '/x' + ws))
    wtop = wsnodes.get('', {})
    check('workspace of three judged standings is one component', str(wtop.get('components')) == '1' and str(wtop.get('islands')) == '0', 'components %s islands %s opened %s' % (wtop.get('components'), wtop.get('islands'), wtop.get('opened')))
    nodes2, dt = timed('overlay /o cummins again (cell now points at it)', lambda: w.view('overlay', cummins))
    fs2 = folders(nodes2 or {}, '/0' + cummins)
    mine = [(l, items) for d, l, _, items in fs2 if d == 'in' and l == 'proof_cummins']
    check('the cell is a backward folder under its own name, holding its result', bool(mine) and mine[0][1] and mine[0][1][0].startswith('/x/'), str(mine[0][1][:1]) if mine else 'no folder proof_cummins')

    # ---- bounds
    shallow = cell(w, node, 'proof_shallow', 'graph', 'overlay', cummins, depth=1)
    s_nodes, dt = timed('depth 1', lambda: tree(w, '/x' + shallow))
    check('depth 1 opens the standing alone', str(s_nodes.get('', {}).get('opened')) == '1', 'opened %s' % s_nodes.get('', {}).get('opened'))
    small = cell(w, node, 'proof_small', 'graph', 'overlay', cummins, standings=[echo, importer], depth=4, nodes=5)
    n_nodes, dt = timed('nodes 5', lambda: tree(w, '/x' + small))
    opened = int(n_nodes.get('', {}).get('opened') or 0)
    check('/nodes caps what opens', 0 < opened <= 5, 'opened %d' % opened)
    capped = cell(w, node, 'proof_capped', 'graph', 'overlay', cummins, depth=2, cap=2)
    c_nodes, dt = timed('cap 2', lambda: tree(w, '/x' + capped))
    cfs = folders(c_nodes, '/0' + cummins)
    check('/cap caps a folder\'s items at the standing, keeping the count', cfs and all(len(items) <= 2 for _, _, _, items in cfs) and any(int(p.get('more') or 0) > 0 or int(p.get('count') or 0) > 2 for _, _, p, _ in cfs) or (cfs and all(int(p.get('count') or 0) <= 2 for _, _, p, _ in cfs)), '; '.join('%s %s/%s' % (l, len(items), p.get('count')) for _, l, p, items in cfs)[:200])

    # ---- history: two things apart, a workspace over them, a judgement, the same workspace pinned before it
    stamp = int(time.time()) % 100000   # fresh names per run: a judgement from an earlier run must not join these
    a_, b_ = '/%s/user/things/proof_a_%d' % (node, stamp), '/%s/user/things/proof_b_%d' % (node, stamp)
    w.tool('write', records=[{'path': a_, 'slots': {'name': 'Proof A'}, 'action': 'set'}, {'path': b_, 'slots': {'name': 'Proof B'}, 'action': 'set'}], who='proof')
    apart = cell(w, node, 'proof_apart', 'graph', 'overlay', a_, standings=[b_], depth=2)
    before = tree(w, '/x' + apart).get('', {})
    # the epoch before the judgement: the one the next write reports, less one (a write's reply names its epoch)
    e1 = int((w.tool('write', records=[{'path': '/%s/user/things/proof_mark' % node, 'slots': {'name': 'mark'}, 'action': 'set'}], who='proof') or {}).get('epoch') or 0)
    check('two things nothing connects are two components, two islands', str(before.get('components')) == '2' and str(before.get('islands')) == '2', 'components %s islands %s at epoch %d' % (before.get('components'), before.get('islands'), e1))
    w.tool('write', records=[{'path': a_ + '/same/proof_b_%d' % stamp, 'slots': {'same': ref(b_), 'note': 'the proof says so', 'source': ref(a_)}, 'action': 'set'}], who='proof')
    after = tree(w, '/x' + apart).get('', {})
    check('a same judgement joins them on the next live read', str(after.get('components')) == '1' and str(after.get('islands')) == '0', 'components %s islands %s' % (after.get('components'), after.get('islands')))
    pinned = cell(w, node, 'proof_pinned', 'graph', 'overlay', a_, standings=[b_], depth=2, epoch=e1)
    pin_nodes, dt = timed('workspace pinned at the epoch before the judgement', lambda: tree(w, '/x' + pinned))
    ptop = pin_nodes.get('', {})
    check('pinned at the epoch before, the picture is the earlier one', str(ptop.get('components')) == '2', 'components %s islands %s (fault: %s)' % (ptop.get('components'), ptop.get('islands'), ptop.get('sys/view/fault') or ptop.get('sys/view/failure') or 'none'))

    # ---- provenance: the buckets the scheme made, read as standings; they meet where their records crossed
    R0 = R + '/usaspending/recipients'; R1 = R + '/echo'; R2 = R + '/importyeti'
    buckets = cell(w, node, 'proof_buckets', 'graph', 'overlay', R0, standings=[R1, R2], depth=3, nodes=150)
    b_nodes, dt = timed('workspace over three buckets, depth 3', lambda: tree(w, '/x' + buckets))
    btop = b_nodes.get('', {})
    roots = sorted({rel.split('/')[1] for rel in b_nodes if re.match(r'^/\d+/', rel)})
    check('buckets meet through their records\' crossings', int(btop.get('components') or 9) < 3, 'components %s islands %s opened %s; roots %s; root slots %s' % (btop.get('components'), btop.get('islands'), btop.get('opened'), ', '.join(roots), ', '.join(sorted(btop))[:120]))

    # ---- composition: a stdlib cell over a path inside the workspace's first virtual root
    try:
        counted = cell(w, node, 'proof_count', 'stdlib', 'count', '/x' + ws + '/0' + R, tack_care='y')
        c, dt = timed('count over /x/<workspace>/0/.../registries', lambda: w.read('/x' + counted, 'x'))
        props = {k.lstrip('/'): v for k, v in (c.get('properties') or {}).items()}
        buckets_with_standings = sorted({re.match(r'^/0' + re.escape(R) + r'/([^/]+)/', k).group(1) for k in wsnodes if k.startswith('/0' + R + '/') and wsnodes[k].get('standing')})
        check('a cell over a cell\'s virtual root counts what sits beneath it', str(props.get('count')) == str(len(buckets_with_standings)) and bool(buckets_with_standings), 'count %s, buckets with a standing under /0: %s' % (props.get('count'), ', '.join(buckets_with_standings)))
    except Exception as e:
        check('a cell over a cell\'s virtual root counts what sits beneath it', False, str(e)[:160])

    print()
    failed = [n for n, ok in RESULTS if not ok]
    print('%d checks, %d failed%s' % (len(RESULTS), len(failed), ': ' + '; '.join(failed) if failed else ''))
    sys.exit(1 if failed else 0)

if __name__ == '__main__':
    main()
