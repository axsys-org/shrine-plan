# Ethereum contracts and Shrine wallet

The deployed contract source is [checked.foil](../src/foil/contracts/checked.foil).
It uses the [contract DSL](../src/foil/contract.foil), lowers to restricted
executable PLAN, and compiles to EVM. Its address is
[0xECc70FEBFbd8D81dD8840DE466B455138a13f061 on Sepolia](https://sepolia.etherscan.io/address/0xECc70FEBFbd8D81dD8840DE466B455138a13f061).
The [artifact](artifacts/checked.json) and [deployment record](deployments/checked-sepolia.json)
remain the evidence of that deployment. The new PLAN assembler reproduces its
ABI, runtime, deployment bytecode, and runtime hash exactly.

## Build and test

```sh
uv venv .venv-ethereum --python 3.12
uv pip install --python .venv-ethereum/bin/python -r ethereum/requirements.lock
nix develop .#eden
x/check contract-tests restricted-plan-tests foil:tests/ethereum_keccak foil:tests/ethereum_wallet foil:tests/ethereum_wallet_foot
x/check-ethereum -q
x/ethereum build
```

The build writes `.check/ethereum/checked-plan.json`. Set `WISP` instead of
entering the Nix shell when using the checkout's pinned runtime directly.
`ETHEREUM_PYTHON` selects another Python interpreter. `build --module NAME`
selects a Foil module exposing `program`. Compiler execution and artifact
serialization happen in PLAN; Python starts the process and writes its output.

## Run the namespace wallet

```sh
# Existing test-wallet files can be reused. This prints only the address.
x/ethereum create-wallet
# Keep the signing capability running in one terminal.
x/ethereum serve-signer
# Start or resume the Shrine wallet in another terminal.
x/ethereum wallet
```

The wallet stores its records under `<owner>/app/ethereum`. Intent and stream
children are ordinary namespace records. Embeddings use
`ethereum_wallet_app/access` to return rejected commands as acknowledgments. Its supervisor saves namespace changes
before acknowledging them. Signed transaction bytes enter the saved namespace
before a later cycle broadcasts them. Restarting `wallet` resumes that namespace.

The default private directory is `~/.local/share/shrine/ethereum-sepolia`.
`--home` selects another key directory; `--world` selects another saved-world
directory. The signing process uses a private `signer-token`. Set
`SEPOLIA_RPC_URL` to an Infura or other Ethereum RPC URL. The launcher supplies
that URL and the signer token over a pipe at each start. Neither credential is
part of the saved namespace. Historical `wallet.sqlite3` and `driver-token`
files are unused; existing transaction history is not imported automatically.

The wallet console accepts one JSON object per line. Responses contain `ok` and
`result` or `error`. The current slice advances network work on explicit `cycle`
commands; an embedding can attach the native polling foot instead.

```json
{"op":"status"}
{"op":"prepare","id":"deploy-example","to":"0x","data":"0x...initcode..."}
{"op":"cycle"}
{"op":"subscribe","id":"results","address":"0x...contract...","start":"0x...block...","confirmations":"0x2"}
{"op":"ack","id":"results","sequence":"0x1"}
```

Replace example hex strings with actual artifact bytes, contract addresses, and
block numbers. `prepare` accepts deployment bytes when `to` is `0x`, or call data
when `to` is a 20-byte address. Reuse an intent id when retrying the same request.
Each cycle advances each intent by at most one phase: quote/reserve, sign,
broadcast, then receipt observation. Phases 0–4 appear in status. Phase 4 means
a canonical receipt was observed; inspect its `status` for execution success.
It does not mean finality. A rejected or unavailable observation fails the cycle and leaves that
intent unchanged for retry. Changes already committed for earlier intents remain.

Streams poll the example contract's `Result(uint256,uint256)` event. Start at a
block greater than zero. Each scan covers at most 128 blocks. Unacknowledged
batches remain visible across scans and restarts; reorganizations append removal
batches. Apply and persist each batch before acknowledging its sequence. An ACK
is cumulative within its stream. The standalone console requires a new `cycle`
to observe later blocks.

## Code ownership

| Responsibility | Implementation |
| --- | --- |
| DSL, restricted PLAN, EVM lowering | `src/foil/contract.foil`, `src/reaver/contract-*.rvr` |
| Assembly, ABI, selectors, constructor, artifact | `src/reaver/contract-assemble.rvr` |
| Keccak, RLP, EIP-1559 transaction encoding | `src/foil/ethereum_{bytes,keccak,transaction}.foil` |
| Wallet policy, nonce reservation, event batches | `src/foil/ethereum_wallet.foil` |
| Namespace behavior and saved-world entry | `src/foil/ethereum_wallet_{app,world,console}.foil` |
| RPC and signer I/O orchestration | `src/foil/ethereum_{rpc,wallet_foot,driver}.foil` |
| Private-key capability | `ethereum/host.py` |
| Process/file/pipe launcher | `ethereum/plan.py`, `ethereum/world.py`, `ethereum/cli.py` |

Python host operations are limited to:

1. Secure random key, password, and bearer-token creation; owner-only keystore
   files; encrypted-keystore unlock; public identity; secp256k1 digest signing.
2. The authenticated loopback transport for that signing capability.
3. Starting the native runtime, copying its initial image, forwarding console
   messages and startup capabilities, and writing compiler output to disk.

These operations require host capabilities, not Python specifically. The signer
uses `eth-account` for keystore compatibility and `eth-keys` for signing; replacing
it with a native or hardware-backed capability does not change wallet policy.
`host-requirements.lock` contains only this adapter's dependency closure. The
larger `requirements.lock` also installs independent test oracles: Web3,
EthereumTester/PyEVM, Ethereum cryptography/encoding libraries, and pytest.
The former Python assembler exists only as `tests/reference_evm.py`.

This remains a Sepolia development wallet: zero value, empty access lists,
fixed fee/gas limits, one configured signer, and one local authority. The event
header history grows with scanning. Fee replacement, nonce-gap recovery,
multiple writers, signature recovery inside PLAN, generalized event filters,
and production key isolation remain future work. Privacy and settlement
choices remain deferred. See the [namespace migration record](../note/arch/ethereum-namespace-wallet.md).
