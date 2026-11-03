"""Phase-0 gate (run from any directory; needs the shrine-mesa binary built at BIN and no wisp running): two worlds, the shrine-mesa sidecars, and the net mount's stale overlay flipping.

World A (0x11) publishes /0x11/pub/aluminum through the publisher sidecar; world B (0x12, with the net mount)
acquires it through the reader sidecar at /0x12/net/names/0x11/aluminum/current. A judgment is recorded as
/seen at the acquired case; the next revision in A must make /x/0x12/net/stale list the name; a kill -9 of B's
runtime must not lose that; re-judging must clear it.
"""
import json, os, shutil, signal, subprocess, sys, tempfile, time, urllib.request, urllib.error

BASE = '/Users/ianchanner/shrine-base'
BIN = '/Users/ianchanner/shrine-mesa/target/debug/shrine-mesa'
TEMP = tempfile.mkdtemp(prefix='phase0-', dir=os.path.join(BASE, '.check'))
report, logs = {}, []

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
    def case_of(self, path):
        ref = self.rpc('read', path=path, care='x')['reference']; return int(ref.split('/')[3])
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

def guard(worlds):
    for w in worlds:
        if w.wisp and w.rss_mb() > 3500: raise SystemExit(f'{w.node} over 3.5 GB')
    if shutil.disk_usage('/').free < 3 * 2**30: raise SystemExit('free disk under 3 GB')

def wait_for(what, pred, timeout=90):
    t = time.monotonic()
    while time.monotonic() - t < timeout:
        v = pred()
        if v: return v, round(time.monotonic() - t, 2)
        time.sleep(0.1)
    raise SystemExit(f'timed out waiting for {what}')

def stale_children(b):
    s = b.rpc('read', path='/x/0x12/net/stale', care='y')
    out = []
    for pub in s.get('children', []):
        for kid in pub.get('children', []): out.append((kid['path'], kid.get('properties', {})))
    return out

if subprocess.run(['pgrep', '-x', 'wisp'], capture_output=True).returncode == 0: raise SystemExit('a wisp is already running')
A = World('0x11', 8301, ['mcp', 'probe']); B = World('0x12', 8302, ['net', 'mcp', 'probe']); worlds = [A, B]; procs = []
try:
    report['boot_A_s'] = A.boot(); log(f'A up in {report["boot_A_s"]} s')
    report['boot_B_s'] = B.boot(); log(f'B up in {report["boot_B_s"]} s'); guard(worlds)
    ka, kb = os.path.join(TEMP, 'a.seed'), os.path.join(TEMP, 'b.seed')
    pa = subprocess.run([BIN, 'keygen', ka], capture_output=True, text=True, check=True).stdout.strip()
    pb = subprocess.run([BIN, 'keygen', kb], capture_output=True, text=True, check=True).stdout.strip()
    A.rpc('write', who='owner', records=[{'path': '/0x11/pub/aluminum', 'slots': {'price': '8.50', 'available': '400 kg', 'unit': 'kg'}}])
    case1 = A.case_of('/0x11/pub/aluminum'); log(f'A revision 1 at case {case1}')
    def peering(me, key, listen, flow, peer, peer_key, peer_addr, peer_flow, state):
        return ['--id', me, '--key', key, '--listen', listen, '--flow-listen', flow, '--peer', peer, '--peer-key', peer_key,
                '--peer-addr', peer_addr, '--peer-flow-addr', peer_flow, '--state', state]
    ra, fa, rb, fb = '127.0.0.1:9311', '127.0.0.1:9321', '127.0.0.1:9312', '127.0.0.1:9322'
    pub = subprocess.Popen([BIN, 'publisher', '--world', A.url, '--path', '/0x11/pub/aluminum', '--name', 'aluminum', '--poll-ms', '200',
                            *peering('0x11', ka, ra, fa, '0x12', pb, rb, fb, os.path.join(TEMP, 'state-a'))],
                           stdout=open(os.path.join(TEMP, 'publisher.log'), 'w'), stderr=subprocess.STDOUT); procs.append(pub)
    rd = subprocess.Popen([BIN, 'reader', '--world', B.url, '--publisher', '0x11',
                           *peering('0x12', kb, rb, fb, '0x11', pa, ra, fa, os.path.join(TEMP, 'state-b'))],
                          stdout=open(os.path.join(TEMP, 'reader.log'), 'w'), stderr=subprocess.STDOUT); procs.append(rd)
    cur = lambda: B.rpc('read', path='/0x12/net/names/0x11/aluminum/current', care='x')
    acquired = lambda c: (lambda: (cur().get('properties', {}).get('/remote_case') == str(c)) and cur())
    _, s = wait_for('revision 1 in B', acquired(case1)); report['acquire_1_s'] = s; log(f'B acquired case {case1} in {s} s')
    B.rpc('write', who='agent', records=[{'path': '/0x12/net/names/0x11/aluminum/seen', 'slots': {'remote_case': case1}}])
    st = stale_children(B); log(f'stale after judging at {case1}: {st}'); assert st == [], st
    t0 = time.monotonic()
    A.rpc('write', who='owner', records=[{'path': '/0x11/pub/aluminum', 'action': 'poke', 'slots': {'price': '9.60', 'available': '150 kg'}}])
    case2 = A.case_of('/0x11/pub/aluminum'); log(f'A revision 2 at case {case2}')
    _, s = wait_for('revision 2 in B', acquired(case2)); report['acquire_2_s'] = s
    flipped, s2 = wait_for('stale to list the name', lambda: stale_children(B) or None, 30)
    report['stale_flip_after_A_write_s'] = round(time.monotonic() - t0, 2)
    log(f'stale after A moved to {case2}: {flipped}')
    assert flipped[0][0] == '/x/0x12/net/stale/0x11/aluminum' and flipped[0][1]['/current'] == str(case2) and flipped[0][1]['/seen'] == str(case1), flipped
    guard(worlds)
    B.kill9(); log('kill -9 B'); report['restart_B_s'] = B.boot(); log(f'B restarted in {report["restart_B_s"]} s')
    st = stale_children(B); log(f'stale after restart: {st}'); assert st and st[0][1]['/current'] == str(case2), st
    B.rpc('write', who='agent', records=[{'path': '/0x12/net/names/0x11/aluminum/seen', 'action': 'poke', 'slots': {'remote_case': case2}}])
    st = stale_children(B); log(f'stale after re-judging at {case2}: {st}'); assert st == [], st
    report['rss_mb'] = {'A': A.rss_mb(), 'B': B.rss_mb()}
    log('PHASE 0 GATE PASSED ' + json.dumps(report))
finally:
    for p in procs:
        if p.poll() is None: p.terminate()
    for w in worlds: w.stop()
    time.sleep(2); subprocess.run(['pkill', '-x', 'wisp'])
    print('logs kept at', TEMP if '--keep' in sys.argv else '(deleted)')
    if '--keep' not in sys.argv: shutil.rmtree(TEMP, ignore_errors=True)
