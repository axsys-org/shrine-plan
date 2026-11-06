import json
import threading
import pytest
import requests
from eth_account import Account
from web3 import Web3, EthereumTesterProvider
from wallet import Wallet, plain
from driver import server
from plan import compile_contract, run
from evm import wrap, calldata


@pytest.fixture
def wallet(tmp_path):
    w3 = Web3(EthereumTesterProvider())
    key = w3.provider.ethereum_tester.backend.account_keys[0]
    return Wallet(w3, Account.from_key(key.to_bytes()), tmp_path, chain_id=w3.eth.chain_id)


@pytest.fixture(scope='module')
def artifact():
    return wrap(compile_contract())


def submit(wallet, identifier, data, to=None):
    prepared = wallet.prepare(identifier, data, to)
    wallet.broadcast(identifier)
    return prepared, wallet.receipt(identifier)['receipt']


def test_sign_recover_retry_restart_and_conflict(wallet, artifact):
    first = wallet.prepare('deploy', artifact['bytecode'])
    with wallet.locked() as db:
        raw = db.execute('SELECT raw FROM intents').fetchone()[0]
    assert Account.recover_transaction(raw) == wallet.account.address
    restarted = Wallet(wallet.w3, wallet.account, wallet.home, wallet.chain_id)
    assert restarted.prepare('deploy', artifact['bytecode']) == first
    restarted.broadcast('deploy')
    restarted.broadcast('deploy')
    receipt = restarted.receipt('deploy')['receipt']
    assert receipt['status'] == 1
    assert wallet.w3.eth.get_transaction_count(wallet.account.address) == 1
    assert plain(wallet.w3.eth.get_code(receipt['contractAddress'])) == artifact['runtime']
    with pytest.raises(ValueError, match='different'):
        wallet.prepare('deploy', '0x00')
    wrong = Wallet(wallet.w3, wallet.account, wallet.home / 'wrong', 11155111)
    with pytest.raises(ValueError, match='chain'):
        wrong.prepare('wrong', artifact['bytecode'])


def test_broadcast_lost_response(wallet, artifact, monkeypatch):
    prepared = wallet.prepare('uncertain', artifact['bytecode'])
    send = wallet.w3.eth.send_raw_transaction
    def lost(raw):
        send(raw)
        raise TimeoutError('response lost')
    with monkeypatch.context() as patch:
        patch.setattr(wallet.w3.eth, 'send_raw_transaction', lost)
        with pytest.raises(RuntimeError, match='uncertain'):
            wallet.broadcast('uncertain')
    assert wallet.broadcast('uncertain')['hash'] == prepared['hash']
    assert wallet.w3.eth.get_transaction_count(wallet.account.address) == 1


def test_event_ack_replay_and_reorganization(wallet, artifact):
    _, deployment = submit(wallet, 'deploy', artifact['bytecode'])
    address = deployment['contractAddress']
    tester = wallet.w3.provider.ethereum_tester
    snapshot = tester.take_snapshot()
    _, recorded = submit(wallet, 'record', '0x' + calldata('record', [6, 7, 7]).hex(), address)
    batch = wallet.events('stream', address, deployment['blockNumber'], 0)
    assert len(batch['added']) == 1
    assert batch['added'][0]['transactionHash'] == recorded['transactionHash']
    restarted = Wallet(wallet.w3, wallet.account, wallet.home, wallet.chain_id)
    assert restarted.events('stream', address, deployment['blockNumber'], 0) == batch
    tester.revert_to_snapshot(snapshot)
    tester.mine_blocks(2)
    next_batch = restarted.events('stream', address, deployment['blockNumber'], 0, batch['batch'])
    assert next_batch['removed'] == batch['added']
    assert next_batch['added'] == []
    assert restarted.events('stream', address, deployment['blockNumber'], 0) == next_batch
    with pytest.raises(ValueError, match='settings'):
        restarted.events('stream', address, deployment['blockNumber'], 2)


def test_driver_auth_and_native_foil_transport(wallet):
    token = 'test-capability-for-local-integration-only'
    http = server(wallet, token, 0)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    port = http.server_port
    try:
        url = f'http://127.0.0.1:{port}/v0'
        assert requests.post(url, json={'op': 'status'}, timeout=5).status_code == 403
        assert requests.post(url, json={'op': 'status'}, timeout=5,
            headers={'Authorization': 'Bearer ' + token, 'Origin': 'https://example.org'}).status_code == 403
        body = int.from_bytes(b'{"op":"status"}', 'little')
        result = run(f'''(#bind source (#module contract-source))
(#bind foil (#module foil-new-env))
(#bind build (#module contract-build))
(#bind std (#module std))
(#import std)
(define sut (source:load "test_fixtures/ethereum_driver_probe"))
(define probe (foil:source-entry-val ["probe"] sut))
(print ["CONTRACT-OUTPUT" (build:numbers (probe {port} "{token}" {body}))])''')
        assert result[0] == 200
        data = result[1].to_bytes((result[1].bit_length() + 7) // 8, 'little')
        decoded = json.loads(data)
        assert decoded['ok']
        assert decoded['result']['address'] == wallet.account.address
    finally:
        http.shutdown()
        http.server_close()
        thread.join()


def test_reorg_during_scan_preserves_unacknowledged_batch(wallet, artifact, monkeypatch):
    _, deployment = submit(wallet, 'deploy', artifact['bytecode'])
    address = deployment['contractAddress']
    tester = wallet.w3.provider.ethereum_tester
    snapshot = tester.take_snapshot()
    submit(wallet, 'record', '0x' + calldata('record', [6, 7, 7]).hex(), address)
    batch = wallet.events('race', address, deployment['blockNumber'], 0)
    tester.mine_blocks(1)
    get_block = wallet.w3.eth.get_block
    changed = False
    def change_chain(number, *args, **kwargs):
        nonlocal changed
        if number == batch['cursor'] + 1 and not changed:
            changed = True
            tester.revert_to_snapshot(snapshot)
            tester.mine_blocks(3)
        return get_block(number, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(wallet.w3.eth, 'get_block', change_chain)
        with pytest.raises(RuntimeError, match='cursor changed'):
            wallet.events('race', address, deployment['blockNumber'], 0, batch['batch'])
    # Failed scan rolls back the ACK as well as its cursor and event changes.
    assert wallet.events('race', address, deployment['blockNumber'], 0) == batch
    recovered = wallet.events('race', address, deployment['blockNumber'], 0, batch['batch'])
    assert recovered['removed'] == batch['added']
