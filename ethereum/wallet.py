"""Dedicated test-account driver: durable signed intents and replayable logs."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from contextlib import contextmanager
from eth_account import Account
from web3 import Web3
from web3.exceptions import TransactionNotFound

SEPOLIA = 11155111
DEFAULT_HOME = Path.home() / '.local/share/shrine/ethereum-sepolia'
DEFAULT_RPC = 'https://ethereum-sepolia-rpc.publicnode.com'


def plain(value):
    if isinstance(value, bytes):
        return '0x' + value.hex()
    if isinstance(value, dict) or hasattr(value, 'items'):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(x) for x in value]
    return value


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def private_file(path, text):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as out:
        out.write(text)
        out.flush()
        os.fsync(out.fileno())


def create_wallet(home=DEFAULT_HOME):
    home = Path(home)
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(home, 0o700)
    import secrets
    if not (home / 'keystore.json').exists():
        account = Account.create()
        password = secrets.token_urlsafe(48)
        # The password file is machine-local automation custody, not a separate
        # security factor. Neither file belongs in a Shrine world or a repo.
        private_file(home / 'password', password)
        private_file(home / 'keystore.json', json.dumps(Account.encrypt(account.key, password)))
    return unlock(home).address


def unlock(home):
    home = Path(home)
    for file in ('keystore.json', 'password'):
        if (home / file).stat().st_mode & 0o077:
            raise ValueError('Wallet files must be readable only by their owner')
    return Account.from_key(Account.decrypt(json.loads((home / 'keystore.json').read_text()),
                                           (home / 'password').read_text()))


class Wallet:
    def __init__(self, web3, account, home, chain_id=SEPOLIA):
        self.w3, self.account, self.home, self.chain_id = web3, account, Path(home), chain_id
        self.home.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.home, 0o700)
        with self.locked() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS identity(chain INTEGER, address TEXT);
                CREATE TABLE IF NOT EXISTS intents(
                    id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, nonce INTEGER UNIQUE,
                    tx TEXT NOT NULL, raw TEXT NOT NULL, hash TEXT NOT NULL, receipt TEXT);
                CREATE TABLE IF NOT EXISTS streams(id TEXT PRIMARY KEY, config TEXT, cursor INTEGER);
                CREATE TABLE IF NOT EXISTS blocks(stream TEXT, number INTEGER, hash TEXT,
                    PRIMARY KEY(stream,number));
                CREATE TABLE IF NOT EXISTS events(stream TEXT, block INTEGER, key TEXT, data TEXT,
                    PRIMARY KEY(stream,key));
                CREATE TABLE IF NOT EXISTS deliveries(
                    stream TEXT PRIMARY KEY, payload TEXT NOT NULL);
            ''')
            identity = db.execute('SELECT chain,address FROM identity').fetchone()
            if identity and identity != (chain_id, account.address):
                raise ValueError('Journal belongs to a different chain or wallet')
            if not identity:
                db.execute('INSERT INTO identity VALUES (?,?)', (chain_id, account.address))
            db.commit()

    @contextmanager
    def locked(self):
        fd = os.open(self.home / 'driver.lock', os.O_RDWR | os.O_CREAT, 0o600)
        with os.fdopen(fd, 'a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            db = sqlite3.connect(self.home / 'wallet.sqlite3')
            os.chmod(self.home / 'wallet.sqlite3', 0o600)
            db.execute('PRAGMA synchronous=FULL')
            try:
                yield db
            finally:
                db.close()

    def check_chain(self):
        if self.w3.eth.chain_id != self.chain_id:
            raise ValueError('RPC chain does not match the configured test network')

    def status(self):
        self.check_chain()
        return {'chainId': self.chain_id, 'address': self.account.address,
                'balanceWei': self.w3.eth.get_balance(self.account.address),
                'pendingNonce': self.w3.eth.get_transaction_count(self.account.address, 'pending')}

    def prepare(self, intent_id, data, to=None):
        """Persist exact signed bytes before any network broadcast."""
        self.check_chain()
        if not isinstance(intent_id, str) or not 1 <= len(intent_id) <= 128:
            raise ValueError('Invalid intent id')
        if not isinstance(data, str) or not data.startswith('0x'):
            raise ValueError('Transaction data must be hex')
        raw_data = bytes.fromhex(data[2:])
        if len(raw_data) > 49152:
            raise ValueError('Transaction data too large')
        target = Web3.to_checksum_address(to) if to else None
        fingerprint = canonical({'chain': self.chain_id, 'to': target, 'data': raw_data.hex(), 'value': 0})
        with self.locked() as db:
            existing = db.execute('SELECT fingerprint,hash,tx FROM intents WHERE id=?', (intent_id,)).fetchone()
            if existing:
                if existing[0] != fingerprint:
                    raise ValueError('Intent id already has different transaction contents')
                return {'id': intent_id, 'hash': existing[1], 'transaction': json.loads(existing[2])}
            last = db.execute('SELECT MAX(nonce) FROM intents').fetchone()[0]
            pending = self.w3.eth.get_transaction_count(self.account.address, 'pending')
            nonce = max(pending, 0 if last is None else last + 1)
            block = self.w3.eth.get_block('latest')
            priority = min(self.w3.eth.max_priority_fee, 2_000_000_000)
            max_fee = 2 * block['baseFeePerGas'] + priority
            if max_fee > 30_000_000_000:
                raise ValueError('Fee exceeds the test-wallet ceiling')
            tx = {'chainId': self.chain_id, 'nonce': nonce, 'type': 2, 'value': 0,
                  'data': data, 'maxFeePerGas': max_fee, 'maxPriorityFeePerGas': priority}
            if target:
                tx['to'] = target
            estimate = self.w3.eth.estimate_gas(dict(tx, **{'from': self.account.address}))
            tx['gas'] = (estimate * 12 + 9) // 10
            if tx['gas'] > 1_000_000 or tx['gas'] * max_fee > 2_000_000_000_000_000:
                raise ValueError('Transaction exceeds test-wallet gas budget')
            if self.w3.eth.get_balance(self.account.address) < tx['gas'] * max_fee:
                raise ValueError('Insufficient test ETH')
            signed = self.account.sign_transaction(tx)
            txhash, raw = plain(signed.hash), plain(signed.raw_transaction)
            db.execute('INSERT INTO intents VALUES (?,?,?,?,?,?,NULL)',
                       (intent_id, fingerprint, nonce, canonical(tx), raw, txhash))
            db.commit()
            return {'id': intent_id, 'hash': txhash, 'transaction': tx}

    def broadcast(self, intent_id):
        """Retry sends identical bytes; a lost response never creates a new nonce."""
        self.check_chain()
        with self.locked() as db:
            row = db.execute('SELECT hash,raw FROM intents WHERE id=?', (intent_id,)).fetchone()
            if not row:
                raise ValueError('Unknown intent')
            txhash, raw = row
            try:
                self.w3.eth.get_transaction(txhash)
                return {'id': intent_id, 'hash': txhash}
            except TransactionNotFound:
                pass
            try:
                got = plain(self.w3.eth.send_raw_transaction(raw))
            except Exception:
                # Provider may have accepted the transaction before timing out.
                # Keep the journal unchanged so a caller can retry or reconcile.
                raise RuntimeError('Broadcast uncertain; retry this same intent id') from None
            if got.lower() != txhash.lower():
                raise RuntimeError('RPC returned a different transaction hash')
            return {'id': intent_id, 'hash': txhash}

    def receipt(self, intent_id):
        self.check_chain()
        with self.locked() as db:
            row = db.execute('SELECT hash FROM intents WHERE id=?', (intent_id,)).fetchone()
            if not row:
                raise ValueError('Unknown intent')
            try:
                receipt = plain(self.w3.eth.get_transaction_receipt(row[0]))
            except TransactionNotFound:
                return {'id': intent_id, 'receipt': None}
            canonical_hash = plain(self.w3.eth.get_block(receipt['blockNumber'])['hash'])
            if canonical_hash != receipt['blockHash']:
                return {'id': intent_id, 'receipt': None}
            receipt['confirmations'] = self.w3.eth.block_number - receipt['blockNumber'] + 1
            db.execute('UPDATE intents SET receipt=? WHERE id=?', (canonical(receipt), intent_id))
            db.commit()
            return {'id': intent_id, 'receipt': receipt}

    def events(self, stream, address, start, confirmations=2, ack=None):
        """Durable at-least-once batches, explicit reorg removals, explicit ACK.

        Consumers must persist the batch before acknowledging it. A repeated poll
        without its ACK returns identical data, including after a process crash.
        """
        self.check_chain()
        from evm import TOPIC
        address = Web3.to_checksum_address(address)
        if type(start) is not int or start < 0 or type(confirmations) is not int or confirmations < 0:
            raise ValueError('Invalid event range')
        if not isinstance(stream, str) or not 1 <= len(stream) <= 128:
            raise ValueError('Invalid stream id')
        config = canonical([address, start, confirmations, plain(TOPIC)])
        with self.locked() as db:
            old = db.execute('SELECT config,cursor FROM streams WHERE id=?', (stream,)).fetchone()
            if old and old[0] != config:
                raise ValueError('Stream id already has different settings')
            pending = db.execute('SELECT payload FROM deliveries WHERE stream=?', (stream,)).fetchone()
            if pending:
                batch = json.loads(pending[0])
                if ack != batch['batch']:
                    return batch
                db.execute('DELETE FROM deliveries WHERE stream=?', (stream,))
            elif ack:
                raise ValueError('No pending batch to acknowledge')
            if not old:
                db.execute('INSERT INTO streams VALUES (?,?,?)', (stream, config, start - 1))
            cursor = old[1] if old else start - 1
            ancestor = cursor
            head = self.w3.eth.block_number
            while ancestor >= start:
                stored = db.execute('SELECT hash FROM blocks WHERE stream=? AND number=?',
                                    (stream, ancestor)).fetchone()
                if stored and ancestor <= head and plain(self.w3.eth.get_block(ancestor)['hash']) == stored[0]:
                    break
                ancestor -= 1
            removed = [json.loads(x[0]) for x in db.execute(
                'SELECT data FROM events WHERE stream=? AND block>? ORDER BY block,key', (stream, ancestor))]
            db.execute('DELETE FROM events WHERE stream=? AND block>?', (stream, ancestor))
            db.execute('DELETE FROM blocks WHERE stream=? AND number>?', (stream, ancestor))
            end = min(head - confirmations, ancestor + 128)
            added = []
            if end > ancestor:
                headers = {n: self.w3.eth.get_block(n) for n in range(ancestor + 1, end + 1)}
                previous = self.w3.eth.get_block(ancestor)['hash'] if ancestor >= 0 else None
                if ancestor >= start:
                    anchor = db.execute('SELECT hash FROM blocks WHERE stream=? AND number=?',
                                        (stream, ancestor)).fetchone()[0]
                    if plain(previous) != anchor:
                        raise RuntimeError('Event cursor changed during scan; retry')
                for n, header in headers.items():
                    if previous is not None and header['parentHash'] != previous:
                        raise RuntimeError('Chain changed during event scan; retry')
                    previous = header['hash']
                logs = self.w3.eth.get_logs({'address': address, 'topics': [plain(TOPIC)],
                                            'fromBlock': ancestor + 1, 'toBlock': end})
                for log in logs:
                    n = log['blockNumber']
                    if n not in headers or headers[n]['hash'] != log['blockHash']:
                        raise RuntimeError('Inconsistent event block hash; retry')
                    value = plain(log)
                    key = canonical([value['blockHash'], value['transactionHash'], value['logIndex']])
                    db.execute('INSERT INTO events VALUES (?,?,?,?)', (stream, n, key, canonical(value)))
                    added.append(value)
                if self.w3.eth.get_block(end)['hash'] != headers[end]['hash']:
                    raise RuntimeError('Chain changed during event scan; retry')
                db.executemany('INSERT INTO blocks VALUES (?,?,?)',
                               [(stream, n, plain(h['hash'])) for n, h in headers.items()])
                ancestor = end
            db.execute('UPDATE streams SET cursor=? WHERE id=?', (ancestor, stream))
            payload = {'stream': stream, 'cursor': ancestor, 'added': added, 'removed': removed}
            payload['batch'] = hashlib.sha256(canonical(payload).encode()).hexdigest()
            db.execute('INSERT INTO deliveries VALUES (?,?)', (stream, canonical(payload)))
            db.commit()
            return payload

    def dispatch(self, request):
        operation = request['op']
        if operation == 'status':
            return self.status()
        if operation == 'prepare':
            return self.prepare(request['id'], request['data'], request.get('to'))
        if operation == 'broadcast':
            return self.broadcast(request['id'])
        if operation == 'receipt':
            return self.receipt(request['id'])
        if operation == 'events':
            return self.events(request['stream'], request['address'], request['start'],
                               request.get('confirmations', 2), request.get('ack'))
        if operation == 'call':
            self.check_chain()
            return {'data': plain(self.w3.eth.call({'to': Web3.to_checksum_address(request['to']),
                                                   'data': request['data']}))}
        raise ValueError('Unknown driver operation')
