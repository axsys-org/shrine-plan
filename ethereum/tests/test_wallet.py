"""Independent host/EVM oracles around the native Shrine application."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import pytest
import requests
from eth_account import Account
from web3 import Web3, EthereumTesterProvider
from host import Signer, server, create_wallet, unlock
from world import World
from plan import compile_contract, run
from reference_evm import calldata


def plain(value):
    if isinstance(value, bytes):
        return '0x' + value.hex()
    if isinstance(value, int) and not isinstance(value, bool):
        return hex(value)
    if hasattr(value, 'items'):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(v) for v in value]
    return value


@contextmanager
def running(http):
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    try:
        yield http.server_port
    finally:
        http.shutdown()
        http.server_close()
        thread.join()


class Chain:
    """Test-only JSON-RPC bridge to the independent PyEVM implementation."""
    def __init__(self):
        provider = EthereumTesterProvider()
        provider.api_endpoints = {**provider.api_endpoints, 'eth': {**provider.api_endpoints['eth'], 'chainId': lambda *_: 11155111}}
        provider.ethereum_tester.backend.chain.chain_id = 11155111
        self.w3 = Web3(provider)
        self.account = Account.from_key(self.w3.provider.ethereum_tester.backend.account_keys[0].to_bytes())
        self.lost = False
        self.lose_next = False
        self.calls = []

    def dispatch(self, method, params):
        self.calls.append(method)
        eth = self.w3.eth
        address = lambda text: Web3.to_checksum_address(text)
        block = lambda number: int(number, 16) if number.startswith('0x') else number
        if method == 'eth_chainId': return 11155111
        if method == 'eth_blockNumber': return eth.block_number
        if method == 'eth_getTransactionCount': return eth.get_transaction_count(address(params[0]), params[1])
        if method == 'eth_maxPriorityFeePerGas': return eth.max_priority_fee
        if method == 'eth_getBalance': return eth.get_balance(address(params[0]), params[1])
        if method == 'eth_estimateGas':
            tx = dict(params[0])
            for key in ('from', 'to'):
                if key in tx: tx[key] = address(tx[key])
            return eth.estimate_gas(tx)
        if method == 'eth_getBlockByNumber': return eth.get_block(block(params[0]))
        if method == 'eth_getTransactionByHash':
            try: return eth.get_transaction(params[0])
            except Exception: return None
        if method == 'eth_getTransactionReceipt':
            try: return eth.get_transaction_receipt(params[0])
            except Exception: return None
        if method == 'eth_sendRawTransaction':
            result = eth.send_raw_transaction(params[0])
            if self.lose_next:
                self.lose_next = False
                self.lost = True
                raise TimeoutError('Accepted transaction; response lost')
            return result
        if method == 'eth_getLogs':
            f = dict(params[0]); f['address'] = address(f['address'])
            for key in ('fromBlock', 'toBlock'): f[key] = block(f[key])
            return eth.get_logs(f)
        raise ValueError(method)

    def server(self):
        chain = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def do_POST(self):
                message = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                try:
                    result = {'result': plain(chain.dispatch(message['method'], message['params']))}
                except Exception:
                    result = {'error': {'code': -32000, 'message': 'test RPC failure'}}
                payload = json.dumps({'jsonrpc': '2.0', 'id': message['id'], **result}).encode()
                self.send_response(200); self.send_header('Content-Length', str(len(payload)))
                self.end_headers(); self.wfile.write(payload)
        return ThreadingHTTPServer(('127.0.0.1', 0), Handler)


def command(world, **value):
    reply = world.request(value)
    assert reply['ok'], reply
    return reply['result']


def test_native_wallet_save_retry_signing_receipts_and_reorg(tmp_path):
    chain = Chain()
    token = 'test-capability-not-a-production-secret'
    artifact = compile_contract()['artifact']
    with running(chain.server()) as rpc, running(server(Signer(chain.account), token, 0)) as port:
        settings = (tmp_path / 'world', chain.account.address, f'http://127.0.0.1:{rpc}', port, token)
        with World(*settings) as world:
            command(world, op='prepare', id='deploy', to='0x', data=artifact['bytecode'])
            quoted = command(world, op='cycle')
            assert quoted['intents'][0]['phase'] == 1
            signed = command(world, op='cycle')['intents'][0]
            assert signed['phase'] == 2
            assert Account.recover_transaction(signed['raw']) == chain.account.address
            assert Web3.keccak(hexstr=signed['raw']).hex() == signed['hash'][2:]
            assert chain.w3.eth.get_transaction_count(chain.account.address) == 0
        # A new native process resumes the saved namespace, including signed bytes.
        with World(*settings) as world:
            assert command(world, op='status')['intents'][0] == signed
            assert command(world, op='prepare', id='deploy', to='0x', data=artifact['bytecode'])['intents'][0] == signed
            assert not world.request({'op': 'prepare', 'id': 'deploy', 'to': '0x', 'data': '0x00'})['ok']
            chain.lose_next = True
            assert not world.request({'op': 'cycle'})['ok']
            assert command(world, op='status')['intents'][0]['phase'] == 2
            assert chain.lost
            assert command(world, op='cycle')['intents'][0]['phase'] == 3
            included = command(world, op='cycle')['intents'][0]
            assert included['phase'] == 4
            receipt = included['receipt']
            address = receipt['contractAddress']
            assert chain.w3.eth.get_transaction_count(chain.account.address) == 1
            assert '0x' + chain.w3.eth.get_code(Web3.to_checksum_address(address)).hex() == artifact['runtime']
            command(world, op='subscribe', id='results', address=address,
                    start=receipt['blockNumber'], confirmations='0x0')
            command(world, op='cycle')
            snapshot = chain.w3.provider.ethereum_tester.take_snapshot()
            chain.w3.eth.send_transaction({'from': chain.account.address, 'to': Web3.to_checksum_address(address),
                                           'data': calldata('record', [6, 7, 7])})
            events = command(world, op='cycle')['streams'][0]
            assert len(events['batches']) == 1
            assert len(events['batches'][0]['added']) == 1
            assert command(world, op='cycle')['streams'][0] == events
        with World(*settings) as world:
            assert command(world, op='status')['streams'][0] == events
            chain.w3.provider.ethereum_tester.revert_to_snapshot(snapshot)
            chain.w3.provider.ethereum_tester.mine_blocks(2)
            replaced = command(world, op='cycle')['streams'][0]
            assert len(replaced['batches']) == 2
            assert replaced['batches'][1]['removed'] == events['batches'][0]['added']
            assert replaced['batches'][1]['added'] == []
            acknowledged = command(world, op='ack', id='results', sequence='0x1')['streams'][0]
            assert len(acknowledged['batches']) == 1
            assert not world.request({'op': 'ack', 'id': 'results', 'sequence': '0x9'})['ok']
            assert not world.request({'op': 'subscribe', 'id': 'results', 'address': address,
                                     'start': receipt['blockNumber'], 'confirmations': '0x2'})['ok']
        assert chain.calls.count('eth_sendRawTransaction') == 1
        assert token not in (tmp_path / 'world/runtime.log').read_text()
        for file in (tmp_path / 'world/snap').rglob('*'):
            if file.is_file():
                assert token.encode() not in file.read_bytes(), file


def test_signer_auth_scope_and_native_transport():
    account = Account.from_key(b'\x01' * 32)
    signer = Signer(account)
    token = 'test-capability-for-local-integration-only'
    with running(server(signer, token, 0)) as port:
        url = f'http://127.0.0.1:{port}/v0'
        assert requests.post(url, json={'op': 'identity'}, timeout=5).status_code == 403
        headers = {'Authorization': 'Bearer ' + token}
        assert requests.post(url, json={'op': 'identity'}, headers={**headers, 'Origin': 'https://example.org'}, timeout=5).status_code == 403
        assert not requests.post(url, json={'op': 'prepare'}, headers=headers, timeout=5).json()['ok']
        body = int.from_bytes(b'{"op":"identity"}', 'little')
        result = run(f'''(#bind source (#module contract-source))
(#bind foil (#module foil-new-env))
(#bind build (#module contract-build))
(define sut (source:load "test_fixtures/ethereum_driver_probe"))
(define probe (foil:source-entry-val ["probe"] sut))
(print ["CONTRACT-OUTPUT" (build:numbers (probe {port} "{token}" {body}))])''')
        assert result[0] == 200
        decoded = json.loads(result[1].to_bytes((result[1].bit_length() + 7) // 8, 'little'))
        assert decoded['result']['address'] == account.address.lower()
        signed = signer.dispatch({'op': 'sign', 'digest': '0x' + '02' * 32})
        from eth_keys import keys
        sig = keys.Signature(vrs=tuple(int(signed[k], 16) for k in ('parity', 'r', 's')))
        assert sig.recover_public_key_from_msg_hash(b'\x02' * 32).to_checksum_address() == account.address
        for invalid in ({'op': 'sign', 'digest': '0x00'}, {'op': 'sign', 'digest': '0x' + '00'*32, 'nonce': 0}):
            with pytest.raises(ValueError): signer.dispatch(invalid)


def test_keystore_permissions_and_reopen(tmp_path):
    home = tmp_path / 'keys'
    address = create_wallet(home)
    assert create_wallet(home) == address == unlock(home).address
    assert (home / 'keystore.json').stat().st_mode & 0o077 == 0
    (home / 'password').chmod(0o644)
    with pytest.raises(ValueError, match='owner-only'): unlock(home)


def test_native_eip1559_encoding_against_eth_account():
    from eth_account.typed_transactions import TypedTransaction
    account = Account.from_key(b'\x01' * 32)
    vectors = [(n, data) for n in (0, 127, 128, 65536) for data in ('0x', '0x0100', '0x' + 'ab'*136)]
    calls, expected = [], []
    for nonce, data in vectors:
        tx = {'type': 2, 'chainId': 11155111, 'nonce': nonce, 'maxPriorityFeePerGas': 10**9,
              'maxFeePerGas': 3*10**9, 'gas': 100000, 'to': '0x' + '11'*20,
              'value': 0, 'data': data, 'accessList': []}
        signed = account.sign_transaction(tx)
        digest = TypedTransaction.from_dict(tx).hash()
        expected.append(['0x' + digest.hex(), '0x' + signed.raw_transaction.hex()])
        calls.append(f'(probe {nonce} {int.from_bytes(data.encode(), "little")} {signed.v} {signed.r} {signed.s})')
    output = run('''(#bind source (#module contract-source))
(#bind foil (#module foil-new-env))
(#bind build (#module contract-build))
(#bind json (#module wire-json))
(#bind std (#module std))
(#import std)
(#bind reef (#module reef))
(#import reef)
(define probe (foil:source-entry-val ["probe"] (source:load "test_fixtures/ethereum_transaction_probe")))
(print ["CONTRACT-OUTPUT" (json:jarr (map build:numbers [''' + ' '.join(calls) + ''']))])''')
    decoded = [[n.to_bytes((n.bit_length()+7)//8, 'little').decode() for n in pair] for pair in output]
    assert decoded == expected
