"""Host process/file launcher. All artifact content is produced by PLAN."""
import argparse
import json
import secrets
import os
import sys
from pathlib import Path
from plan import ROOT, compile_contract
DEFAULT_HOME = Path.home() / ".local/share/shrine/ethereum-sepolia"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['build', 'create-wallet', 'serve-signer', 'wallet'])
    parser.add_argument('--module', default='contracts/checked')
    parser.add_argument('--artifact', default=str(ROOT / '.check/ethereum/checked-plan.json'))
    parser.add_argument('--home', type=type(DEFAULT_HOME), default=DEFAULT_HOME)
    parser.add_argument('--port', type=int, default=18545)
    parser.add_argument('--world', type=Path, help='Private directory for the saved Shrine world')
    args = parser.parse_args()
    if args.command == 'build':
        report = compile_contract(args.module)
        path = Path(args.artifact)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report['artifact'], indent=2) + '\n')
        print(json.dumps({'artifact': str(path)}))
    elif args.command == 'create-wallet':
        from host import create_wallet
        print(json.dumps({'address': create_wallet(args.home)}))
    elif args.command == 'serve-signer':
        from host import Signer, unlock, private_file, server
        path = args.home / 'signer-token'
        if not path.exists():
            private_file(path, secrets.token_urlsafe(32))
        print(json.dumps({'listening': f'127.0.0.1:{args.port}', 'tokenFile': str(path)}), flush=True)
        server(Signer(unlock(args.home)), path.read_text(), args.port).serve_forever()
    else:
        from world import World
        address = json.loads((args.home / 'keystore.json').read_text())['address']
        if not address.startswith('0x'):
            address = '0x' + address
        rpc = os.environ.get('SEPOLIA_RPC_URL', 'https://ethereum-sepolia-rpc.publicnode.com')
        token = (args.home / 'signer-token').read_text()
        directory = args.world or args.home / 'shrine-wallet'
        with World(directory, address, rpc, args.port, token) as wallet:
            print(json.dumps({'ready': True, 'world': str(directory)}), flush=True)
            for line in sys.stdin:
                if line.strip():
                    print(json.dumps(wallet.request(json.loads(line))), flush=True)


if __name__ == '__main__':
    main()
