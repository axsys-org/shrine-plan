"""Phase-2 gate: hosting and claiming.

The host service (`shrine-mesa host`) boots the inquirer's world A (0x11) and, behind a stranger's first
answer, a recipient world; an agent proposes an outreach in A, the owner approves it through the host's
token-bearing MCP route, the host mails one link; a software WebAuthn authenticator stands in for the
stranger's browser: it answers through the link, claims the new world through the mailed verification link
and a passkey, edits the answer, mints an agent token, and after a kill -9 of host, worlds and services
signs in again with the passkey alone. Every answer lands in A through phase 1's acquisition.

Flags: --keep (leave the temp directory and logs), --bin <shrine-mesa binary>, --firewalled (assert the world ports
are closed on the LAN address, for a pilot host with its firewall up).
"""
import base64, hashlib, http.cookiejar, json, os, re, secrets, shutil, signal, socket, subprocess, sys, tempfile, time
import urllib.error, urllib.parse, urllib.request
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

BASE = '/Users/ianchanner/shrine-base'
BIN = os.environ.get('SHRINE_MESA', '/Users/ianchanner/shrine-mesa/target/debug/shrine-mesa')
if '--bin' in sys.argv: BIN = sys.argv[sys.argv.index('--bin') + 1]
KEEP = '--keep' in sys.argv
os.makedirs(os.path.join(BASE, '.check'), exist_ok=True)
TEMP = tempfile.mkdtemp(prefix='phase2-', dir=os.path.join(BASE, '.check'))
HOST_PORT = 8400
ORIGIN = f'http://localhost:{HOST_PORT}'
RP_ID = 'localhost'
A = '0x11'
MAILBOX = 'shop@example.test'
report, t_start = {}, time.monotonic()


def log(s): print(f'[{time.monotonic() - t_start:7.1f}] {s}', flush=True)


def b64u(b): return base64.urlsafe_b64encode(b).rstrip(b'=').decode()


def unb64u(s): return base64.urlsafe_b64decode(s + '=' * (-len(s) % 4))


# --- a minimal CBOR encoder (CTAP2 canonical key order), enough for an attestation object -----------------
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
    """A software passkey: one P-256 key, user present and verified, attestation none."""
    def __init__(self):
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.cred_id = secrets.token_bytes(16)
        self.count = 0

    def cose_key(self):
        n = self.key.public_key().public_numbers()
        return cbor({1: 2, 3: -7, -1: 1, -2: n.x.to_bytes(32, 'big'), -3: n.y.to_bytes(32, 'big')})

    def auth_data(self, flags, attested):
        data = hashlib.sha256(RP_ID.encode()).digest() + bytes([flags]) + self.count.to_bytes(4, 'big')
        if attested: data += bytes(16) + len(self.cred_id).to_bytes(2, 'big') + self.cred_id + self.cose_key()
        return data

    def create(self, options):
        o = options.get('publicKey', options)
        assert any(p.get('alg') == -7 for p in o['pubKeyCredParams']), o['pubKeyCredParams']
        assert o['rp']['id'] == RP_ID, o['rp']
        client = json.dumps({'type': 'webauthn.create', 'challenge': o['challenge'], 'origin': ORIGIN, 'crossOrigin': False}).encode()
        att = cbor({'fmt': 'none', 'attStmt': {}, 'authData': self.auth_data(0x45, True)})
        return {'id': b64u(self.cred_id), 'rawId': b64u(self.cred_id), 'type': 'public-key',
                'response': {'attestationObject': b64u(att), 'clientDataJSON': b64u(client)}, 'clientExtensionResults': {}}

    def get(self, options):
        o = options.get('publicKey', options)
        allowed = [c['id'] for c in o.get('allowCredentials', [])]
        assert b64u(self.cred_id) in allowed, allowed
        self.count += 1
        client = json.dumps({'type': 'webauthn.get', 'challenge': o['challenge'], 'origin': ORIGIN, 'crossOrigin': False}).encode()
        ad = self.auth_data(0x05, False)
        sig = self.key.sign(ad + hashlib.sha256(client).digest(), ec.ECDSA(hashes.SHA256()))
        return {'id': b64u(self.cred_id), 'rawId': b64u(self.cred_id), 'type': 'public-key',
                'response': {'authenticatorData': b64u(ad), 'clientDataJSON': b64u(client), 'signature': b64u(sig), 'userHandle': None},
                'clientExtensionResults': {}}


# --- HTTP -----------------------------------------------------------------------------------------------------
class Client:
    """A browser session: its own cookie jar; answers (status, headers, body)."""
    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def call(self, method, url, data=None, headers=None, timeout=60):
        req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
        try:
            with self.opener.open(req, timeout=timeout) as r:
                return r.status, dict(r.headers), r.read().decode(errors='replace')
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), e.read().decode(errors='replace')

    def get(self, path): return self.call('GET', ORIGIN + path)

    def form(self, path, **fields):
        return self.call('POST', ORIGIN + path, urllib.parse.urlencode(fields).encode(), {'Content-Type': 'application/x-www-form-urlencoded'})

    def json(self, path, body=None, headers=None):
        h = {'Content-Type': 'application/json'}; h.update(headers or {})
        status, hdrs, text = self.call('POST', ORIGIN + path, json.dumps(body if body is not None else {}).encode(), h)
        try: return status, json.loads(text)
        except json.JSONDecodeError: return status, text


def rpc_body(name, **args):
    return {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'mcp/' + name, 'arguments': args}}


def world_rpc(port, name, **args):
    """A loopback call on a world: what an agent on the host machine does."""
    body = json.dumps(rpc_body(name, **args)).encode()
    with urllib.request.urlopen(urllib.request.Request(f'http://127.0.0.1:{port}/mcp', body, {'Content-Type': 'application/json'}), timeout=120) as r:
        reply = json.load(r)
    res = reply['result']
    if res.get('isError'): raise RuntimeError(str(res)[:500])
    return res['structuredContent']


def proxy_rpc(client, node, token, name, **args):
    """The host's token-bearing MCP route; answers (status, result or text)."""
    headers = {'Authorization': 'Bearer ' + token} if token else {}
    status, reply = client.json(f'/w/{node}/mcp', rpc_body(name, **args), headers)
    if status == 200 and isinstance(reply, dict) and 'result' in reply:
        res = reply['result']
        if res.get('isError'): raise RuntimeError(str(res)[:500])
        return status, res['structuredContent']
    return status, reply


def wait_for(what, pred, timeout=120, every=0.5):
    t = time.monotonic()
    while time.monotonic() - t < timeout:
        try:
            v = pred()
        except Exception:
            v = None
        if v: return v, round(time.monotonic() - t, 2)
        time.sleep(every)
    raise SystemExit(f'timed out after {timeout} s waiting for {what}')


def check(label, cond, detail=''):
    if not cond: raise SystemExit(f'FAILED: {label} {str(detail)[:600]}')
    log(f'ok: {label}')


# --- the host, worlds and mail ------------------------------------------------------------------------------
STATE, OUTBOX, WORLDS = (os.path.join(TEMP, d) for d in ('state', 'outbox', 'worlds'))
CONFIG = os.path.join(TEMP, 'host.json')
host_proc, host_log_n = None, 0


def write_config():
    json.dump({'listen': f'127.0.0.1:{HOST_PORT}', 'origin': ORIGIN, 'rp_id': RP_ID, 'name': 'Shrine pilot host',
               'state': STATE, 'shrine': BASE, 'mounts': ['net', 'mcp', 'probe'], 'worlds': WORLDS,
               'ports': {'world': 8500, 'mesa': 9500, 'flow': 9600}, 'node_base': '0x20', 'poll_ms': 300,
               'mail': {'dir': OUTBOX}}, open(CONFIG, 'w'), indent=1)


def host_cli(*args):
    r = subprocess.run([BIN, 'host', *args, '--config', CONFIG], capture_output=True, text=True)
    if r.returncode != 0: raise SystemExit(f'host {" ".join(args)} failed: {r.stdout[-800:]} {r.stderr[-800:]}')
    return r.stdout.strip()


def start_host():
    global host_proc, host_log_n
    host_log_n += 1
    out = open(os.path.join(TEMP, f'host-{host_log_n}.log'), 'w')
    host_proc = subprocess.Popen([BIN, 'host', '--config', CONFIG], stdout=out, stderr=subprocess.STDOUT, cwd=TEMP)
    def up():
        if host_proc.poll() is not None: raise SystemExit(f'host exited: {open(out.name).read()[-1500:]}')
        try:
            with socket.create_connection(('127.0.0.1', HOST_PORT), timeout=0.3): return True
        except OSError: return False
    _, s = wait_for('the host to listen', up, 30, 0.2)
    return s


def registry(): return json.load(open(os.path.join(STATE, 'registry.json')))


def world_port(node):
    for w in registry()['worlds']:
        if w['node'] == node: return w['port']
    return None


def world_up(node):
    port = world_port(node)
    if not port: return None
    try: return world_rpc(port, 'read', path='/' + node, care='x').get('exists') and port
    except Exception: return None


def mails():
    out = []
    for name in sorted(os.listdir(OUTBOX)) if os.path.isdir(OUTBOX) else []:
        text = open(os.path.join(OUTBOX, name), errors='replace').read()
        head, _, body = text.partition('\n\n')
        headers = {k.strip().lower(): v.strip() for k, v in (line.split(':', 1) for line in head.splitlines() if ':' in line)}
        out.append((name, headers, body))
    return out


def link_in(body, kind):
    m = re.search(re.escape(ORIGIN) + '/' + kind + r'/[A-Za-z0-9_-]+', body)
    return m.group(0)[len(ORIGIN):] if m else None


def rss_mb(pattern):
    out = subprocess.run(['pgrep', '-x', pattern], capture_output=True, text=True).stdout.split()
    total = 0
    for pid in out:
        r = subprocess.run(['ps', '-o', 'rss=', '-p', pid], capture_output=True, text=True).stdout.strip()
        total += int(r) // 1024 if r else 0
    return total


def kill_everything(sig=signal.SIGKILL):
    global host_proc
    if host_proc and host_proc.poll() is None:
        os.kill(host_proc.pid, sig); host_proc.wait(timeout=30)
    subprocess.run(['pkill', f'-{int(sig)}', '-x', 'wisp'])
    time.sleep(1)
    subprocess.run(['pkill', f'-{int(sig)}', '-f', 'x/eden --node'])
    subprocess.run(['pkill', f'-{int(sig)}', '-f', 'shrine-mesa serve'])
    time.sleep(1)


def lan_address():
    out = subprocess.run(['ifconfig'], capture_output=True, text=True).stdout
    for m in re.finditer(r'inet (\d+\.\d+\.\d+\.\d+)', out):
        if not m.group(1).startswith('127.'): return m.group(1)
    return None


def refused_on(addr, port):
    try:
        with socket.create_connection((addr, port), timeout=1): return False
    except OSError: return True


# --- the run -------------------------------------------------------------------------------------------------
if subprocess.run(['pgrep', '-x', 'wisp'], capture_output=True).returncode == 0: raise SystemExit('a wisp is already running')
if not os.access(BIN, os.X_OK): raise SystemExit(f'no shrine-mesa binary at {BIN}')
for d in (STATE, OUTBOX, WORLDS): os.makedirs(d, exist_ok=True)
write_config()
try:
    host_cli('add-world', '--node', A, '--name', 'Northstar', '--contact', 'owner-a@example.test')
    owner_a = host_cli('token', '--node', A, '--who', 'owner')
    check('a token is one line of base64url', re.fullmatch(r'[A-Za-z0-9_-]{40,}', owner_a), owner_a[:80])
    report['host_start_s'] = start_host(); log(f'host listening after {report["host_start_s"]} s')
    port_a, s = wait_for('world A to boot', lambda: world_up(A), 300, 1); report['boot_A_s'] = s; log(f'A up on {port_a} in {s} s')

    # The agent proposes; nothing is mailed before the owner approves.
    world_rpc(port_a, 'write', who='agent', records=[
        {'path': f'/{A}/needs/aluminum', 'slots': {'material': '6061-T6 aluminum plate, 12 mm', 'quantity': '400 kg a month', 'from': 'December 2026'}},
        {'path': f'/{A}/net/outreach/o1/request', 'slots': {'to': MAILBOX, 'about': f'/{A}/needs/aluminum',
                                                            'note': 'Northstar machines fixtures and needs a steady plate supplier. Could you supply this, and on what terms?'}}])
    time.sleep(2.5)
    check('no mail before the approval', not mails(), mails())
    status, _ = proxy_rpc(Client(), A, None, 'read', path=f'/{A}/net/self', care='x')
    check('the MCP route without a token answers 401', status == 401, status)
    status, _ = proxy_rpc(Client(), A, 'x' * 43, 'read', path=f'/{A}/net/self', care='x')
    check('the MCP route with an unknown token answers 401', status == 401, status)
    t0 = time.monotonic()
    status, ev = proxy_rpc(Client(), A, owner_a, 'write', who='agent', records=[{'path': f'/{A}/net/outreach/o1/approval', 'slots': {'note': 'go ahead'}}])
    check('the owner approves through the token route', status == 200 and 'epoch' in ev, (status, ev))
    events = world_rpc(port_a, 'history', after=ev['epoch'] - 1, limit=3)['events']
    check('the proxy forced who to the token principal', events and events[0]['who'] == 'owner', events)
    (name, headers, body), s = wait_for('the invitation mail', lambda: next(iter(mails()), None), 60, 0.3)
    report['approval_to_mail_s'] = round(time.monotonic() - t0, 2)
    check('the invitation went to the request mailbox', headers.get('to', '').endswith(MAILBOX), headers)
    invite = link_in(body, 'i'); check('the mail carries one invitation link', invite, body[:300])
    sent = world_rpc(port_a, 'read', path=f'/{A}/net/outreach/o1/sent', care='x')
    check('the host recorded sent in A', sent.get('exists') and sent['properties'].get('/at'), sent)

    # The stranger answers through the link.
    stranger = Client()
    status, _, page = stranger.get(invite)
    check('the invitation page shows the inquiry', status == 200 and 'Northstar' in page and '6061-T6' in page and 'steady plate supplier' in page, (status, page[:400]))
    answer1 = 'We stock 6061-T6 plate in 12 mm. 400 kg a month is fine from December; 8.50 per kg, two weeks lead time.'
    t0 = time.monotonic()
    status, _, page = stranger.form(invite, text=answer1)
    check('the answer is taken', status == 200 and 'verif' in page.lower(), (status, page[:400]))
    status, _, page = stranger.form(invite, text='again')
    check('the link takes one answer only', status == 410, status)
    (node_b, port_b), s = wait_for('the recipient world', lambda: next(((w['node'], w['port']) for w in registry()['worlds'] if w['node'] != A and world_up(w['node'])), None), 400, 2)
    report['boot_B_s'] = s; log(f'recipient world {node_b} up on {port_b} in {s} s')
    acquired = lambda n: (lambda: (lambda r: r if r.get('exists') and int(r['properties'].get('/remote_case', '0')) >= n else None)(world_rpc(port_a, 'read', path=f'/{A}/net/names/{node_b}/o1/current', care='x')))
    cur, s = wait_for('the answer acquired in A', acquired(1), 300, 0.5)
    report['answer_to_acquired_s'] = round(time.monotonic() - t0, 2)
    check('A holds the answer under the recipient name', cur['properties'].get('/text') == answer1 and cur['properties'].get('/publisher') == node_b, cur['properties'])
    case1 = int(cur['properties']['/remote_case'])
    own = world_rpc(port_b, 'read', path=f'/{node_b}/net/answers/o1', care='x')['properties']
    check('the answer is a record under the recipient root', own.get('/text') == answer1 and own.get('/to') == A, own)
    self_b = world_rpc(port_b, 'read', path=f'/{node_b}/net/self', care='x')['properties']
    check('the recipient self carries the contact', self_b.get('/contact') == MAILBOX, self_b)

    # The claim: the mailed verification link, then a passkey.
    (name, headers, body), _ = wait_for('the claim mail', lambda: next(((n, h, b) for n, h, b in mails() if link_in(b, 'c')), None), 60, 0.3)
    check('the claim went to the same mailbox', headers.get('to', '').endswith(MAILBOX), headers)
    claim = link_in(body, 'c')
    t0 = time.monotonic()
    status, _, page = stranger.get(claim)
    check('the claim page offers a passkey and states the limits', status == 200 and 'passkey' in page.lower() and 'key' in page.lower(), (status, page[:400]))
    status, options = stranger.json(claim + '/passkey/options')
    check('creation options', status == 200 and isinstance(options, dict), (status, options))
    passkey = Authenticator()
    status, result = stranger.json(claim + '/passkey', passkey.create(options))
    check('the passkey is registered and a session opens', status == 200 and result.get('ok') and result.get('next') == f'/w/{node_b}', (status, result))
    report['claim_to_session_s'] = round(time.monotonic() - t0, 2)
    status, _, page = stranger.get(f'/w/{node_b}')
    check('the owner page shows the answer', status == 200 and answer1 in page, (status, page[:400]))
    status, _, _ = stranger.get(claim)
    check('the claim link is spent', status == 404, status)
    self_b = world_rpc(port_b, 'read', path=f'/{node_b}/net/self', care='x')['properties']
    check('self records the verification and the publisher key', self_b.get('/verified') and re.fullmatch(r'[0-9a-f]{64}', self_b.get('/publisher', '')), self_b)

    # The owner edits; the inquirer acquires the next case.
    answer2 = answer1.replace('8.50', '8.20')
    t0 = time.monotonic()
    status, _, page = stranger.form(f'/w/{node_b}/answers/o1', text=answer2)
    check('the edit is taken', status in (200, 303, 302), status)
    cur, s = wait_for('the edit acquired in A', acquired(case1 + 1), 120, 0.3)
    report['edit_to_acquired_s'] = round(time.monotonic() - t0, 2)
    check('A holds the edited answer as the next case', cur['properties'].get('/text') == answer2, cur['properties'])
    case2 = int(cur['properties']['/remote_case'])

    # The agent token: the owner's world only.
    status, _, page = stranger.form(f'/w/{node_b}/token')
    m = re.search(r'[A-Za-z0-9_-]{43}', page)
    check('a token is minted and shown once', status == 200 and m, (status, page[:400]))
    token_b = m.group(0)
    status, rec = proxy_rpc(Client(), node_b, token_b, 'read', path=f'/{node_b}/net/answers/o1', care='x')
    check('the token reads its own world', status == 200 and rec['properties'].get('/text') == answer2, (status, rec))
    status, _ = proxy_rpc(Client(), A, token_b, 'read', path=f'/{A}/net/self', care='x')
    check('the token is refused at another node', status == 403, status)
    status, ev = proxy_rpc(Client(), node_b, token_b, 'write', who='host', records=[{'path': f'/{node_b}/net/self', 'action': 'poke', 'slots': {'name': 'Shop B'}}])
    events = world_rpc(port_b, 'history', after=ev['epoch'] - 1, limit=3)['events']
    check('a token write carries the token principal, not the claimed who', events and events[0]['who'] == 'owner', events)
    status, _, _ = Client().get(f'/w/{A}')
    check('a session for one node does not open another', stranger.get(f'/w/{A}')[0] == 404, stranger.get(f'/w/{A}')[0])

    # Nothing else of the host is reachable: the host listens on loopback (Caddy fronts it in production), the
    # Mesa sockets are loopback, and the worlds' ports are measured: the runtime binds every interface at this
    # commit, so on a pilot host the firewall closes them (README, "Deployment"); --firewalled asserts it.
    lan = lan_address()
    if lan:
        check(f'the host port refuses connections on the LAN address {lan}', refused_on(lan, HOST_PORT), HOST_PORT)
        for w in registry()['worlds']:
            for key in ('mesa', 'flow'):
                addr = str(w.get(key, ''))
                check(f'{w["node"]} {key} socket is loopback', addr.startswith('127.0.0.1:'), addr)
        open_worlds = [label for label, port in (('A', port_a), ('B', port_b)) if not refused_on(lan, port)]
        report['world_ports_open_on_lan'] = open_worlds
        if '--firewalled' in sys.argv: check('the world ports refuse connections on the LAN address', not open_worlds, open_worlds)
        else: log(f'world ports accepting on {lan}: {open_worlds or "none"} (the firewall closes them on a pilot host)')
        report['lan_checked'] = lan
    else:
        log('no LAN address on this machine; the reachability check is skipped'); report['lan_checked'] = None
    for path in ('/', f'/x/{A}/net/stale', '/mcp', f'/w/{A}/mcp', '/i/', '/state/registry.json', f'/w/{node_b}/../../state/registry.json'):
        status, _, _ = Client().get(path)
        check(f'{path} answers 404', status == 404, status)

    # kill -9 everything, restart the host, return without cookies.
    report['rss_mb_before_kill'] = {'wisp': rss_mb('wisp'), 'shrine-mesa': rss_mb('shrine-mesa')}
    kill_everything(); log('host, worlds and services killed with -9')
    t0 = time.monotonic()
    start_host()
    _, s = wait_for('both worlds back', lambda: world_up(A) and world_up(node_b), 300, 1)
    report['restart_all_s'] = round(time.monotonic() - t0, 2); log(f'host and both worlds back in {report["restart_all_s"]} s')
    returning = Client()
    status, _, page = returning.get(f'/w/{node_b}')
    check('without a session the owner page asks for the passkey', status == 200 and answer2 not in page and 'passkey' in page.lower(), (status, page[:300]))
    status, options = returning.json(f'/w/{node_b}/login/options')
    check('login options name the registered passkey', status == 200 and any(c['id'] == b64u(passkey.cred_id) for c in options.get('publicKey', options).get('allowCredentials', [])), (status, options))
    status, result = returning.json(f'/w/{node_b}/login', passkey.get(options))
    check('the passkey alone signs the owner in', status == 200 and result.get('ok'), (status, result))
    status, _, page = returning.get(f'/w/{node_b}')
    check('the owner page is back with the edited answer', status == 200 and answer2 in page, (status, page[:300]))
    answer3 = answer2 + ' Certificates on request.'
    t0 = time.monotonic()
    returning.form(f'/w/{node_b}/answers/o1', text=answer3)
    cur, s = wait_for('the third case acquired in A', acquired(case2 + 1), 120, 0.3)
    report['edit_after_restart_to_acquired_s'] = round(time.monotonic() - t0, 2)
    check('A holds the third case', cur['properties'].get('/text') == answer3, cur['properties'])
    hist = world_rpc(port_a, 'history', path=f'/{A}/net/names/{node_b}/o1/current', limit=10)
    check('A holds exactly the three cases, newest first', [v['properties'].get('/text') for v in hist['versions']] == [answer3, answer2, answer1], [v['properties'].get('/text') for v in hist['versions']])
    status, rec = proxy_rpc(Client(), node_b, token_b, 'read', path=f'/{node_b}/net/answers/o1', care='x')
    check('the token still reads after the restart', status == 200 and rec['properties'].get('/text') == answer3, (status, rec))
    report['rss_mb_after'] = {'wisp': rss_mb('wisp'), 'shrine-mesa': rss_mb('shrine-mesa')}
    report['recipient'] = node_b
    log('PHASE 2 GATE PASSED ' + json.dumps(report))
except SystemExit as e:
    print(f'\n{e}', flush=True)
    for name in sorted(os.listdir(TEMP)):
        if name.startswith('host-') and name.endswith('.log'):
            print(f'--- {name} (tail) ---'); print(open(os.path.join(TEMP, name), errors='replace').read()[-3000:])
    raise
finally:
    kill_everything(signal.SIGTERM)
    time.sleep(2); subprocess.run(['pkill', '-x', 'wisp'])
    print('kept at', TEMP if KEEP else '(deleted)', flush=True)
    if not KEEP: shutil.rmtree(TEMP, ignore_errors=True)
