"""Private-key capability adapter. No wallet policy, RPC, encoding or journal."""
import hmac
import json
import os
from pathlib import Path
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from eth_account import Account
from eth_keys import keys

DEFAULT_HOME = Path.home() / '.local/share/shrine/ethereum-sepolia'


def private_file(path, text):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as out:
        out.write(text)
        out.flush()
        os.fsync(out.fileno())


def unlock(home):
    home = Path(home)
    for file in ('keystore.json', 'password'):
        if (home / file).stat().st_mode & 0o077:
            raise ValueError('Wallet files must be owner-only')
    return Account.from_key(Account.decrypt(json.loads((home / 'keystore.json').read_text()),
                                           (home / 'password').read_text()))


def create_wallet(home=DEFAULT_HOME):
    home = Path(home)
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(home, 0o700)
    if not (home / 'keystore.json').exists():
        account = Account.create()
        password = secrets.token_urlsafe(48)
        private_file(home / 'password', password)
        private_file(home / 'keystore.json', json.dumps(Account.encrypt(account.key, password)))
    return unlock(home).address


class Signer:
    def __init__(self, account):
        self.account = account
        self.key = keys.PrivateKey(bytes(account.key))

    def dispatch(self, request):
        if request == {'op': 'identity'}:
            return {'address': self.account.address.lower()}
        if set(request) != {'op', 'digest'} or request['op'] != 'sign':
            raise ValueError('Only identity and digest signing are host operations')
        digest = request['digest']
        if not isinstance(digest, str) or len(digest) != 66 or not digest.startswith('0x'):
            raise ValueError('Expected a 32-byte digest')
        raw = bytes.fromhex(digest[2:])
        if len(raw) != 32:
            raise ValueError('Expected a 32-byte digest')
        signature = self.key.sign_msg_hash(raw)
        return {'digest': '0x' + raw.hex(), 'parity': hex(signature.v),
                'r': hex(signature.r), 's': hex(signature.s)}


def server(signer, token, port=18545):
    if len(token) < 24:
        raise ValueError('Signer capability is too short')

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            self.connection.settimeout(10)
            if self.path != '/v0' or self.headers.get('Origin') or not hmac.compare_digest(
                    self.headers.get('Authorization', ''), 'Bearer ' + token):
                self.send_error(403)
                return
            try:
                size = int(self.headers.get('Content-Length', '-1'))
                if not 0 < size <= 4096 or self.headers.get('Transfer-Encoding'):
                    raise ValueError('Invalid signer request size')
                response = {'ok': True, 'result': signer.dispatch(json.loads(self.rfile.read(size)))}
            except Exception:
                response = {'ok': False, 'error': 'signer_rejected'}
            payload = json.dumps(response).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
    return ThreadingHTTPServer(('127.0.0.1', port), Handler)
