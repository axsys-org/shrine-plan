"""The relationship gate, against the shrine-mesa host.

--wake-only   the generic wake mechanism with the stub agent: an agent-declared wake fires on a time passing, on
              an event beneath a referenced name by an outside principal, and on an ask cell asking again; nothing
              fires for the agent's own writes, an unrelated relationship or a culled wake; every run is recorded;
              a wake declared before a kill -9 fires after the restart. One world. No domain words anywhere.

(default)     the relationship before and after adoption, with the inbox fixture playing Precision Works and the
              gate itself writing what the agent would write (deterministic; the real agent runs in the
              recording): an approved outreach mails and provisions a prospective world; the reply lands by
              threading as a conversation record by `mail`; observations cite it; a counter-offer goes out and is
              answered; the judgment cell beside the folder is answered; proposals are written into the peer's
              prospective world through a scoped token; everything survives a kill -9 and restart; the invitation
              shows the prospective namespace; the claim (mailbox, passkey) opens the owner page listing the
              proposals; publishing one writes /our/<inquirer>/<name> and its publication; the inquirer acquires
              it at /her/<peer>/<name> over Mesa; the scoped token is revoked; a later change by the owner arrives
              as the next case and makes the judgment ask again with no mail sent for it.

Flags: --keep, --bin <shrine-mesa>.
"""
import base64, hashlib, json, os, re, secrets, shutil, signal, socket, subprocess, sys, tempfile, time
from http.cookiejar import CookieJar
import urllib.error, urllib.parse, urllib.request
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = '/Users/ianchanner/shrine-base'
BIN = os.environ.get('SHRINE_MESA', '/Users/ianchanner/shrine-mesa/target/debug/shrine-mesa')
if '--bin' in sys.argv: BIN = sys.argv[sys.argv.index('--bin') + 1]
KEEP = '--keep' in sys.argv
os.makedirs(os.path.join(BASE, '.check'), exist_ok=True)
TEMP = tempfile.mkdtemp(prefix='relationship-', dir=os.path.join(BASE, '.check'))
HOST_PORT = 8400
ORIGIN = f'http://localhost:{HOST_PORT}'
RP_ID = 'localhost'
A = '0x11'
MAILBOX = 'precision@example.test'
SECRET = 'fixture-inbound-secret'
STATE, OUTBOX, WORLDS, CONFIG = (os.path.join(TEMP, d) for d in ('state', 'outbox', 'worlds', 'host.json'))
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
    return p if p and world_rpc(p, 'read', path='/' + node, care='x').get('exists') else None


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
    global host, fixture
    for p in (host, fixture):
        if p and p.poll() is None:
            os.kill(p.pid, sig); p.wait(timeout=30)
    subprocess.run(['pkill', f'-{int(sig)}', '-x', 'wisp']); time.sleep(1)
    subprocess.run(['pkill', f'-{int(sig)}', '-f', 'x/eden --node']); subprocess.run(['pkill', f'-{int(sig)}', '-f', 'shrine-mesa serve'])
    time.sleep(1)


def write_config(wake=None):
    cfg = {'listen': f'127.0.0.1:{HOST_PORT}', 'origin': ORIGIN, 'rp_id': RP_ID, 'name': 'Shrine pilot host', 'state': STATE, 'shrine': BASE,
           'mounts': ['net', 'mcp', 'probe'], 'worlds': WORLDS, 'ports': {'world': 8500, 'mesa': 9500, 'flow': 9600}, 'node_base': '0x20',
           'poll_ms': 300, 'mail': {'dir': OUTBOX, 'inbound_secret': SECRET}}
    if wake: cfg['wake'] = wake
    json.dump(cfg, open(CONFIG, 'w'), indent=1)


def start_host():
    global host, host_logs
    host_logs += 1
    out = open(os.path.join(TEMP, f'host-{host_logs}.log'), 'w')
    host = subprocess.Popen([BIN, 'host', '--config', CONFIG], stdout=out, stderr=subprocess.STDOUT, cwd=TEMP)
    def listening():
        if host.poll() is not None: raise SystemExit('host exited: ' + open(out.name).read()[-1500:])
        try:
            with socket.create_connection(('127.0.0.1', HOST_PORT), timeout=0.3): return True
        except OSError: return False
    wait('the host', listening, 30, 0.2)


def start_fixture():
    global fixture
    fixture = subprocess.Popen([sys.executable, os.path.join(HERE, 'fixtures', 'counterparty.py'), '--outbox', OUTBOX, '--hook', f'{ORIGIN}/hooks/mail/{SECRET}',
                                '--market', os.path.join(HERE, 'fixtures', 'market.json')], stdout=open(os.path.join(TEMP, 'fixture.log'), 'w'), stderr=subprocess.STDOUT)


def live_ref(path, care): return {'type': 'reference', 'value': f'/h/{care}/0/{len(path.strip("/").split("/"))}/{path.strip("/")}'}


def pinned(record): return {'type': 'reference', 'value': record['reference']}


def children(port, path): return world_rpc(port, 'read', path=path, care='y').get('children', [])


def conversation(port, folder=f'/{A}/relationships/precision/conversation'):
    return sorted(children(port, folder), key=lambda c: c['path'])


host, fixture, host_logs = None, None, 0
if subprocess.run(['pgrep', '-x', 'wisp'], capture_output=True).returncode == 0: raise SystemExit('a wisp is already running')
if not os.access(BIN, os.X_OK): raise SystemExit(f'no shrine-mesa binary at {BIN}')
for d in (STATE, OUTBOX, WORLDS): os.makedirs(d, exist_ok=True)


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
        {'path': f'/{A}/relationships/precision', 'slots': {'contact': 'precision@example.test'}},
        {'path': f'/{A}/relationships/allied', 'slots': {'contact': 'allied@example.test'}},
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
    proxy(A, mail, 'write', records=[{'path': f'/{A}/relationships/precision/conversation/m1', 'slots': {'from': 'precision@example.test', 'text': 'We can make 500 at 43.', 'at': at}}])
    (marks, s) = wait('the name wake', lambda: (lambda m: m if len(m) > before else None)(stub_markers(port)), 30, 0.3)
    check('the name wake fired with the changed path', any(m.get('/why') == 'precision moved' and 'conversation/m1' in m.get('/paths', '') for m in marks), marks)
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
    proxy(A, mail, 'write', records=[{'path': f'/{A}/relationships/precision/conversation/m2', 'slots': {'from': 'precision@example.test', 'text': '39.50 for a recurring order.', 'at': at}}])
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
    owner = cli('token', '--node', A, '--who', 'owner'); agent = cli('token', '--node', A, '--who', 'agent')
    start_host(); start_fixture()
    (pa, s) = wait('world A', lambda: up(A), 300, 2); log(f'A up in {s} s')
    stdlib = {c['path'].rsplit('/', 1)[1]: pinned(c) for c in world_rpc(pa, 'read', path=f'/{A}/weft/stdlib', care='y', limit=100)['children']}
    world_rpc(pa, 'write', who='owner', records=[{'path': f'/{A}/net/self', 'action': 'poke', 'slots': {'name': 'Northstar'}}])

    # --- 1 the relationship begins: a need, the folder, the standing approval, the first message
    proxy(A, owner, 'write', records=[
        {'path': f'/{A}/needs/widgets', 'slots': {'want': '500', 'maximum_price': '40 per unit', 'note': 'a supplier able to resume deliveries when production restarts'}},
        {'path': f'/{A}/needs/widgets/approval', 'slots': {'until': '2027-01-01T00:00:00Z', 'note': 'any outreach about widgets while I sleep'}}])
    proxy(A, agent, 'write', records=[
        {'path': f'/{A}/relationships/precision', 'slots': {'contact': MAILBOX, 'refers': f'/{A}/needs/widgets'}},
        {'path': f'/{A}/judgments/precision', 'slots': {'sys/weft': stdlib['ask'], 'sys/tack': live_ref(f'/{A}/relationships/precision', 'z'),
                                                        'prompt': f'Does this relationship satisfy /{A}/needs/widgets? Say ok or not, why, and when to look again.', 'model': 'any'}},
        {'path': f'/{A}/net/outreach/widgets_precision/request', 'slots': {'to': MAILBOX, 'about': f'/{A}/needs/widgets', 'relationship': f'/{A}/relationships/precision',
                                                                           'subject': 'widgets', 'note': 'Can you supply 500 widgets at $40/unit or less? We need a supplier who can resume fulfilling orders when production restarts.'}}])
    t0 = time.monotonic()
    (conv, s) = wait('the reply by mail', lambda: (lambda c: c if c else None)(conversation(pa)), 90, 0.5)
    report['ask_to_reply_s'] = round(time.monotonic() - t0, 2)
    reply = conv[0]; rp = reply['properties']
    check('the reply landed by threading as a conversation record by mail', rp.get('/channel') == 'email' and rp.get('/outreach') == 'widgets_precision' and rp.get('/in_reply_to') and '$43' in rp.get('/text', ''), rp)
    check('the reply is attributed and marked simulated', rp.get('/from') == MAILBOX and 'simulated' in rp.get('/text', '') and rp.get('/authenticated') == 'claimed', rp)
    sent = world_rpc(pa, 'read', path=f'/{A}/net/outreach/widgets_precision/sent', care='x')['properties']
    peer = sent.get('/peer'); check('sent names the prospective world reserved for the mailbox', peer and peer.startswith('0x'), sent)
    events = world_rpc(pa, 'history', after=0, limit=40)['events']
    check('the reply event carries principal mail', any(e['who'] == 'mail' and any(p.startswith(f'/{A}/relationships/precision/conversation/') for p in e['touched']) for e in events), [(e['who'], e['touched'][-1]) for e in events][-5:])
    # the agent's observation, a counter-offer
    proxy(A, agent, 'write', records=[
        {'path': f'/{A}/relationships/precision/observations/o1', 'slots': {'about': 'widgets', 'said': 'can make 500; current price 43 per unit', 'by': MAILBOX, 'at': rp.get('/at', ''), 'source': pinned(reply)}},
        {'path': f'/{A}/net/outreach/widgets_precision/request', 'action': 'poke', 'slots': {'note': 'Would you consider $39.50/unit for a recurring arrangement?'}}])
    (conv, s) = wait('the answer to the counter-offer', lambda: (lambda c: c if len(c) >= 2 else None)(conversation(pa)), 60, 0.5)
    rp2 = conv[1]['properties']
    check('the counter-offer was mailed again on the same thread and answered', '39.5' in rp2.get('/text', '') and '30 days' in rp2.get('/text', ''), rp2)
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
    # the proposals in the peer's prospective world, through a scoped token
    (pb, s) = wait('the prospective world', lambda: up(peer), 400, 2); log(f'peer {peer} up in {s} s')
    status, got = Client().json(f'/w/{A}/peers/{peer}/token', {}, {'Authorization': 'Bearer ' + agent})
    check('a scoped token for the prospective world', status == 200 and got.get('scope') == f'/{peer}/proposed/relationships/{A}', (status, got))
    scoped = got['token']
    st, _ = proxy(peer, scoped, 'write', records=[
        {'path': f'/{peer}/proposed/relationships/{A}', 'slots': {'inquiry': f'/{A}/needs/widgets', 'contact': 'owner-a@example.test', 'note': 'what Northstar recorded from your correspondence'}},
        {'path': f'/{peer}/proposed/relationships/{A}/conversation/m1', 'slots': {'from': 'owner-a@example.test', 'text': 'Can you supply 500 widgets at $40/unit or less?', 'at': rp.get('/at', '')}},
        {'path': f'/{peer}/proposed/relationships/{A}/conversation/m2', 'slots': {'from': MAILBOX, 'text': rp2.get('/text', ''), 'at': rp2.get('/at', '')}},
        {'path': f'/{peer}/proposed/relationships/{A}/proposed_terms/widgets', 'slots': {'price': '39.50 per unit', 'valid': '30 days', 'capacity': 'unconfirmed', 'source': pinned(conv[1])}},
        {'path': f'/{peer}/proposed/relationships/{A}/proposed_capabilities/widgets', 'slots': {'can_make': '500 widgets', 'lead_time': '14 days', 'source': pinned(reply)}}])
    check('the proposals are written under the scope', st == 200, st)
    provisional = {c['path']: (c['reference'], c['properties']) for c in children(pb, f'/{peer}/proposed/relationships/{A}/proposed_terms')}
    report['proposals'] = len(provisional)
    log('test 1 holds: the relationship exists before the counterparty joins')

    # --- 2 persistence: kill everything, restart, the records and the wakes are there
    kill_everything(signal.SIGKILL); log('host, fixture, worlds and services killed')
    t0 = time.monotonic(); start_host(); start_fixture()
    wait('both worlds back', lambda: up(A) and up(peer), 300, 1); report['restart_s'] = round(time.monotonic() - t0, 2)
    check('the conversation, the judgment and the wakes survive', len(conversation(pa)) == 2 and world_rpc(pa, 'read', path=f'/x/{A}/judgments/precision', care='x').get('exists')
          and len(children(pa, f'/{A}/agent/wakes')) == 2, 'after restart')
    log('test 2 holds: nothing lives in a process')

    # --- 4 claiming: the invitation shows the prospective namespace; claim, passkey, review, publish
    invite = next(link_in(b, 'i') for n, h, b in mails() if link_in(b, 'i'))
    stranger = Client()
    status, _, page = stranger.get(invite)
    check('the invitation shows the inquiry and what was recorded', status == 200 and 'Northstar' in page and '39.50 per unit' in page and 'proposed_terms' in page and 'Claim this world' in page, (status, page[:300]))
    status, _, page = stranger.form(invite + '/claim')
    check('the claim mails a verification link', status == 200, (status, page[:200]))
    (claim, s) = wait('the claim mail', lambda: next((link_in(b, 'c') for n, h, b in mails() if link_in(b, 'c')), None), 30, 0.3)
    status, options = stranger.json(claim + '/passkey/options')
    passkey = Authenticator()
    status, result = stranger.json(claim + '/passkey', passkey.create(options))
    check('the mailbox is verified and a passkey registered', status == 200 and result.get('ok'), (status, result))
    st, why = proxy(peer, scoped, 'write', records=[{'path': f'/{peer}/proposed/relationships/{A}/proposed_terms/late', 'slots': {'price': '1'}}])
    check('the provisional writer lost its authority at the claim', st in (401, 403), (st, why))
    status, _, page = stranger.get(f'/w/{peer}')
    check('the owner page lists the proposals for review', status == 200 and 'Recorded by 0x11' in page and 'Publish to 0x11' in page and '39.50 per unit' in page, page[:500])
    status, _, page = stranger.form(f'/w/{peer}/publish/{A}/widgets', **{'slot.price': '39.50 per unit', 'slot.valid': '30 days', 'slot.capacity': '500 a month confirmed', 'slot.lead_time': '14 days'})
    check('publishing writes the owned name', status in (200, 303), status)
    own = world_rpc(pb, 'read', path=f'/{peer}/our/{A}/widgets', care='x')['properties']
    check('/our/<inquirer>/widgets holds the corrected terms', own.get('/capacity') == '500 a month confirmed' and own.get('/price') == '39.50 per unit', own)
    pub = world_rpc(pb, 'read', path=f'/{peer}/net/publications/widgets_{A}', care='x')['properties']
    check('its publication names the path and the inquirer', pub.get('/path') == f'/{peer}/our/{A}/widgets' and pub.get('/to') == A, pub)
    hist = world_rpc(pb, 'history', path=f'/{peer}/proposed/relationships/{A}/proposed_terms/widgets', limit=10)
    first = hist['versions'][-1]['properties']
    check('the provisional record keeps its first case as the agent wrote it', first.get('/capacity') == 'unconfirmed' and hist['versions'][0]['properties'].get('/stance') == 'published', hist['versions'])
    events = world_rpc(pb, 'history', after=0, limit=40)['events']
    check('the provisional writes stay attributed to the inquirer\'s agent, the publication to the owner',
          any(e['who'] == f'agent_{A}' for e in events) and any(e['who'] == 'owner' and any('/our/' in p for p in e['touched']) for e in events), [(e['who'], e['touched'][-1]) for e in events][-6:])
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
    report['mails'] = len(mails())
    log('RELATIONSHIP GATE PASSED ' + json.dumps(report))


try:
    if '--wake-only' in sys.argv:
        wake_only()
    else:
        full()
except SystemExit as e:
    print(f'\n{e}', flush=True)
    for name in sorted(os.listdir(TEMP)):
        if name.startswith('host-') and name.endswith('.log') or name == 'fixture.log':
            print(f'--- {name} (tail) ---'); print(open(os.path.join(TEMP, name), errors='replace').read()[-2500:])
    raise
finally:
    kill_everything(signal.SIGTERM)
    time.sleep(1); subprocess.run(['pkill', '-x', 'wisp'])
    print('kept at', TEMP if KEEP else '(deleted)', flush=True)
    if not KEEP: shutil.rmtree(TEMP, ignore_errors=True)
