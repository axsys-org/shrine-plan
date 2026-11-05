"""The relationship gate, against the shrine-mesa host.

--wake-only   the generic wake mechanism with the stub agent: an agent-declared wake fires on a time passing, on
              an event beneath a referenced name by an outside principal, and on an ask cell asking again; nothing
              fires for the agent's own writes, an unrelated relationship or a culled wake; every run is recorded;
              a wake declared before a kill -9 fires after the restart. One world. No domain words anywhere.

(default)     the relationship before and after adoption, through the mail gateway (an ordinary Mesa peer: its own
              hosted world, its own sidecar, and `shrine-mesa gateway` on the directory transport), with the inbox
              fixture playing Precision Works by dropping reply files into the gateway's inbox, and the gate itself
              writing what the agent would write (deterministic; the real agent runs in the recording): a request
              under /our/<gateway>/requests is published once the standing approval covers it; the gateway
              acquires it, sends, and publishes the result, acquired at /her/<gateway>/results; the reply arrives as
              the gateway's inbound, acquired at /her/<gateway>/inbound, and the host files it as an interaction of
              the relationship by the request it answers, written as the gateway with a source reference;
              observations cite it; a counter-offer goes out on the same thread and is answered; the judgment cell
              beside the folder is answered; proposals are written into the peer's prospective world through a
              scoped token; everything survives a kill -9 and restart, and an attempt the gateway left unfinished
              comes back as an `unknown` result; the invitation shows the prospective namespace; the claim
              (mailbox, passkey) opens the owner page listing the proposals; publishing one writes
              /our/<inquirer>/<name> and its publication; the inquirer acquires it at /her/<peer>/<name> over Mesa;
              the scoped token is revoked; a later change by the owner arrives as the next case and makes the
              judgment ask again with no mail sent for it.

Flags: --keep, --bin <shrine-mesa>. Environment: GATE_PORTS (a base, 8400; the host, worlds, mesa and flows take
base, base+100, base+1100, base+1200), SHRINE_BASE (the checkout; default: this file's), SHRINE_MESA (the binary).
The gate kills only its own process groups, so it runs beside a live pilot on the same machine.
"""
import base64, hashlib, json, os, re, secrets, shutil, signal, socket, subprocess, sys, tempfile, time
from http.cookiejar import CookieJar
import urllib.error, urllib.parse, urllib.request
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get('SHRINE_BASE', os.path.abspath(os.path.join(HERE, '..', '..', '..', '..')))
BIN = os.environ.get('SHRINE_MESA', '/Users/ianchanner/shrine-mesa/target/debug/shrine-mesa')
if '--bin' in sys.argv: BIN = sys.argv[sys.argv.index('--bin') + 1]
KEEP = '--keep' in sys.argv
os.makedirs(os.path.join(BASE, '.check'), exist_ok=True)
# GATE_TMP keeps the gate's worlds out of the source tree, which every world boot copies into the Nix store
TEMP = tempfile.mkdtemp(prefix='relationship-', dir=os.environ.get('GATE_TMP') or os.path.join(BASE, '.check'))
# ports: the pilot's defaults, or a base from the environment so the gate can run beside a live pilot (GATE_PORTS=8600)
PORT_BASE = int(os.environ.get('GATE_PORTS', '8400'))
HOST_PORT, WORLD_PORT, MESA_PORT, FLOW_PORT = PORT_BASE, PORT_BASE + 100, PORT_BASE + 1100, PORT_BASE + 1200
ORIGIN = f'http://localhost:{HOST_PORT}'
RP_ID = 'localhost'
A = '0x11'
G = '0x1f'
MAILBOX = 'precision@example.test'
STATE, WORLDS, CONFIG, GWMAIL, GWCONFIG = (os.path.join(TEMP, d) for d in ('state', 'worlds', 'host.json', 'gw-mail', 'gateway.json'))
OUTBOX, INBOX = os.path.join(GWMAIL, 'out'), os.path.join(GWMAIL, 'in')
report, t_start = {}, time.monotonic()


def log(s): print(f'[{time.monotonic() - t_start:7.1f}] {s}', flush=True)


def check(label, cond, detail=''):
    if not cond: raise SystemExit(f'FAILED: {label} {str(detail)[:900]}')
    log(f'ok: {label}')


def b64u(b): return base64.urlsafe_b64encode(b).rstrip(b'=').decode()


# --- a minimal CBOR encoder and a software passkey (as phase2.py) -------------------------------------------
def _head(major, n):
    if n < 24: return bytes([major << 5 | n])
    if n < 256: return bytes([major << 5 | 24, n])
    if n < 65536: return bytes([major << 5 | 25]) + n.to_bytes(2, 'big')
    return bytes([major << 5 | 26]) + n.to_bytes(4, 'big')


def cbor(v):
    if isinstance(v, bool): return b'\xf5' if v else b'\xf4'
    if isinstance(v, int): return _head(0, v) if v >= 0 else _head(1, -1 - v)
    if isinstance(v, bytes): return _head(2, len(v)) + v
    if isinstance(v, str):
        e = v.encode(); return _head(3, len(e)) + e
    if isinstance(v, list): return _head(4, len(v)) + b''.join(cbor(x) for x in v)
    if isinstance(v, dict):
        items = sorted(((cbor(k), cbor(x)) for k, x in v.items()), key=lambda kv: (len(kv[0]), kv[0]))
        return _head(5, len(items)) + b''.join(k + x for k, x in items)
    raise TypeError(type(v))


class Authenticator:
    def __init__(self):
        self.key = ec.generate_private_key(ec.SECP256R1()); self.cred_id = secrets.token_bytes(16); self.count = 0

    def cose_key(self):
        n = self.key.public_key().public_numbers()
        return cbor({1: 2, 3: -7, -1: 1, -2: n.x.to_bytes(32, 'big'), -3: n.y.to_bytes(32, 'big')})

    def auth_data(self, flags, attested):
        data = hashlib.sha256(RP_ID.encode()).digest() + bytes([flags]) + self.count.to_bytes(4, 'big')
        if attested: data += bytes(16) + len(self.cred_id).to_bytes(2, 'big') + self.cred_id + self.cose_key()
        return data

    def create(self, options):
        o = options.get('publicKey', options)
        client = json.dumps({'type': 'webauthn.create', 'challenge': o['challenge'], 'origin': ORIGIN, 'crossOrigin': False}).encode()
        att = cbor({'fmt': 'none', 'attStmt': {}, 'authData': self.auth_data(0x45, True)})
        return {'id': b64u(self.cred_id), 'rawId': b64u(self.cred_id), 'type': 'public-key',
                'response': {'attestationObject': b64u(att), 'clientDataJSON': b64u(client)}, 'clientExtensionResults': {}}

    def get(self, options):
        o = options.get('publicKey', options); self.count += 1
        client = json.dumps({'type': 'webauthn.get', 'challenge': o['challenge'], 'origin': ORIGIN, 'crossOrigin': False}).encode()
        ad = self.auth_data(0x05, False)
        sig = self.key.sign(ad + hashlib.sha256(client).digest(), ec.ECDSA(hashes.SHA256()))
        return {'id': b64u(self.cred_id), 'rawId': b64u(self.cred_id), 'type': 'public-key',
                'response': {'authenticatorData': b64u(ad), 'clientDataJSON': b64u(client), 'signature': b64u(sig), 'userHandle': None}, 'clientExtensionResults': {}}


# --- HTTP -----------------------------------------------------------------------------------------------------
class Client:
    def __init__(self):
        self.jar = CookieJar(); self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def call(self, method, url, data=None, headers=None, timeout=60):
        req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
        try:
            with self.opener.open(req, timeout=timeout) as r: return r.status, dict(r.headers), r.read().decode(errors='replace')
        except urllib.error.HTTPError as e: return e.code, dict(e.headers), e.read().decode(errors='replace')

    def get(self, path): return self.call('GET', ORIGIN + path)

    def form(self, path, **fields):
        return self.call('POST', ORIGIN + path, urllib.parse.urlencode(fields).encode(), {'Content-Type': 'application/x-www-form-urlencoded'})

    def json(self, path, body=None, headers=None):
        h = {'Content-Type': 'application/json'}; h.update(headers or {})
        status, _, text = self.call('POST', ORIGIN + path, json.dumps(body if body is not None else {}).encode(), h)
        try: return status, json.loads(text)
        except json.JSONDecodeError: return status, text


def http(method, url, data=None, headers=None, timeout=60): return Client().call(method, url, data, headers, timeout)[::2]


def rpc_body(name, **args): return {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'mcp/' + name, 'arguments': args}}


def world_rpc(port, name, **args):
    status, text = http('POST', f'http://127.0.0.1:{port}/mcp', json.dumps(rpc_body(name, **args)).encode(), {'Content-Type': 'application/json'}, 120)
    res = json.loads(text)['result']
    if res.get('isError'): raise RuntimeError(str(res)[:500])
    return res['structuredContent']


def proxy(node, token, name, **args):
    h = {'Content-Type': 'application/json'}
    if token: h['Authorization'] = 'Bearer ' + token
    status, text = http('POST', f'{ORIGIN}/w/{node}/mcp', json.dumps(rpc_body(name, **args)).encode(), h, 120)
    try: body = json.loads(text)
    except json.JSONDecodeError: body = text
    if status == 200 and isinstance(body, dict) and 'result' in body:
        res = body['result']
        if res.get('isError'): raise RuntimeError(str(res)[:500])
        return 200, res['structuredContent']
    return status, body


def registry(): return json.load(open(os.path.join(STATE, 'registry.json')))


def port_of(node): return next((w['port'] for w in registry()['worlds'] if w['node'] == node), None)


def up(node):
    p = port_of(node)
    try:
        return p if p and world_rpc(p, 'read', path='/' + node, care='x').get('exists') else None
    except OSError:
        return None


def wait(what, pred, timeout=300, every=1.0):
    t, last = time.monotonic(), None
    while time.monotonic() - t < timeout:
        try: v = pred()
        except Exception as e: v, last = None, repr(e)[:300]
        if v: return v, round(time.monotonic() - t, 2)
        time.sleep(every)
    raise SystemExit(f'timed out after {timeout} s waiting for {what}; last error: {last}')


def cli(*args):
    r = subprocess.run([BIN, 'host', *args, '--config', CONFIG], capture_output=True, text=True)
    if r.returncode: raise SystemExit(f'host {" ".join(args)}: {r.stdout[-500:]} {r.stderr[-500:]}')
    return r.stdout.strip()


def mails():
    out = []
    for name in sorted(os.listdir(OUTBOX)):
        if not name.endswith('.eml'): continue
        text = open(os.path.join(OUTBOX, name), errors='replace').read(); head, _, body = text.partition('\n\n')
        headers = {k.strip().lower(): v.strip() for k, v in (l.split(':', 1) for l in head.splitlines() if ':' in l)}
        out.append((name, headers, body))
    return out


def link_in(body, kind):
    m = re.search(re.escape(ORIGIN) + '/' + kind + r'/[A-Za-z0-9_-]+', body)
    return m.group(0)[len(ORIGIN):] if m else None


def kill_everything(sig=signal.SIGKILL):
    """Only this gate's processes: each of host, gateway and fixture leads its own process group (the host's
    worlds, runtimes and services are in the host's), so a live pilot on the same machine is untouched."""
    global host, fixture, gateway
    for p in (host, fixture, gateway):
        if p and p.poll() is None:
            try: os.killpg(p.pid, sig)
            except ProcessLookupError: pass
            try: p.wait(timeout=30)
            except subprocess.TimeoutExpired: pass
    # anything of this gate's worlds that outlived its group (a runtime re-parented by a kill -9 of its launcher)
    subprocess.run(['pkill', f'-{int(sig)}', '-f', TEMP], capture_output=True)
    time.sleep(1)


def write_config(wake=None):
    cfg = {'listen': f'127.0.0.1:{HOST_PORT}', 'origin': ORIGIN, 'rp_id': RP_ID, 'name': 'Shrine pilot host', 'state': STATE, 'shrine': BASE,
           'mounts': ['net', 'mcp', 'probe'], 'worlds': WORLDS, 'ports': {'world': WORLD_PORT, 'mesa': MESA_PORT, 'flow': FLOW_PORT}, 'node_base': '0x20',
           'poll_ms': 300, 'gateways': {'mail': G}, 'limits': {'fresh_lock': os.path.join(TEMP, 'fresh.lock')}}
    if wake: cfg['wake'] = wake
    json.dump(cfg, open(CONFIG, 'w'), indent=1)


def start_host():
    global host, host_logs
    host_logs += 1
    out = open(os.path.join(TEMP, f'host-{host_logs}.log'), 'w')
    host = subprocess.Popen([BIN, 'host', '--config', CONFIG], stdout=out, stderr=subprocess.STDOUT, cwd=TEMP, start_new_session=True)
    def listening():
        if host.poll() is not None: raise SystemExit('host exited: ' + open(out.name).read()[-1500:])
        try:
            with socket.create_connection(('127.0.0.1', HOST_PORT), timeout=0.3): return True
        except OSError: return False
    wait('the host', listening, 30, 0.2)


def start_fixture():
    global fixture
    fixture = subprocess.Popen([sys.executable, os.path.join(HERE, 'fixtures', 'counterparty.py'), '--outbox', OUTBOX, '--inbox', INBOX,
                                '--market', os.path.join(HERE, 'fixtures', 'market.json')], stdout=open(os.path.join(TEMP, 'fixture.log'), 'w'), stderr=subprocess.STDOUT, start_new_session=True)


def start_gateway(serves):
    """The mail gateway process beside its world (registered with the host like any world): the directory transport."""
    global gateway, gateway_logs
    gateway_logs += 1
    json.dump({'world': f'http://127.0.0.1:{port_of(G)}', 'node': G, 'poll_ms': 400,
               'adapters': [{'kind': 'email', 'id': 'mail', 'bind': serves, 'transport': {'dir': GWMAIL, 'from': 'gateway@shrine.local'}}]},
              open(GWCONFIG, 'w'), indent=1)
    gateway = subprocess.Popen([BIN, 'gateway', '--config', GWCONFIG], stdout=open(os.path.join(TEMP, f'gateway-{gateway_logs}.log'), 'w'), stderr=subprocess.STDOUT, cwd=TEMP, start_new_session=True)


def live_ref(path, care): return {'type': 'reference', 'value': f'/h/{care}/0/{len(path.strip("/").split("/"))}/{path.strip("/")}'}


def pinned(record): return {'type': 'reference', 'value': record['reference']}


def children(port, path): return world_rpc(port, 'read', path=path, care='y').get('children', [])


def interactions(port, folder=f'/{A}/relationships/precision/interactions'):
    return sorted(children(port, folder), key=lambda c: c['path'])


def result_of(port, node, rid):
    r = world_rpc(port, 'read', path=f'/{node}/her/{G}/results/{rid}', care='x')
    return r['properties'] if r.get('exists') else None


host, fixture, gateway, host_logs, gateway_logs = None, None, None, 0, 0
# an earlier run from this same temp directory only: other checkouts' runs have their own ports and temp directories
if subprocess.run(['pgrep', '-f', r'(x/eden|shrine-mesa (host|gateway)|wisp).*' + re.escape(os.path.join(os.path.dirname(TEMP), 'relationship-'))], capture_output=True).stdout.decode().split() != []: raise SystemExit('an earlier run of this gate is still running')
if not os.access(BIN, os.X_OK): raise SystemExit(f'no shrine-mesa binary at {BIN}')
for d in (STATE, OUTBOX, INBOX, WORLDS): os.makedirs(d, exist_ok=True)


def stub_markers(port): return [c['properties'] for c in children(port, f'/{A}/agent/stub')]


def runs(port): return [c['properties'] for c in children(port, f'/{A}/agent/runs')]


def wake_only():
    write_config({'command': [sys.executable, os.path.join(HERE, 'fixtures', 'stub_agent.py')], 'skills': [], 'timeout_s': 60, 'cooldown_s': 1})
    cli('add-world', '--node', A, '--name', 'Northstar', '--contact', 'owner-a@example.test')
    agent = cli('token', '--node', A, '--who', 'agent'); mail = cli('token', '--node', A, '--who', 'mail')
    start_host()
    (port, s) = wait('world A', lambda: up(A), 300, 2); log(f'A up in {s} s')
    stdlib = {c['path'].rsplit('/', 1)[1]: pinned(c) for c in world_rpc(port, 'read', path=f'/{A}/weft/stdlib', care='y', limit=100)['children']}
    check('the stdlib ask cell is seeded', 'ask' in stdlib, list(stdlib)[:10])
    proxy(A, agent, 'write', records=[
        {'path': f'/{A}/relationships/precision', 'slots': {'note': 'a shop'}},
        {'path': f'/{A}/relationships/precision/identifiers/email', 'slots': {'value': 'precision@example.test'}},
        {'path': f'/{A}/relationships/allied', 'slots': {'note': 'another shop'}},
        {'path': f'/{A}/relationships/allied/identifiers/email', 'slots': {'value': 'allied@example.test'}},
        {'path': f'/{A}/judgments/precision', 'slots': {'sys/weft': stdlib['ask'], 'sys/tack': live_ref(f'/{A}/relationships/precision', 'z'),
                                                        'prompt': 'Does this relationship hold? Say ok or not and why.', 'model': 'any'}}])
    at = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(time.time() + 6))
    folder_case = world_rpc(port, 'read', path=f'/{A}/relationships/precision', care='x')['reference'].split('/')[3]
    proxy(A, agent, 'write', records=[
        {'path': f'/{A}/agent/wakes/clock', 'slots': {'why': 'look again at the clock', 'at': at}},
        {'path': f'/{A}/agent/wakes/name', 'slots': {'why': 'precision moved', 'on': {'type': 'reference', 'value': f'/h/z/{folder_case}/3/{A}/relationships/precision'}}},
        {'path': f'/{A}/agent/wakes/cell', 'slots': {'why': 'the judgment asks', 'cell': live_ref(f'/{A}/judgments/precision', 'x')}},
        {'path': f'/{A}/agent/wakes/never', 'slots': {'why': 'allied moved', 'on': live_ref(f'/{A}/relationships/allied', 'z')}}])
    (marks, s) = wait('the clock and cell wakes', lambda: (lambda m: m if len(m) >= 2 else None)(stub_markers(port)), 60, 0.5)
    log(f'{len(marks)} run(s) after {s} s: ' + '; '.join(m.get('/why', '') for m in marks))
    whys = ' | '.join(m.get('/why', '') for m in marks)
    check('the clock wake fired with its why', 'look again at the clock' in whys, whys)
    check('the cell wake fired with the cell path', any('judgment asks' in m.get('/why', '') and 'judgments' in m.get('/paths', '') for m in marks), marks)
    check("the agent's own marker writes fired nothing more", len(stub_markers(port)) == len(marks), stub_markers(port))
    wakes = {c['path'].rsplit('/', 1)[1]: c['properties'] for c in children(port, f'/{A}/agent/wakes')}
    check('fired wakes carry fired, the others do not', '/fired' in wakes['clock'] and '/fired' in wakes['cell'] and '/fired' not in wakes['name'] and '/fired' not in wakes['never'], wakes)
    before = len(stub_markers(port))
    proxy(A, mail, 'write', records=[{'path': f'/{A}/relationships/precision/interactions/m1', 'slots': {'from': 'precision@example.test', 'text': 'We can make 500 at 43.', 'at': at}}])
    (marks, s) = wait('the name wake', lambda: (lambda m: m if len(m) > before else None)(stub_markers(port)), 30, 0.3)
    check('the name wake fired with the changed path', any(m.get('/why') == 'precision moved' and 'interactions/m1' in m.get('/paths', '') for m in marks), marks)
    check('the unrelated relationship fired nothing', not any(m.get('/why') == 'allied moved' for m in marks), marks)
    before = len(stub_markers(port))
    proxy(A, agent, 'write', records=[{'path': f'/{A}/agent/wakes/never', 'action': 'cull'},
                                      {'path': f'/{A}/relationships/allied/observations/o1', 'slots': {'said': 'nothing'}},
                                      {'path': f'/{A}/relationships/precision/observations/o1', 'slots': {'said': '500 at 43'}}])
    time.sleep(4)
    check("neither a culled wake nor the agent's own writes fire", len(stub_markers(port)) == before, stub_markers(port)[before:])
    ctx = world_rpc(port, 'read', path=f'/c/x/{A}/judgments/precision', care='x')['properties']
    proxy(A, agent, 'write', records=[
        {'path': f'/{A}/judgments/precision/result', 'slots': {'answer': 'ok', 'ok': 'yes', 'case': int(ctx.get('/sys/tack/case', 0)), 'model': 'any', 'prompt': ctx.get('/prompt', '')}},
        {'path': f'/{A}/judgments/precision', 'action': 'poke', 'slots': {'result': live_ref(f'/{A}/judgments/precision/result', 'x')}},
        {'path': f'/{A}/agent/wakes/cell2', 'slots': {'why': 'the judgment asks again', 'cell': live_ref(f'/{A}/judgments/precision', 'x')}}])
    time.sleep(3)
    answered = world_rpc(port, 'read', path=f'/x/{A}/judgments/precision', care='x')
    check('the answered cell answers its result', answered.get('exists') and answered['properties'].get('/answer') == 'ok', answered)
    proxy(A, mail, 'write', records=[{'path': f'/{A}/relationships/precision/interactions/m2', 'slots': {'from': 'precision@example.test', 'text': '39.50 for a recurring order.', 'at': at}}])
    wait('the cell to ask again', lambda: (lambda m: m if any(x.get('/why', '').startswith('the judgment asks again') for x in m) else None)(stub_markers(port)), 30, 0.3)
    check('a changed folder makes the answered cell ask again and the wake fire', True)
    (rs, _) = wait('runs recorded', lambda: (lambda r: r if r and all('/ended' in x for x in r) else None)(runs(port)), 20, 0.5)
    check('every run has started, ended and exit 0', all(x.get('/exit') == '0' for x in rs) and len(rs) >= 4, rs)
    proxy(A, agent, 'write', records=[{'path': f'/{A}/agent/wakes/later', 'slots': {'why': 'after the restart', 'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(time.time() + 12))}}])
    time.sleep(1)
    kill_everything(signal.SIGKILL); log('host and world killed')
    start_host(); wait('world A back', lambda: up(A), 300, 1)
    wait('the wake declared before the restart', lambda: (lambda m: m if any(x.get('/why') == 'after the restart' for x in m) else None)(stub_markers(port)), 60, 0.5)
    check('a wake declared before a restart fires after it', True)
    report['wake_runs'] = len(stub_markers(port))
    log('WAKE GATE PASSED ' + json.dumps(report))


def full():
    write_config()
    cli('add-world', '--node', A, '--name', 'Northstar', '--contact', 'owner-a@example.test')
    cli('add-world', '--node', G, '--name', 'mail gateway', '--contact', 'gateway@shrine.local')
    owner = cli('token', '--node', A, '--who', 'owner'); agent = cli('token', '--node', A, '--who', 'agent')
    start_host(); start_gateway([A]); start_fixture()
    (pa, s) = wait('world A', lambda: up(A), 300, 2); log(f'A up in {s} s')
    (pg, s) = wait('the gateway world', lambda: up(G), 300, 2); log(f'gateway world {G} up in {s} s')
    stdlib = {c['path'].rsplit('/', 1)[1]: pinned(c) for c in world_rpc(pa, 'read', path=f'/{A}/weft/stdlib', care='y', limit=100)['children']}
    world_rpc(pa, 'write', who='owner', records=[{'path': f'/{A}/net/self', 'action': 'poke', 'slots': {'name': 'Northstar'}}])
    (port_record, s) = wait('the gateway\'s port acquired at /her', lambda: (lambda r: r if r.get('exists') else None)(world_rpc(pa, 'read', path=f'/{A}/her/{G}/public/ports/email', care='x')), 120, 0.5)
    check('the gateway advertises send over email to everyone, under its /our/public', port_record['properties'].get('/kind') == 'email' and port_record['properties'].get('/operations') == 'send' and port_record['properties'].get('/publisher') == G, port_record['properties'])
    (binding, s) = wait('the binding acquired at /her', lambda: (lambda r: r if r.get('exists') else None)(world_rpc(pa, 'read', path=f'/{A}/her/{G}/bindings/mail', care='x')), 60, 0.5)
    check('the world sees its own binding to the endpoint, for send and receive, with its address', 'send' in binding['properties'].get('/operations', '') and 'receive' in binding['properties'].get('/operations', '') and binding['properties'].get('/kind') == 'email', binding['properties'])
    other = world_rpc(pa, 'read', path=f'/{A}/her/{G}/endpoints', care='y')
    check('the gateway keeps its own bookkeeping to itself', not other.get('children'), other)
    log(f'port acquired {s} s after both worlds were up')

    # --- 1 the relationship begins: a need, the folder, the standing approval, the first request
    proxy(A, owner, 'write', records=[
        {'path': f'/{A}/needs/widgets', 'slots': {'want': '500', 'maximum_price': '40 per unit', 'note': 'a supplier able to resume deliveries when production restarts'}},
        {'path': f'/{A}/needs/widgets/approval', 'slots': {'until': '2027-01-01T00:00:00Z', 'note': 'any outreach about widgets while I sleep'}}])
    rid = 'widgets_precision'
    proxy(A, agent, 'write', records=[
        {'path': f'/{A}/relationships/precision', 'slots': {'refers': f'/{A}/needs/widgets'}},
        {'path': f'/{A}/relationships/precision/identifiers/email', 'slots': {'value': MAILBOX}},
        {'path': f'/{A}/judgments/precision', 'slots': {'sys/weft': stdlib['ask'], 'sys/tack': live_ref(f'/{A}/relationships/precision', 'z'),
                                                        'prompt': f'Does this relationship satisfy /{A}/needs/widgets? Say ok or not, why, and when to look again.', 'model': 'any'}},
        {'path': f'/{A}/our/{G}/requests/{rid}', 'slots': {'do': 'send', 'channel': 'email', 'to': MAILBOX, 'about': f'/{A}/needs/widgets', 'relationship': f'/{A}/relationships/precision',
                                                         'subject': 'widgets', 'text': 'Can you supply 500 widgets at $40/unit or less? We need a supplier who can resume fulfilling orders when production restarts.'}}])
    t0 = time.monotonic()
    (res, s) = wait('the result from the gateway', lambda: result_of(pa, A, rid), 90, 0.5)
    report['request_to_result_s'] = round(time.monotonic() - t0, 2)
    check('the result says sent, with the message id, at the request\'s case', res.get('/status') == 'sent' and res.get('/message_id') and res.get('/case') and res.get('/publisher') == G, res)
    (conv, s) = wait('the reply by mail', lambda: (lambda c: c if c else None)(interactions(pa)), 90, 0.5)
    report['ask_to_reply_s'] = round(time.monotonic() - t0, 2)
    reply = conv[0]; rp = reply['properties']
    check('the reply was filed as an interaction by the request it answers', rp.get('/channel') == 'email' and rp.get('/request') == rid and rp.get('/in_reply_to') and '$43' in rp.get('/text', ''), rp)
    check('the interaction references the acquired inbound and names the gateway', rp.get('/source', '').startswith(f'/h/x/') and f'/her/{G}/inbound/' in rp.get('/source', '') and rp.get('/gateway') == G, rp)
    check('the reply is attributed and marked simulated', rp.get('/from') == MAILBOX and 'simulated' in rp.get('/text', '') and rp.get('/authenticated') == 'claimed', rp)
    request = world_rpc(pa, 'read', path=f'/{A}/our/{G}/requests/{rid}', care='x')['properties']
    check('the host added the claim link as the request\'s footer before publishing', '/i/' in request.get('/footer', ''), request)
    peer = next((w['node'] for w in registry()['worlds'] if w['contact'] == MAILBOX), None)
    check('a prospective world is reserved for the mailbox', peer and peer.startswith('0x') and peer not in (A, G), peer)
    events = world_rpc(pa, 'history', after=0, limit=60)['events']
    check('the interaction event carries the gateway as its principal', any(e['who'] == G and any(p.startswith(f'/{A}/relationships/precision/interactions/') for p in e['touched']) for e in events), [(e['who'], e['touched'][-1]) for e in events][-6:])
    attempt = world_rpc(pg, 'read', path=f'/{G}/attempts/{A}/{rid}', care='x')['properties']
    check('the gateway recorded its attempt before sending and closed it', attempt.get('/status') == 'done' and attempt.get('/external_id') == res.get('/message_id') and attempt.get('/endpoint') == 'mail', attempt)
    # the agent's observation, a counter-offer on the same thread
    proxy(A, agent, 'write', records=[
        {'path': f'/{A}/relationships/precision/observations/o1', 'slots': {'about': 'widgets', 'said': 'can make 500; current price 43 per unit', 'by': MAILBOX, 'at': rp.get('/at', ''), 'source': pinned(reply)}},
        {'path': f'/{A}/our/{G}/requests/{rid}', 'action': 'poke', 'slots': {'text': 'Would you consider $39.50/unit for a recurring arrangement?', 'in_reply_to': rp.get('/message_id', '')}}])
    (conv, s) = wait('the answer to the counter-offer', lambda: (lambda c: c if len(c) >= 2 else None)(interactions(pa)), 60, 0.5)
    rp2 = conv[1]['properties']
    check('the counter-offer was sent again on the same thread and answered', '39.5' in rp2.get('/text', '') and '30 days' in rp2.get('/text', '') and rp2.get('/request') == rid, rp2)
    (res2, s) = wait('the second result', lambda: (lambda r: r if r and int(r.get('/case', 0)) > int(res.get('/case', 0)) else None)(result_of(pa, A, rid)), 30, 0.3)
    check('one attempt per request case, each with its own result', res2.get('/status') == 'sent' and res2.get('/message_id') != res.get('/message_id'), (res, res2))
    ctx = world_rpc(pa, 'read', path=f'/c/x/{A}/judgments/precision', care='x')['properties']
    check('the judgment cell beside the folder asks', ctx.get('/sys/view/asking', '').startswith('no answer yet'), ctx)
    follow_up = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(time.time() + 26 * 86400))
    # the evidence first (it moves the folder's case), then the answer stamped with the case it judged
    proxy(A, agent, 'write', records=[
        {'path': f'/{A}/relationships/precision/observations/o2', 'slots': {'about': 'widgets', 'said': '39.50 per unit for a recurring arrangement, valid 30 days, subject to capacity', 'by': MAILBOX, 'expires': follow_up, 'qualified': 'capacity unconfirmed', 'source': pinned(conv[1])}},
        {'path': f'/{A}/relationships/precision/unresolved/capacity', 'slots': {'question': 'Can they sustain 500 a month?', 'since': rp2.get('/at', ''), 'due': follow_up}}])
    ctx = world_rpc(pa, 'read', path=f'/c/x/{A}/judgments/precision', care='x')['properties']
    proxy(A, agent, 'write', records=[
        {'path': f'/{A}/judgments/precision/result', 'slots': {'answer': 'Price meets the target. Supplier appears operational. Capacity unconfirmed; follow up before the offer expires.', 'ok': 'yes',
                                                                'case': int(ctx.get('/sys/tack/case', 0)), 'model': 'any', 'prompt': ctx.get('/prompt', ''), 'relied_on': f'/{A}/relationships/precision/observations/o2', 'follow_up': follow_up}},
        {'path': f'/{A}/judgments/precision', 'action': 'poke', 'slots': {'result': live_ref(f'/{A}/judgments/precision/result', 'x')}},
        {'path': f'/{A}/agent/wakes/precision_offer', 'slots': {'why': 'the 39.50 offer expires; confirm capacity or look elsewhere', 'at': follow_up}},
        {'path': f'/{A}/agent/wakes/precision_moved', 'slots': {'why': 'precision published or wrote', 'on': live_ref(f'/{A}/her/{peer}', 'z')}}])
    judged = world_rpc(pa, 'read', path=f'/x/{A}/judgments/precision', care='x')
    check('the judgment is answered with what it relied on and a follow-up', judged.get('exists') and judged['properties'].get('/ok') == 'yes' and judged['properties'].get('/follow_up') == follow_up, judged)
    # what Northstar publishes to the person before they join: under its own /our/<peer>, by the convention;
    # the reservation is a name and a key with no runtime until the person opens a link
    reservation = next(w for w in registry()['worlds'] if w['node'] == peer)
    check('the reservation holds no runtime before the person opens the link', reservation.get('dormant') and not up(peer), reservation)
    rel = world_rpc(pa, 'read', path=f'/{A}/relationships/precision', care='x')['properties']
    check('the relationship names the world reserved for the mailbox', rel.get('/prospective') == peer, rel)
    st, _ = proxy(A, agent, 'write', records=[
        {'path': f'/{A}/our/{peer}/hello', 'slots': {'who': 'Northstar, a small machine shop', 'how': 'we wrote to your mailbox about widgets', 'wants': 'a supplier for 500 widgets a month'}},
        {'path': f'/{A}/our/{peer}/inquiry/widgets', 'slots': {'what': '500 widgets a month, 6061 anodized', 'by': 'monthly, recurring', 'note': 'the inquiry of ' + rp.get('/at', '')}},
        {'path': f'/{A}/our/{peer}/understood/widgets', 'slots': {'price': '39.50 per unit', 'valid': '30 days', 'capacity': 'unconfirmed', 'channel': 'email', 'source': pinned(conv[1])}}])
    check('Northstar wrote what it publishes to the person under its own /our', st == 200, st)
    log('test 1 holds: the relationship exists before the counterparty joins, through a gateway that knows nothing of it')

    # --- 2 persistence: kill everything, restart; the records and the wakes are there; an unfinished attempt is reported unknown
    world_rpc(pg, 'write', who='gateway', records=[{'path': f'/{G}/attempts/{A}/ghost', 'slots': {'case': 1, 'status': 'attempting', 'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}}])
    kill_everything(signal.SIGKILL); log('host, gateway, fixture, worlds and services killed')
    t0 = time.monotonic(); start_host(); start_gateway([A]); start_fixture()
    wait('the worlds back', lambda: up(A) and up(G), 600, 1); report['restart_s'] = round(time.monotonic() - t0, 2)
    check('the interactions, the judgment and the wakes survive', len(interactions(pa)) == 2 and world_rpc(pa, 'read', path=f'/x/{A}/judgments/precision', care='x').get('exists')
          and len(children(pa, f'/{A}/agent/wakes')) == 2, 'after restart')
    (ghost, s) = wait('the unknown result', lambda: result_of(pa, A, 'ghost'), 60, 0.5)
    check('an attempt the gateway could not finish comes back as unknown, never sent again', ghost.get('/status') == 'unknown' and 'restart' in ghost.get('/error', ''), ghost)
    log('test 2 holds: nothing lives in a process, and uncertainty is recorded as such')

    # --- 4 claiming: the invitation shows the prospective namespace; claim, passkey, review, publish
    invite = next(link_in(b, 'i') for n, h, b in mails() if link_in(b, 'i'))
    stranger = Client()
    stranger.get(invite)
    # opening the link wakes the reservation; it boots and acquires what was published to it while it slept
    (pb, s) = wait('the prospective world, woken by its link', lambda: up(peer), 900, 2); log(f'peer {peer} up in {s} s'); report['wake_s'] = s
    (understood, s) = wait('the publication acquired in the woken world', lambda: (lambda r: r if r.get('exists') else None)(world_rpc(pb, 'read', path=f'/{peer}/her/{A}/understood/widgets', care='x')), 120, 0.5)
    check("the person's namespace holds it, signed by Northstar, never as the person's statement", understood['properties'].get('/publisher') == A and understood['properties'].get('/capacity') == 'unconfirmed', understood['properties'])
    report['proposals'] = len(children(pb, f'/{peer}/her/{A}/understood'))
    status, _, page = stranger.get(invite)
    check('the invitation shows the inquiry and what was recorded', status == 200 and 'Northstar' in page and '39.50 per unit' in page and 'understood' in page and 'Claim this world' in page, (status, page[:300]))
    # the reply page: the agent says what it asks and what to show; the person answers in a few taps, into their own world
    proxy(A, agent, 'write', records=[{'path': f'/{A}/our/{G}/requests/{rid}', 'action': 'poke', 'slots': {
        'ask': 'price (number USD/each): at 500 a month\nlead_time (number day)\nterms (choice: net 30 | net 60)', 'show_1': live_ref(f'/{A}/needs/widgets', 'x')}}])
    status, _, page = stranger.get(invite)
    check('the reply page asks for the fields the agent chose, prefilled from what was noted, beside what it chose to show',
          status == 200 and 'name="f.price"' in page and '<span class="unit">$</span>' in page and 'a piece' in page and 'Lead time' in page and 'net 60' in page and '39.50' in page and 'Maximum price' in page and 'noted' in page, page[:600])
    status, _, page = stranger.form(invite + '/answer', **{'f.price': '39.50', 'f.lead_time': '14', 'f.terms': 'net 30', 'note': 'price holds until December'})
    check('Send thanks them and offers their page', status == 200 and 'Sent to Northstar' in page and 'Claim your page' in page, page[:300])
    (answer, s) = wait('the answer acquired by the asker', lambda: (lambda r: r if r.get('exists') else None)(world_rpc(pa, 'read', path=f'/{A}/her/{peer}/{rid}', care='x')), 120, 0.5)
    check("the answer is the person's own publication, signed by their world, typed: a number with its unit", answer['properties'].get('/publisher') == peer and answer['properties'].get('/price') == '39.50'
          and answer['properties'].get('/price/unit') == 'USD/each' and answer['properties'].get('/lead_time/unit') == 'day'
          and answer['properties'].get('/terms') == 'net 30' and answer['properties'].get('/note') == 'price holds until December', answer['properties'])
    report['reply_s'] = s
    status, _, page = stranger.get(invite)
    check('the page opens again on their answer, to change it, and says where the values came from', 'You answered this already' in page and 'value="14"' in page and 'your answer' in page and 'Filled in from' in page, page[:600])
    status, _, page = stranger.form(invite + '/claim')
    check('the claim requests a verification mail', status == 200, (status, page[:200]))
    (claim, s) = wait('the claim mail through the gateway', lambda: next((link_in(b, 'c') for n, h, b in mails() if link_in(b, 'c')), None), 60, 0.3)
    status, options = stranger.json(claim + '/passkey/options')
    passkey = Authenticator()
    status, result = stranger.json(claim + '/passkey', passkey.create(options))
    check('the mailbox is verified and a passkey registered', status == 200 and result.get('ok'), (status, result))
    st, _ = proxy(A, agent, 'write', records=[{'path': f'/{A}/our/{peer}/understood/widgets', 'action': 'poke', 'slots': {'note': 'written after the claim'}}])
    (after_claim, s) = wait('the next case acquired after the claim', lambda: (lambda h: h if h.get('cases', 0) >= 2 else None)(world_rpc(pb, 'history', path=f'/{peer}/her/{A}/understood/widgets', limit=5)), 60, 0.3)
    check('the inquirer keeps publishing after the claim under its own authority, as a new case', after_claim.get('cases', 0) >= 2, after_claim)
    status, _, page = stranger.get(f'/w/{peer}')
    check('the owner page lists the proposals for review', status == 200 and 'Recorded by 0x11' in page and 'Publish to 0x11' in page and '39.50 per unit' in page, page[:500])
    status, _, page = stranger.form(f'/w/{peer}/publish/{A}/widgets', **{'slot.price': '39.50 per unit', 'slot.valid': '30 days', 'slot.capacity': '500 a month confirmed', 'slot.lead_time': '14 days'})
    check('publishing writes the owned name', status in (200, 303), status)
    own = world_rpc(pb, 'read', path=f'/{peer}/our/{A}/widgets', care='x')['properties']
    check('/our/<inquirer>/widgets holds the corrected terms', own.get('/capacity') == '500 a month confirmed' and own.get('/price') == '39.50 per unit', own)
    pub = world_rpc(pb, 'read', path=f'/{peer}/net/publications/widgets_{A}', care='x')['properties']
    check('its publication names the path and the inquirer', pub.get('/path') == f'/{peer}/our/{A}/widgets' and pub.get('/to') == A, pub)
    hist = world_rpc(pb, 'history', path=f'/{peer}/her/{A}/understood/widgets', limit=10)
    check('what the inquirer published keeps every case as the inquirer wrote it; the owner rewrote none', all(v['properties'].get('/capacity') == 'unconfirmed' for v in hist['versions']) and hist['cases'] >= 2, hist['versions'])
    events = world_rpc(pb, 'history', after=0, limit=60)['events']
    check('the acquired records are never attributed to the owner; the publication is',
          any(e['who'] != 'owner' and any(f'/her/{A}/' in p for p in e['touched']) for e in events) and any(e['who'] == 'owner' and any('/our/' in p for p in e['touched']) for e in events), [(e['who'], e['touched'][-1]) for e in events][-6:])
    log('test 4 holds: the claim consolidates without rewriting')

    # --- 5 native convergence: acquired at /her, a later change re-judged, no mail
    t0 = time.monotonic()
    (her, s) = wait('the publication acquired at /her', lambda: (lambda r: r if r.get('exists') else None)(world_rpc(pa, 'read', path=f'/{A}/her/{peer}/widgets', care='x')), 120, 0.5)
    report['publish_to_her_s'] = round(time.monotonic() - t0, 2)
    hp = her['properties']
    check('/her/<peer>/widgets holds the owner\'s statement with its case and publisher', hp.get('/capacity') == '500 a month confirmed' and hp.get('/publisher') == peer and hp.get('/remote_case'), hp)
    mails_before = len(mails())
    owner_b = cli('token', '--node', peer, '--who', 'owner')
    (poked, s) = wait('the owner token to be known to the host', lambda: (lambda r: r if r[0] == 200 else None)(proxy(peer, owner_b, 'write', records=[{'path': f'/{peer}/our/{A}/widgets', 'action': 'poke', 'slots': {'price': '41 per unit'}}])), 20, 0.5)
    check('the owner changed the published price', poked[0] == 200, poked)
    (her2, s) = wait('the next case at /her', lambda: (lambda r: r if r['properties'].get('/price') == '41 per unit' else None)(world_rpc(pa, 'read', path=f'/{A}/her/{peer}/widgets', care='x')), 60, 0.3)
    report['change_to_her_s'] = s
    proxy(A, agent, 'write', records=[{'path': f'/{A}/relationships/precision/observations/o3', 'slots': {'about': 'widgets', 'said': '41 per unit', 'by': peer, 'source': pinned(her2)}}])
    ctx = world_rpc(pa, 'read', path=f'/c/x/{A}/judgments/precision', care='x')['properties']
    check('the judgment asks again from the Mesa case', ctx.get('/sys/view/asking', '').startswith('re-asking'), ctx)
    time.sleep(2)
    check('no mail went out for information that is published', len(mails()) == mails_before, mails()[mails_before:])
    hist = world_rpc(pa, 'history', path=f'/{A}/her/{peer}/widgets', limit=5)
    check('/her keeps every acquired case', hist['cases'] >= 2, hist)
    log('test 5 holds: the observation source changed from mail to Mesa at the same relationship')

    # --- 6 a slice: a blank on any record, a copied link that sends nothing, the stranger answers into their own world
    stranger_box = 'quotes@anodizer.example.test'
    proxy(A, owner, 'write', records=[{'path': f'/{A}/vendors/anodizer', 'slots': {'name': 'Bright Anodizing', 'email': stranger_box, 'text': 'A finisher a colleague mentioned.',
                                                                             'price/hole': 'number USD/each: per plate, type II clear', 'turnaround/hole': 'number day'}}])
    sid = 'ask_anodizer_1'
    proxy(A, owner, 'write', records=[{'path': f'/{A}/our/{G}/requests/{sid}', 'slots': {'do': 'send', 'channel': 'email', 'to': stranger_box, 'subject': 'A few questions from Northstar',
        'text': 'Northstar would like to know a few things.', 'ask': 'price (number USD/each): per plate, type II clear\nturnaround (number day)', 'show_1': live_ref(f'/{A}/vendors/anodizer', 'x'),
        'relationship': f'/{A}/vendors/anodizer', 'about': f'/{A}/vendors/anodizer'}}])
    mails_now = len(mails())
    status, text = http('POST', f'{ORIGIN}/w/{A}/link', json.dumps({'request': f'/{A}/our/{G}/requests/{sid}'}).encode(), {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + owner}, 60)
    link = json.loads(text).get('link') if status == 200 else None
    check('copy link gives a reply link and sends nothing', bool(link) and '/i/' in link and len(mails()) == mails_now, (status, text[:300]))
    slice_peer = world_rpc(pa, 'read', path=f'/{A}/vendors/anodizer', care='x')['properties'].get('/prospective')
    check('the record, outside /relationships, learns the world reserved for the address', bool(slice_peer), slice_peer)
    other = Client()
    status, _, page = other.get(link[len(ORIGIN):])
    check('the link opens a page asking for exactly the blanks, typed', status == 200 and 'name="f.price"' in page and 'name="f.turnaround"' in page and 'a piece' in page and 'days' in page, page[:500])
    status, _, page = other.form(link[len(ORIGIN):] + '/answer', **{'f.price': '4.80', 'f.turnaround': '5'})
    check('their answer is sent', status == 200 and 'Sent to' in page, page[:300])
    (sl, s) = wait('the slice answered into the asker', lambda: (lambda r: r if r.get('exists') else None)(world_rpc(pa, 'read', path=f'/{A}/her/{slice_peer}/{sid}', care='x')), 300, 1)
    check("the answer is the stranger's own publication, typed", sl['properties'].get('/publisher') == slice_peer and sl['properties'].get('/price') == '4.80' and sl['properties'].get('/turnaround/unit') == 'day', sl['properties'])
    report['slice_s'] = s
    report['mails'] = len(mails())
    log('RELATIONSHIP GATE PASSED ' + json.dumps(report))


def many():
    """Several independent worlds, one previously non-Shrine business: separately attributed histories in one
    prospective world; the claim shows all; each inquirer sees only its own; publication is per inquirer."""
    write_config()
    # two inquirers on this 8 GB laptop (three fresh worlds booting at once took 4.4 GB); booted one after the other
    inquirers = [(A, 'Northstar'), ('0x12', 'Allied Metals')]
    tokens, ports = {}, {}
    cli('add-world', '--node', G, '--name', 'mail gateway', '--contact', 'gateway@shrine.local')
    start_host(); start_gateway([n for n, _ in inquirers]); start_fixture()
    for node, name in inquirers:
        cli('add-world', '--node', node, '--name', name, '--contact', f'owner-{node}@example.test')
        tokens[node] = (cli('token', '--node', node, '--who', 'owner'), cli('token', '--node', node, '--who', 'agent'))
        (ports[node], s) = wait(f'world {node}', lambda n=node: up(n), 400, 2); log(f'{name} {node} up in {s} s')
        world_rpc(ports[node], 'write', who='owner', records=[{'path': f'/{node}/net/self', 'action': 'poke', 'slots': {'name': name}}])
    def wisp_rss():
        mine = os.path.dirname(STATE)
        pids = [pid for pid in subprocess.run(['pgrep', '-x', 'wisp'], capture_output=True, text=True).stdout.split()
                if not os.path.exists('/proc') or mine in open(f'/proc/{pid}/cmdline', 'rb').read().decode(errors='replace')]
        return sum(int(x) for pid in pids for x in subprocess.run(['ps', '-o', 'rss=', '-p', pid], capture_output=True, text=True).stdout.split()) // 1024
    report['rss_mb_two_worlds'] = wisp_rss()
    # the guard is the machine's: a fresh world holds about 2.5 GB on the box after its first boot, under 1 GB on the laptop
    guard = int(os.environ.get('GATE_RSS_MB', '3500'))
    check('the worlds stay under the guard', report['rss_mb_two_worlds'] < guard, (report['rss_mb_two_worlds'], guard))
    # each inquirer asks the same mailbox about its own need; the host reserves one prospective world for the mailbox
    asks = {A: ('widgets', '500 at 40 per unit'), '0x12': ('brackets', '2000 a quarter, 12 per unit')}
    for node, name in inquirers:
        owner, agent = tokens[node]; need, want = asks[node]
        proxy(node, owner, 'write', records=[{'path': f'/{node}/needs/{need}', 'slots': {'want': want}}, {'path': f'/{node}/needs/{need}/approval', 'slots': {'note': 'standing'}}])
        proxy(node, agent, 'write', records=[
            {'path': f'/{node}/relationships/precision', 'slots': {'refers': f'/{node}/needs/{need}'}},
            {'path': f'/{node}/relationships/precision/identifiers/email', 'slots': {'value': MAILBOX}},
            {'path': f'/{node}/our/{G}/requests/{need}_precision', 'slots': {'do': 'send', 'channel': 'email', 'to': MAILBOX, 'about': f'/{node}/needs/{need}', 'relationship': f'/{node}/relationships/precision',
                                                                         'subject': need, 'text': f'{name} asks: can you supply {want}?'}}])
    for node, name in inquirers:
        need = asks[node][0]
        (res, s) = wait(f'the result for {node}', lambda n=node, d=need: result_of(ports[n], n, f'{d}_precision'), 90, 0.5)
        check(f'{name}\'s request was sent by the gateway', res.get('/status') == 'sent', res)
    peers = {w['node'] for w in registry()['worlds'] if w['contact'] == MAILBOX}
    check('one prospective world serves every inquirer of the mailbox', len(peers) == 1, peers)
    peer = next(iter(peers))
    for node, name in inquirers:
        (conv, s) = wait(f'reply to {node}', lambda n=node: (lambda c: c if c else None)(interactions(ports[n], f'/{n}/relationships/precision/interactions')), 90, 0.5)
        check(f'{name} received its own threaded reply', conv[0]['properties'].get('/request') == f'{asks[node][0]}_precision', conv[0]['properties'])
    check('the reservation holds no runtime before the person opens a link', next(w for w in registry()['worlds'] if w['node'] == peer).get('dormant') and not up(peer), peer)
    for node, name in inquirers:
        need = asks[node][0]
        st, _ = proxy(node, tokens[node][1], 'write', records=[
            {'path': f'/{node}/our/{peer}/hello', 'slots': {'who': name, 'how': 'we wrote to your mailbox'}},
            {'path': f'/{node}/our/{peer}/inquiry/{need}', 'slots': {'what': f'{need}, as {name} needs them'}},
            {'path': f'/{node}/our/{peer}/understood/{need}', 'slots': {'price': f'{name} was quoted 43 per unit', 'note': f'recorded by {name}\'s agent'}}])
        check(f'{name} published what it understood, under its own /our', st == 200, st)
    invite = next(link_in(b, 'i') for n, h, b in mails() if link_in(b, 'i'))
    stranger = Client()
    stranger.get(invite)
    (pb, s) = wait('the prospective world, woken by its link', lambda: up(peer), 900, 2); log(f'peer {peer} up in {s} s')
    for node, name in inquirers:
        need = asks[node][0]
        wait(f'{name}\'s publication lands in the prospective world', lambda n=node, d=need: (lambda r: r if r.get('exists') else None)(world_rpc(pb, 'read', path=f'/{peer}/her/{n}/understood/{d}', care='x')), 120, 0.5)
    report['rss_mb_three_worlds'] = wisp_rss()
    cross = world_rpc(ports[A], 'read', path=f'/{A}/her/{peer}/understood/brackets', care='x')
    check("what Allied published to the person is nowhere in Northstar's world", not cross.get('exists'), cross)
    before = {c['path']: c['reference'] for c in children(pb, f'/{peer}/her/{A}/understood')}
    # the claim through Northstar's link; the owner reviews all three, publishes to two, relates them, sets one aside
    status, _, page = stranger.get(invite)
    check('the invitation shows only the inquirer whose link it is', status == 200 and 'Northstar' in page and 'Allied Metals' not in page, page[:300])
    stranger.form(invite + '/claim')
    (claim, s) = wait('the claim mail', lambda: next((link_in(b, 'c') for n, h, b in mails() if link_in(b, 'c')), None), 60, 0.3)
    status, options = stranger.json(claim + '/passkey/options'); passkey = Authenticator()
    status, result = stranger.json(claim + '/passkey', passkey.create(options))
    check('the world is claimed once, by its mailbox', status == 200 and result.get('ok'), (status, result))
    status, _, page = stranger.get(f'/w/{peer}')
    check('the owner page lists every inquirer\'s proposals, separately', all(f'Recorded by {n}' in page for n, _ in inquirers), page[:600])
    stranger.form(f'/w/{peer}/publish/{A}/widgets', **{'slot.price': '39.50 per unit', 'slot.capacity': '500 a month'})
    stranger.form(f'/w/{peer}/publish/0x12/brackets', **{'slot.price': '11.80 per unit', 'slot.also': f'/{peer}/our/{A}/widgets'})
    stranger.form(f'/w/{peer}/aside/0x12/brackets')
    for node, need, expect in [(A, 'widgets', '39.50 per unit'), ('0x12', 'brackets', '11.80 per unit')]:
        (her, s) = wait(f'{node} acquires at /her', lambda n=node, d=need: (lambda r: r if r.get('exists') else None)(world_rpc(ports[n], 'read', path=f'/{n}/her/{peer}/{d}', care='x')), 120, 0.5)
        check(f'{node} observes its own publication at /her/{peer}/{need}', her['properties'].get('/price') == expect and her['properties'].get('/publisher') == peer, her['properties'])
    time.sleep(3)
    cross = (world_rpc(ports[A], 'read', path=f'/{A}/her/{peer}/brackets', care='x'), world_rpc(ports['0x12'], 'read', path=f'/0x12/her/{peer}/widgets', care='x'))
    check('neither inquirer observes what was published to the other', not cross[0].get('exists') and not cross[1].get('exists'), cross)
    aside = world_rpc(pb, 'read', path=f'/{peer}/our/0x12/declined/brackets', care='x')
    check('a proposal set aside is answered by a publication of the decline, by the owner', aside.get('exists'), aside)
    related = world_rpc(pb, 'read', path=f'/{peer}/our/0x12/brackets', care='x')['properties']
    check('the owner related two descriptions by a reference of its own', related.get('/also') == f'/{peer}/our/{A}/widgets', related)
    after = {c['path']: c['reference'] for c in children(pb, f'/{peer}/her/{A}/understood')}
    hist = world_rpc(pb, 'history', path=f'/{peer}/her/{A}/understood/widgets', limit=5)
    check("what Northstar published is intact under the owner's answers", hist['versions'][-1]['properties'].get('/price', '').startswith('Northstar was quoted') and set(before) == set(after), (before, after))
    events = [e for e in world_rpc(pb, 'history', after=0, limit=60)['events']]
    whos = {e['who'] for e in events}
    check('the acquisitions and the owner are distinct principals in the history', 'owner' in whos and len(whos) >= 2, whos)
    # one person, one world: Allied reaches a second address of theirs; opened on the device that claimed the
    # first, the link offers to add it, one click folds the reservation in, and Allied's record names the world
    second_box, (o2, a2) = 'sales@precision-two.example.test', tokens['0x12']
    proxy('0x12', a2, 'write', records=[
        {'path': '/0x12/suppliers/precision_sales', 'slots': {'refers': '/0x12/needs/brackets', 'note': 'their sales desk; anywhere in the world, not under /relationships'}},
        {'path': '/0x12/suppliers/precision_sales/identifiers/email', 'slots': {'value': second_box}},
        {'path': f'/0x12/our/{G}/requests/brackets_sales', 'slots': {'do': 'send', 'channel': 'email', 'to': second_box, 'about': '/0x12/needs/brackets', 'relationship': '/0x12/suppliers/precision_sales',
                                                                   'subject': 'brackets', 'text': 'Allied Metals asks your sales desk too.'}}])
    (res2, s) = wait('the result for the second address', lambda: result_of(ports['0x12'], '0x12', 'brackets_sales'), 90, 0.5)
    second = next(w['node'] for w in registry()['worlds'] if w['contact'] == second_box)
    check('the second address is a reservation of its own until the person says otherwise', second != peer, (second, peer))
    invite2 = next(link_in(b, 'i') for n, h, b in mails() if second_box in h.get('to', '') and link_in(b, 'i'))
    stranger.form(invite2 + '/claim')
    (claim2, s) = wait('the claim mail to the second address', lambda: next((link_in(b, 'c') for n, h, b in mails() if second_box in h.get('to', '') and link_in(b, 'c')), None), 60, 0.3)
    status, _, page = stranger.get(claim2)
    check('opened where they are signed in, the link offers to add the address to their world', status == 200 and 'Add sales@precision-two.example.test' in page and 'separate world' in page, page[:400])
    status, _, page = stranger.form(claim2 + '/fold')
    folded = next(w for w in registry()['worlds'] if w['node'] == second)
    check('one click folds the reservation into the world', folded.get('folded_into') == peer and second_box in next(w for w in registry()['worlds'] if w['node'] == peer).get('identifiers', []), folded)
    (named, s) = wait("Allied's record names the person's world", lambda: (lambda r: r if r.get('/peer') == peer else None)(world_rpc(ports['0x12'], 'read', path='/0x12/suppliers/precision_sales', care='x').get('properties', {})), 30, 0.5)
    check('the inquirer learns the world from its own record, wherever that record is', named.get('/folded_from') == second, named)
    report['inquirers'] = len(inquirers)
    log('MANY GATE PASSED ' + json.dumps(report))


try:
    if '--wake-only' in sys.argv:
        wake_only()
    elif '--many' in sys.argv:
        many()
    else:
        full()
except SystemExit as e:
    print(f'\n{e}', flush=True)
    for name in sorted(os.listdir(TEMP)):
        if name.startswith(('host-', 'gateway-')) and name.endswith('.log') or name == 'fixture.log':
            print(f'--- {name} (tail) ---'); print(open(os.path.join(TEMP, name), errors='replace').read()[-2500:])
    raise
finally:
    kill_everything(signal.SIGTERM)
    time.sleep(1); kill_everything(signal.SIGKILL)
    print('kept at', TEMP if KEEP else '(deleted)', flush=True)
    if not KEEP: shutil.rmtree(TEMP, ignore_errors=True)
