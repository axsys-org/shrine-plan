# Ethereum development slice

Build a Foil contract through restricted PLAN, execute the EVM differential tests,
and deploy the test contract with a dedicated Sepolia wallet. The
[architecture record](../note/arch/foil-sepolia-v0.md) defines the limits.

The example is deployed on
[Sepolia](https://sepolia.etherscan.io/address/0xECc70FEBFbd8D81dD8840DE466B455138a13f061).
Its [build artifact](artifacts/checked.json) and
[deployment evidence](deployments/checked-sepolia.json) are checked in.

## Setup

From the repository root:

```sh
uv venv .venv-ethereum --python 3.12
uv pip install --python .venv-ethereum/bin/python -r ethereum/requirements.lock
nix develop .#eden
```

The commands below run inside that Nix shell. Alternatively set `WISP` to the
runtime pinned by this checkout. `ETHEREUM_PYTHON` selects a different Python
installation with the locked dependencies.

## Test and build

```sh
x/check contract-tests restricted-plan-tests foil:tests/ethereum_word foil:tests/paramutuel_rules
x/check-ethereum -q
x/ethereum build
```

The build writes `.check/ethereum/checked.json`. The source is
`src/foil/contracts/checked.foil`. It takes `(a,b,denominator)` and returns
`(status,value)`. For `(6,7,7)` it returns `(0,7)`. For a zero denominator it
returns `(0,0)`. Checked multiplication and addition retain their overflow faults.

## Deploy to Sepolia

```sh
x/ethereum create-wallet
x/ethereum status
# Fund the printed address with Sepolia test ETH.
x/ethereum deploy
```

Wallet files live in `~/.local/share/shrine/ethereum-sepolia`, outside the repo.
The generated password is stored beside the encrypted keystore for local
unattended signing. `--home` selects another private directory. Use
`SEPOLIA_RPC_URL` for an Infura or other authenticated endpoint; avoid putting
credential-bearing URLs in shell arguments or checked-in files.

Deployment verifies the returned runtime bytes, compares three on-chain calls
with PLAN results, sends a `record(6,7,7)` transaction, and consumes its Result
log through the durable event listener. Evidence is written to
`.check/ethereum/sepolia.json`. Rerunning uses the saved intent ids and transaction
hashes. It does not deploy a second copy. The verification run observes included
blocks with zero event delay; its evidence does not assert finality.

The `deploy` command exercises the bundled three-argument example. `build
--module` can compile another local module exposing `program`; other arities
require callers to supply their own ABI arguments through the driver protocol.

## Use the I/O driver

```sh
x/ethereum serve
```

The service binds `127.0.0.1:18545`. It writes a private `driver-token` in the
wallet directory and prints the file path. A Shrine foot uses
`ethereum_driver/request port token message`; deterministic contract code cannot
call this interface. The first adapter is a transport API, not a mounted wallet
application.

POST JSON to `/v0` with `Authorization: Bearer <token>`. Supported requests:

```json
{"op":"status"}
{"op":"prepare","id":"unique-intent","data":"0x...","to":"0x..."}
{"op":"broadcast","id":"unique-intent"}
{"op":"receipt","id":"unique-intent"}
{"op":"call","to":"0x...","data":"0x..."}
{"op":"events","stream":"results","address":"0x...","start":123,"confirmations":2}
{"op":"events","stream":"results","address":"0x...","start":123,"confirmations":2,"ack":"previous-batch-token"}
```

Omit `to` when preparing deployment init code. Persist an event batch before
sending its acknowledgment. Repeat an uncertain transaction using the same
intent id. Driver responses use `{"ok":true,"result":...}` or
`{"ok":false,"error":...}`. Error responses omit provider details that could
contain RPC credentials.
