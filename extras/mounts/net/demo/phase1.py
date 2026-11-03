"""Phase-1 gate: 500 revisions under random kills, none lost or duplicated.

World A (0x11) publishes /0x11/pub/aluminum through a publication record; world B (0x12) acquires it at
/0x12/net/names/0x11/aluminum/current. One shrine-mesa service runs beside each world. Across the run the
script kills, with -9 and at random points, A's runtime, B's runtime, A's service and B's service, and
restarts each from the same directory; bursts of revisions are written while a service is down. At the end
the acquired record's history in B must hold exactly A's cases, once each and in order.

Run from the shrine-base checkout:  python3 extras/mounts/net/demo/phase1.py [--revisions N] [--seed S] [--keep]
"""
import json, os, random, shutil, signal, subprocess, sys, tempfile, time, urllib.error, urllib.request

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
BIN = os.environ.get('SHRINE_MESA', '/Users/ianchanner/shrine-mesa/target/debug/shrine-mesa')
TEMP = tempfile.mkdtemp(prefix='phase1-', dir=os.path.join(BASE, '.check'))
ARGS = sys.argv[1:]
def arg(flag, default):
    return type(default)(ARGS[ARGS.index(flag) + 1]) if flag in ARGS else default
REVISIONS, SEED, KILLS = arg('--revisions', 500), arg('--seed', 1), arg('--kills', 20)
report, logs = {'revisions': REVISIONS, 'seed': SEED}, []

def log(s):
    print(s, flush=True); logs.append(s)

class World:
    def __init__(self, node, port, mounts):
        self.node, self.port, self.mounts = node, port, mounts
        self.url = f'http://127.0.0.1:{port}'
        self.dir = os.path.join(TEMP, node); self.launcher = self.wisp = None; self.boots = 0
    def boot(self):
        self.boots += 1
        logp = os.path.join(TEMP, f'launcher-{self.node}-{self.boots}.log'); out = open(logp, 'w')
        env = dict(os.environ); env.pop('_EDEN_NIX_ROOT', None)
        cmd = [sys.executable, 'x/eden', '--node', self.node, *sum([['--mount', m] for m in self.mounts], []),
               '--port', str(self.port), '--world', self.dir, '--startup-timeout', '1500']
        self.launcher = subprocess.Popen(cmd, cwd=BASE, stdout=out, stderr=out, env=env)
        t = time.monotonic()
        while time.monotonic() - t < 1500:
            text = open(logp, errors='replace').read()
            if self.launcher.poll() is not None: raise SystemExit(f'{self.node} launcher exited: {text[-1500:]}')
            if 'Eden: http://' in text:
                try:
                    self.rpc('read', path='/' + self.node, care='x'); break
                except Exception: pass
            time.sleep(0.5)
        else: raise SystemExit(f'{self.node} startup timed out')
        kids = subprocess.run(['pgrep', '-P', str(self.launcher.pid), '-x', 'wisp'], capture_output=True, text=True).stdout.split()
        self.wisp = int(kids[0]); return round(time.monotonic() - t, 1)
    def rpc(self, name, **args):
        body = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'mcp/' + name, 'arguments': args}}).encode()
        with urllib.request.urlopen(urllib.request.Request(self.url + '/mcp', body, {'Content-Type': 'application/json'}), timeout=120) as r:
            reply = json.load(r)
        res = reply['result']
        if res.get('isError'): raise RuntimeError(str(res)[:400])
        return res['structuredContent']
    def rpc_retry(self, name, timeout=120, **args):
        """The same call, retried while the world is down (its runtime was killed and is restarting)."""
        t = time.monotonic()
        while True:
            try: return self.rpc(name, **args)
            except (urllib.error.URLError, ConnectionError, OSError) as e:
                if time.monotonic() - t > timeout: raise
                time.sleep(0.5)
    def case_of(self, path):
        ref = self.rpc_retry('read', path=path, care='x')['reference']; return int(ref.split('/')[3])
    def kill9(self):
        os.kill(self.wisp, signal.SIGKILL); self.launcher.wait(timeout=60)
    def stop(self):
        if self.launcher and self.launcher.poll() is None:
            self.launcher.terminate()
            try: self.launcher.wait(timeout=30)
            except subprocess.TimeoutExpired: self.launcher.kill()
    def rss_mb(self):
        out = subprocess.run(['ps', '-o', 'rss=', '-p', str(self.wisp)], capture_output=True, text=True).stdout.strip()
        return int(out) // 1024 if out else 0

class Service:
    """One shrine-mesa service beside one world, restartable from its state directory."""
    def __init__(self, tag, config):
        self.tag, self.proc, self.starts = tag, None, 0
        self.config_path = os.path.join(TEMP, f'service-{tag}.json')
        json.dump(config, open(self.config_path, 'w'), indent=1)
    def start(self):
        self.starts += 1
        out = open(os.path.join(TEMP, f'service-{self.tag}-{self.starts}.log'), 'w')
        self.proc = subprocess.Popen([BIN, 'serve', '--config', self.config_path], stdout=out, stderr=subprocess.STDOUT)
    def kill9(self):
        self.proc.send_signal(signal.SIGKILL); self.proc.wait(timeout=30)
    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try: self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired: self.proc.kill()
    def alive(self): return self.proc is not None and self.proc.poll() is None

def service_config(world, me, key, listen, flow, state, peer, peer_key, peer_addr, peer_flow):
    return {'world': world.url, 'id': me, 'key': key, 'listen': listen, 'flow_listen': flow, 'state': state, 'poll_ms': 200,
            'peers': [{'id': peer, 'key': peer_key, 'addr': peer_addr, 'flow_addr': peer_flow}]}

def guard(worlds):
    for w in worlds:
        if w.wisp and w.rss_mb() > 3500: raise SystemExit(f'{w.node} over 3.5 GB')
    if shutil.disk_usage('/').free < 3 * 2**30: raise SystemExit('free disk under 3 GB')

def wait_for(what, pred, timeout=120):
    t = time.monotonic()
    while time.monotonic() - t < timeout:
        v = pred()
        if v: return v, round(time.monotonic() - t, 2)
        time.sleep(0.1)
    raise SystemExit(f'timed out waiting for {what}')

def acquired_case(b):
    try:
        rec = b.rpc('read', path='/0x12/net/names/0x11/aluminum/current', care='x')
    except (urllib.error.URLError, ConnectionError, OSError):
        return 0
    return int(rec.get('properties', {}).get('/remote_case', 0) or 0)

if subprocess.run(['pgrep', '-x', 'wisp'], capture_output=True).returncode == 0: raise SystemExit('a wisp is already running')
if not os.path.exists(BIN): raise SystemExit(f'no sidecar binary at {BIN}')
rng = random.Random(SEED)
A = World('0x11', 8301, ['net', 'mcp', 'probe']); B = World('0x12', 8302, ['net', 'mcp', 'probe']); worlds = [A, B]; services = []
try:
    report['boot_A_s'] = A.boot(); log(f'A up in {report["boot_A_s"]} s')
    report['boot_B_s'] = B.boot(); log(f'B up in {report["boot_B_s"]} s'); guard(worlds)
    ka, kb = os.path.join(TEMP, 'a.seed'), os.path.join(TEMP, 'b.seed')
    pa = subprocess.run([BIN, 'keygen', ka], capture_output=True, text=True, check=True).stdout.strip()
    pb = subprocess.run([BIN, 'keygen', kb], capture_output=True, text=True, check=True).stdout.strip()
    A.rpc('write', who='owner', records=[{'path': '/0x11/pub/aluminum', 'slots': {'price': '8.50', 'available': '400 kg', 'rev': 1}}])
    A.rpc('write', who='owner', records=[{'path': '/0x11/net/publications/aluminum', 'slots': {'path': '/0x11/pub/aluminum', 'to': '0x12'}}])
    ra, fa, rb, fb = '127.0.0.1:9311', '127.0.0.1:9321', '127.0.0.1:9312', '127.0.0.1:9322'
    SA = Service('a', service_config(A, '0x11', ka, ra, fa, os.path.join(TEMP, 'state-a'), '0x12', pb, rb, fb))
    SB = Service('b', service_config(B, '0x12', kb, rb, fb, os.path.join(TEMP, 'state-b'), '0x11', pa, ra, fa))
    services = [SA, SB]; SA.start(); SB.start()
    _, s = wait_for('revision 1 in B', lambda: acquired_case(B) == 1); report['acquire_1_s'] = s; log(f'B acquired case 1 in {s} s')

    # The kill schedule: KILLS events at distinct revision numbers, each one of four kinds; a burst of
    # revisions is written while a service is down so reconciliation and pending deliveries are exercised.
    kinds = ['world A', 'world B', 'service A', 'service B']
    schedule = {r: kinds[i % 4] for i, r in enumerate(sorted(rng.sample(range(2, REVISIONS - 5), KILLS)))}
    report['kills'] = {k: sum(1 for v in schedule.values() if v == k) for k in kinds}
    restarts, t_run, down = [], time.monotonic(), None
    for rev in range(2, REVISIONS + 1):
        A.rpc_retry('write', who='owner', records=[{'path': '/0x11/pub/aluminum', 'action': 'poke', 'slots': {'price': f'{rev / 100:.2f}', 'rev': rev}}])
        kind = schedule.get(rev)
        if kind == 'world A':
            A.kill9(); t = A.boot(); restarts.append((kind, t)); log(f'rev {rev}: kill -9 {kind}, back in {t} s')
        elif kind == 'world B':
            B.kill9(); t = B.boot(); restarts.append((kind, t)); log(f'rev {rev}: kill -9 {kind}, back in {t} s')
        elif kind in ('service A', 'service B'):
            svc = SA if kind == 'service A' else SB
            svc.kill9(); down = (svc, rev + 3); log(f'rev {rev}: kill -9 {kind}; three revisions while it is down')
        if down and rev >= down[1]:
            down[0].start(); log(f'rev {rev}: {down[0].tag} service restarted'); down = None
        if rev % 50 == 0:
            guard(worlds); log(f'rev {rev}: A case {A.case_of("/0x11/pub/aluminum")}, B acquired {acquired_case(B)}')
        for svc in services:
            if svc is not (down and down[0]) and not svc.alive(): raise SystemExit(f'service {svc.tag} died: see service-{svc.tag}-{svc.starts}.log')
    if down: down[0].start(); down = None
    final = A.case_of('/0x11/pub/aluminum'); log(f'all revisions written; A at case {final}')
    _, s = wait_for('the last revision in B', lambda: acquired_case(B) == final, 300); report['drain_s'] = s
    report['run_s'] = round(time.monotonic() - t_run, 1); report['restarts'] = restarts
    guard(worlds)

    # Ground truth: every case of A's record (pinned reads), and every case of B's acquired record.
    a_cases = []
    for k in range(1, final + 1):
        props = A.rpc('read', path='/0x11/pub/aluminum', care='x', case=k).get('properties', {})
        a_cases.append((k, props.get('/rev')))
    b_total = B.case_of('/0x12/net/names/0x11/aluminum/current')
    b_cases = []
    for k in range(1, b_total + 1):
        props = B.rpc('read', path='/0x12/net/names/0x11/aluminum/current', care='x', case=k).get('properties', {})
        b_cases.append((int(props.get('/remote_case', 0)), props.get('/rev')))
    report['a_cases'], report['b_cases'] = len(a_cases), len(b_cases)
    lost = [k for k, _ in a_cases if k not in {c for c, _ in b_cases}]
    dup = [c for c in {c for c, _ in b_cases} if sum(1 for x, _ in b_cases if x == c) > 1]
    order_ok = [c for c, _ in b_cases] == sorted(c for c, _ in b_cases)
    mismatched = [(c, r) for c, r in b_cases if dict(a_cases).get(c) != r]
    log(f'A cases {len(a_cases)}, B acquired {len(b_cases)}; lost {lost[:10]}, duplicated {dup[:10]}, in order {order_ok}, slot mismatches {mismatched[:5]}')
    assert not lost and not dup and order_ok and not mismatched and len(b_cases) == len(a_cases), 'the gate failed'
    report['rss_mb'] = {'A': A.rss_mb(), 'B': B.rss_mb()}
    log('PHASE 1 GATE PASSED ' + json.dumps(report))
finally:
    for svc in services: svc.stop()
    for w in worlds: w.stop()
    time.sleep(2); subprocess.run(['pkill', '-x', 'wisp'])
    print('logs kept at', TEMP if '--keep' in ARGS else '(deleted)')
    if '--keep' not in ARGS: shutil.rmtree(TEMP, ignore_errors=True)
