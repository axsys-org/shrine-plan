import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import sys
import time
from web3 import Web3
from evm import wrap, calldata, TOPIC
from plan import ROOT, compile_contract
from wallet import Wallet, DEFAULT_HOME, DEFAULT_RPC, create_wallet, unlock, plain, private_file


def build(path, module='contracts/checked'):
    report = compile_contract(module, [[6, 7, 7], [1, 2, 0], [2**255, 2, 1]])
    artifact = wrap(report)
    artifact['module'] = module
    artifact['sourceSha256'] = hashlib.sha256((ROOT / 'src/foil' / (module + '.foil')).read_bytes()).hexdigest()
    files = ['flake.lock', 'src/foil/contract.foil', 'src/reaver/restricted-plan.rvr',
             'src/reaver/contract-lower.rvr', 'src/reaver/contract-evm.rvr',
             'src/reaver/contract-source.rvr', 'src/reaver/contract-build.rvr', 'ethereum/evm.py']
    artifact['compilerSources'] = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in files}
    artifact['reference'] = report['reference']
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(artifact, indent=2) + '\n')
    return artifact


def wait(wallet, intent_id, seconds=180):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        result = wallet.receipt(intent_id)
        if result['receipt'] is not None:
            if result['receipt']['status'] != 1:
                raise RuntimeError(f'Transaction reverted: {result["receipt"]["transactionHash"]}')
            return result['receipt']
        time.sleep(3)
    raise RuntimeError('Receipt pending; retry with the same intent id')


def deploy(wallet, artifact, output):
    """Idempotent deployment plus event exercise; reusable after any interruption."""
    # Bind the intent to exact init code, not just the runtime hash.
    identity = Web3.keccak(hexstr=artifact['bytecode']).hex()
    deploy_id = 'deploy-' + identity
    wallet.prepare(deploy_id, artifact['bytecode'])
    wallet.broadcast(deploy_id)
    receipt = wait(wallet, deploy_id)
    address = receipt['contractAddress']
    code = plain(wallet.w3.eth.get_code(address))
    if code != artifact['runtime']:
        raise RuntimeError('Deployed runtime differs from the compiler artifact')
    calls = []
    for args, reference in artifact['reference']:
        returned = wallet.w3.eth.call({'to': address, 'data': calldata('evaluate', args)})
        got = [int.from_bytes(returned[:32], 'big'), int.from_bytes(returned[32:], 'big')]
        if len(returned) != 64 or got != reference:
            raise RuntimeError('Sepolia result differs from PLAN')
        calls.append({'args': args, 'result': got})
    record_id = 'record-' + identity
    wallet.prepare(record_id, '0x' + calldata('record', [6, 7, 7]).hex(), address)
    wallet.broadcast(record_id)
    event_receipt = wait(wallet, record_id)
    batch = wallet.events('result-' + identity, address, receipt['blockNumber'], confirmations=0)
    # Stream batches are bounded; catch up if a previous deployment is old.
    for _ in range(1000):
        if any(x['transactionHash'] == event_receipt['transactionHash'] for x in batch['added']):
            break
        batch = wallet.events('result-' + identity, address, receipt['blockNumber'],
                              confirmations=0, ack=batch['batch'])
    else:
        raise RuntimeError('Event not yet observed; rerun deployment verification')
    matching = [x for x in batch['added'] if x['transactionHash'] == event_receipt['transactionHash']]
    if len(matching) != 1 or matching[0]['topics'] != [plain(TOPIC)]:
        raise RuntimeError('Unexpected result event')
    if matching[0]['data'] != '0x' + (0).to_bytes(32, 'big').hex() + (7).to_bytes(32, 'big').hex():
        raise RuntimeError('Incorrect event payload')
    evidence = {'chainId': wallet.chain_id, 'wallet': wallet.account.address, 'contract': address,
                'deployment': receipt, 'recordTransaction': event_receipt,
                'runtimeKeccak': artifact['runtimeKeccak'], 'calls': calls, 'eventBatch': batch}
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(json.dumps(evidence, indent=2) + '\n')
    return {'contract': address, 'deploymentHash': receipt['transactionHash'],
            'recordHash': event_receipt['transactionHash'], 'evidence': str(output)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['create-wallet', 'build', 'status', 'serve', 'deploy', 'request'])
    parser.add_argument('--home', type=Path, default=DEFAULT_HOME)
    parser.add_argument('--rpc', default=os.environ.get('SEPOLIA_RPC_URL', DEFAULT_RPC))
    parser.add_argument('--artifact', type=Path, default=ROOT / '.check/ethereum/checked.json')
    parser.add_argument('--evidence', type=Path, default=ROOT / '.check/ethereum/sepolia.json')
    parser.add_argument('--module', default='contracts/checked')
    parser.add_argument('--port', type=int, default=18545)
    args = parser.parse_args()
    if args.command == 'create-wallet':
        result = {'address': create_wallet(args.home)}
    elif args.command == 'build':
        artifact = build(args.artifact, args.module)
        result = {'artifact': str(args.artifact), 'runtimeKeccak': artifact['runtimeKeccak']}
    else:
        wallet = Wallet(Web3(Web3.HTTPProvider(args.rpc, request_kwargs={'timeout': 20})),
                        unlock(args.home), args.home)
        if args.command == 'status':
            result = wallet.status()
        elif args.command == 'deploy':
            result = deploy(wallet, json.loads(args.artifact.read_text()), args.evidence)
        elif args.command == 'request':
            result = wallet.dispatch(json.load(sys.stdin))
        else:
            from driver import server
            path = args.home / 'driver-token'
            if not path.exists():
                private_file(path, secrets.token_urlsafe(32))
            print(json.dumps({'listening': f'127.0.0.1:{args.port}', 'tokenFile': str(path)}), flush=True)
            server(wallet, path.read_text(), args.port).serve_forever()
            return
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
