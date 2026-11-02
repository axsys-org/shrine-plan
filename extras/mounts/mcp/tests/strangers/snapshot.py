"""Fingerprint every record under a path with its version: python3 snapshot.py /0x11/user out.json
Diff two fingerprints to prove a world was not restructured: python3 snapshot.py --diff before.json after.json"""
import json, re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from world import W

def walk(root):
    out, nxt = {}, None
    while True:
        r = W.read(root, 'z', limit=500, **({'next': nxt} if nxt else {}))
        def visit(n):
            if n.get('exists'):
                out[n['path']] = {'ref': n.get('reference'), 'props': n.get('properties')}
            for c in n.get('children') or []:
                visit(c)
        visit(r)
        nxt = r.get('next')
        if not nxt:
            return out

def diff(a, b):
    norm = lambda v: re.sub(r'^/h/[xyz]/\d+/\d+', '', str(v))
    gone = [p for p in a if p not in b]
    changed = [p for p in a if p in b and a[p]['ref'] != b[p]['ref']]
    new = [p for p in b if p not in a]
    machinery = lambda p: '/talk/' in p or p.endswith('/mentions') or '/views/' in p
    over = [p for p in changed if not machinery(p) and any(norm(v) != norm(b[p]['props'].get(k)) for k, v in a[p]['props'].items())]
    return {'before': len(a), 'after': len(b), 'removed': gone, 'changed': len(changed), 'overwritten_knowledge': over, 'new': len(new)}

if __name__ == '__main__':
    if sys.argv[1] == '--diff':
        print(json.dumps(diff(json.load(open(sys.argv[2])), json.load(open(sys.argv[3]))), indent=1))
    else:
        snap = walk(sys.argv[1]); json.dump(snap, open(sys.argv[2], 'w')); print(len(snap), 'records')
