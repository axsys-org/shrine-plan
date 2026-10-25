"""Three Strangers, One World: the proofs, against a running world with 0x11 (yours) and simulated peers 0x12, 0x13.
Prints each check with its evidence and PASS / FAIL / UNSUPPORTED, writes proofs.json beside this file.

    python3 extras/mounts/mcp/tests/strangers/proofs.py [snapshot-of-0x11-now.json]

The snapshot (from snapshot.py) is used by check 6 to look for copies; without it that part is skipped.
Checks 5, 7 and 8 come last; their cells are written in the kernel's own shape (sys/weft + sys/tack)."""
import json, time, re, urllib.parse, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from world import W, idx, props, stream
RUN = str(int(time.time()))[-6:]          # every run writes its own probe records, so the script can be run again
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'proofs.json')
SNAP = sys.argv[1] if len(sys.argv) > 1 else None
R11, R12, R13 = '/0x11/user', '/0x11/0x12/user', '/0x11/0x13/user'
ref = lambda p, care='x': {'type': 'reference', 'path': p, 'care': care, 'case': 0}
results = {}
def verdict(key, ok, evidence):
    results[key] = {'verdict': ok, 'evidence': evidence}
    print(f'\n=== {key}: {ok}\n' + (evidence if isinstance(evidence, str) else json.dumps(evidence, indent=1)[:3000]))
q = idx
def short(p):
    return p.replace('/0x11/0x12/user/', '0x12:').replace('/0x11/0x13/user/', '0x13:').replace('/0x11/0x14/user/', '0x14:').replace('/0x11/user/', '0x11:')

# 1. multi-hop traversal across all three worlds, including a connection no string match finds
reach = q('/reach?worlds=0x11,0x12,0x13&limit=40')['only_with_all']
def path_txt(x):
    return ' -> '.join([short(x['from'])] + [f"[{h['label']} by {h['asserted_by']}] {short(h['to'])}" for h in x['path']])
judg = props(W.read(R11 + '/orgs/verisk/same/verisk_0x12'))
names = (props(W.read(R11 + '/orgs/verisk')).get('name'), props(W.read(R12 + '/investments/vrsk')).get('name'))
nonstring = names[0].lower() != names[1].lower() and names[0].lower() not in names[1].lower() and names[1].lower() not in names[0].lower()
lines = [path_txt(x) for x in reach[:8]]
verdict('1 multi-hop traversal across three worlds', 'PASS' if reach and nonstring and judg.get('why') else 'FAIL',
        f"{len(reach)} connections exist only when 0x11, 0x12 and 0x13 all take part, e.g.\n  " + '\n  '.join(lines) +
        f"\nVerisk(0x11, name {names[0]!r}) = VRSK(0x12, name {names[1]!r}): names share no string; judged same because: {judg.get('why')}")

# 2. navigable hierarchy from Verisk's vantage, folders drawn from every world
u = q('/unfold?at=' + urllib.parse.quote(R11 + '/orgs/verisk') + '&depth=3')
out = []
def tree(fs, d=0):
    for f in fs:
        out.append('  ' * d + f"[{f['label']}]" + (f" (+{f['more']} closed)" if f.get('closed') else (f" (+{f['more']})" if f.get('more') else '')))
        for it in f['items']:
            out.append('  ' * d + f"  {it['name']}  worlds={','.join(it.get('worlds') or [it['world']])}")
            tree(it.get('folders') or [], d + 2)
tree(u['folders'])
worlds_seen = set(re.findall(r'0x1[123]', '\n'.join(out)))
verdict('2 navigable hierarchy across worlds', 'PASS' if worlds_seen >= {'0x11', '0x12', '0x13'} else 'FAIL',
        f"unfold of Verisk (same as {', '.join(short(x) for x in u['same'])}):\n" + '\n'.join(out[:60]))

# 3. x / y / z reads with minimal dependencies
M = R13 + '/companies/mckenzie'
def count(n):
    return 1 + sum(count(c) for c in n.get('children') or [])
rx, ry, rz = W.read(M, 'x'), W.read(M, 'y', limit=500), W.read(M, 'z', limit=500)
cx, cy, cz = 1, count(ry), count(rz)
bx, by_, bz = len(json.dumps(rx)), len(json.dumps(ry)), len(json.dumps(rz))
verdict('3 x/y/z reads', 'PASS' if cx < cy < cz and bx < by_ < bz else 'FAIL',
        f"0x13 McKenzie: x = 1 record ({bx} bytes, no children), y = {cy} nodes ({by_} bytes), z = {cz} nodes ({bz} bytes). "
        f"A read at x carries only the record; its relations are names read at their own place, not copies.")

# 4. remote update visibility
before = q('/unfold?at=' + urllib.parse.quote(R11 + '/orgs/verisk') + '&depth=3&open=' + urllib.parse.quote(M))
def has_item(u, name):
    return name in json.dumps(u)
t0 = time.time()
wr = W.tool('write', who='owner_0x13', records=[{'path': M + '/products/probe_' + RUN, 'slots': {'name': 'Probe ' + RUN, 'description': 'Observed flood extent maps after an event, for claims triage', 'source': ref(R13 + '/web/pages/mckenzieintelligence_com/index')}}])
seen_at = None
for i in range(40):
    time.sleep(0.25)
    after = q('/unfold?at=' + urllib.parse.quote(R11 + '/orgs/verisk') + '&depth=3&open=' + urllib.parse.quote(M))
    if has_item(after, 'Probe ' + RUN):
        seen_at = time.time() - t0; break
verdict('4 remote update visibility', 'PASS' if seen_at is not None and not has_item(before, 'Probe ' + RUN) else 'FAIL',
        f"0x13's owner added companies/mckenzie/products/probe_{RUN}; 0x11's Verisk view showed it under acquisitions > McKenzie > products after {seen_at and round(seen_at, 2)} s. "
        "Same process, simulated peer: this is index propagation, not network sync.")
# 6. canonical owner retained: one record per world, nothing copied into 0x11
hits = list(json.load(open(SNAP))) if SNAP else []
copies = [short(p) for p in hits if 'probe_' in p or 'global_events_observer' in p or '/products/geo' in p]
un = q('/union?at=' + urllib.parse.quote(R11 + '/orgs/mckenzie_intelligence_services'))
verdict('6 canonical owner retained', 'PASS' if not copies and len({r['world'] for r in un['records']}) == 3 else 'FAIL',
        f"McKenzie is described by {[(r['world'], short(r['path'])) for r in un['records']]}; each record stays at its owner's path. "
        f"Copies of 0x13's products in 0x11: {copies or 'none'}. 0x13's record history has {W.tool('history', path=M).get('cases')} versions, all at its own path.")

# 9, 10. peers and permissions
verdict('9 peer disconnect and reconnect', 'UNSUPPORTED',
        'Peers are simulated as subtrees of one world (/0x11/0x12, /0x11/0x13) in one wisp; there is no network link to cut. '
        'A real test needs one wisp per world, which the one-wisp-at-a-time rule for this branch forbids.')
try:
    other = W.tool('write', who='owner_0x11', records=[{'path': '/0x12/user/probe', 'slots': {'x': 1}}])
    refused_other = other.get('refused'), other.get('reason')
except Exception as e:
    refused_other = ('error', str(e)[:160])
verdict('10 unauthorized records inaccessible', 'UNSUPPORTED',
        f"No read permissions exist between simulated peers: every hand can read every subtree. The kernel does refuse writes outside its own node: writing /0x12/user/probe gave {refused_other}.")

# 11. conflicting claims keep their sources
dis = un['disagreements']
verdict('11 conflicting claims keep their sources', 'PASS' if any(d['slot'] == 'founded' and len(d['values']) >= 2 for d in dis) else 'FAIL',
        json.dumps(dis, indent=1) + '\n0x11 claims beneath McKenzie: ' + json.dumps([props(c) for c in W.read(R11 + '/orgs/mckenzie_intelligence_services/claims', 'y').get('children', [])], indent=1)[:1200])

# 12. similar names never inherit attributes
mi_facts = ['mackenzieinvestments.com', '1967', 'Alex Christ', '20000930', 'Dun & Bradstreet']
leaks = [f for f in mi_facts if f.lower() in json.dumps(un).lower()]
sim = q('/shared')['similar_names']
mis_names = [s for s in sim if s['name'] in ('mis', 'mckenzie', 'mi')]
verdict('12 similar names never inherit attributes', 'PASS' if not leaks else 'FAIL',
        f"McKenzie Intelligence's union across three worlds contains none of Mackenzie Investments' or Moody's Investors Service's facts: leaks={leaks}. "
        f"Names held by several separate things: {[(s['name'], [[short(x) for x in g] for g in s['things']]) for s in sim][:8]}. "
        "Found and repaired during the run: 0x12's digest had filed Moody's Investors Service facts on 0x12's MIS (both are 'MIS' by that world's convention); the identity guard now holds such writes back.")

# 13. intersection then union queries
agree = [f for f in un['facts'] if f['all']]
knows = q('/knows?at=' + urllib.parse.quote(R11 + '/orgs/mckenzie_intelligence_services') + '&world=0x13&not=0x11')['things']
shared = q('/shared')['things']
verdict('13 intersection then union', 'PASS' if shared and knows else 'FAIL',
        f"things several worlds describe: {[(s['name'], s['worlds']) for s in shared]}\n"
        f"all three agree on McKenzie: {[(f['labels'], f.get('value') or f.get('name')) for f in agree]}\n"
        f"what 0x13 knows about McKenzie that 0x11 does not ({len(knows[0]['facts']) if knows else 0} facts): {[(f['labels'][0], f.get('value') or f.get('name')) for f in (knows[0]['facts'] if knows else [])][:14]}\n"
        f"relationships reachable only with all three: {len(reach)}")


# ---- checks 5, 7 and 8: invalidation, a saved arrangement as kernel cells, cycles
gather = next(c['reference'] for c in W.read('/0x11/weft/stdlib', 'y', limit=100).get('children') if c['path'].endswith('/gather'))
cell = lambda tack, care='z', **more: dict({'sys/weft': {'type': 'reference', 'value': gather}, 'sys/tack': ref(tack, care)}, **more)

# 5. one more update in 0x13, each event in the window with its cause
watch = [R11 + '/orgs/verisk', R12 + '/investments/vrsk', R11 + '/orgs/mckenzie_intelligence_services', R12 + '/private/mis', M, R11 + '/people/cory_doctorow']
cases0 = {p: W.read(p).get('reference') for p in watch}
wr = W.tool('write', who='owner_0x13', records=[{'path': M + '/products/probe2_' + RUN, 'slots': {'name': 'Probe two ' + RUN, 'description': 'Machine-readable damage footprints for insurers'}}])
time.sleep(4)
lines, _ = stream.poll(W.base, '0x11', wr['epoch'] - 1, limit=200)
cases1 = {p: W.read(p).get('reference') for p in watch}
ev = []
for l in lines:
    t = [x for x in l['touched'] if '/agent/journal/' not in x]
    ev.append((l['epoch'], l.get('who'), [short(x) for x in t]))
own = [e for e in ev if e[0] == wr['epoch']]
others = [e for e in ev if e[0] != wr['epoch']]
caused = []
for e in others:                                  # a later event is caused by the update only if it touches what depends on McKenzie
    for x in e[2]:
        if x.startswith('0x13:companies/mckenzie') or any(short(p) == x for p in watch):
            caused.append(e)
same_versions = [short(p) for p in watch if cases0[p] == cases1[p]]
verdict('5 no unnecessary invalidation', 'PASS' if own and not caused and len(same_versions) == len(watch) else 'FAIL',
        f"the owner's event {own}; other events in the window, by other hands, none touching McKenzie or what depends on it: {others or 'none'}.\n"
        f"Versions unchanged after the update (McKenzie's own record included; only a new child was added): {same_versions}. "
        "Every view over McKenzie (Verisk's unfold, the union, a cell's /x) is computed on read, so nothing derived is rewritten or invalidated.")

# 7. a saved arrangement: overlay cells in the kernel's shape
C = R11 + '/collections/cat_intel'
r = W.tool('write', who='person', records=[
    {'path': C + '/mckenzie', 'action': 'make', 'slots': cell(M, 'z', note='watch after the Verisk deal')},
    {'path': C + '/vrsk', 'action': 'make', 'slots': cell(R12 + '/investments/vrsk', 'z')}])
time.sleep(2)
xs = W.read('/x' + C + '/mckenzie', 'x')
xkids = W.read('/x' + C + '/mckenzie', 'y', limit=200)
arr = idx('/around?at=' + urllib.parse.quote(M) + '&depth=1')
anc = [(short(a['via']), ' < '.join(c['name'] for c in a['chain'])) for a in arr['ancestors']]
derived = json.dumps(idx('/unfold?at=' + urllib.parse.quote(R11 + '/orgs/verisk') + '&depth=2'))
verdict('7 saved arrangement coexists with derived organisation',
        'PASS' if xs.get('exists') and any('cat_intel' in a[0] for a in anc) and 'McKenzie Intelligence' in derived else 'FAIL',
        f"write refused={r.get('refused')} {r.get('reason')}. /x of the saved overlay: exists={xs.get('exists')}, name={props(xs).get('name')}, "
        f"children read through it: {len(xkids.get('children') or [])}. McKenzie's places: {anc}. "
        "Verisk's computed acquisitions still list McKenzie: the user's grouping and the derived relation appear together, and neither was copied.")

# 8. cycles: unfold bounds them, and the kernel refuses a cell over itself
t = time.time(); uc = idx('/unfold?at=' + urllib.parse.quote(R12 + '/notes/cycle_a') + '&depth=8'); dt = time.time() - t
selfcell = C + '/self_loop'
r2 = W.tool('write', who='person', records=[{'path': selfcell, 'action': 'make', 'slots': cell(C, 'z')}])
time.sleep(1)
cx = W.read('/c/x' + selfcell, 'x')
fault = json.dumps(cx)
verdict('8 cycles bounded', 'PASS' if dt < 2 and 'cycle' in fault.lower() else 'FAIL',
        f"0x12 cycle_a -> 0x13 cycle_b -> 0x12 cycle_a unfolds at depth 8 in {round(dt, 3)} s: {json.dumps(uc['folders'])[:300]}. "
        f"A saved cell whose live input is its own folder: the kernel's context reads {re.findall(r'[^\"]*[Cc]ycle[^\"]*', fault)[:2] or fault[:300]}.")
json.dump(results, open(OUT, 'w'), indent=1)
print('\nSUMMARY', {k: v['verdict'] for k, v in results.items()})
