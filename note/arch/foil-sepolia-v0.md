# Foil contracts and Sepolia v0

Status: implemented, tested, and deployed to Sepolia on 2026-11-06.

## Scope

The first contract compiles from a typed embedded Foil language through executable
restricted PLAN to EVM. It evaluates checked arithmetic and emits the result of a
transaction. It has no storage, custody, settlement, oracle, or privacy policy.

`src/foil/contract.foil` defines the expression constructors. `contracts/checked`
uses three uint256 arguments to compute `(a * b + 7) / denominator`. A zero
denominator selects zero without evaluating the other branch. Overflow in the
product or sum returns a failure even when the final mathematical quotient fits.

This slice is an embedded language: Foil constructs typed expression values. It
does not compile arbitrary ordinary Foil functions to EVM. Additional syntax can
lower into the same constructors without changing the execution boundary.

## Compilation

The normal Foil publication pipeline compiles the source module. Its `program`
export supplies argument count and expression data to `contract-lower.rvr`.
Lowering constructs a pinned executable PLAN law using the closed restricted
library. The restricted PLAN checker admits that law before code generation.

`contract-evm.rvr` reads the admitted law's body and emits symbolic EVM
instructions. It does not consume the source expression tree. Static helper calls
substitute suspended arguments; only a demanded argument emits execution code.
Conditional branches jump around unselected expressions. Checked operations
propagate the first failure in PLAN evaluation order.

Inlining can duplicate a demanded helper argument. The backend rejects expansion
above 8,192 instruction tokens, independently of PLAN admission limits. The
assembler rejects runtime code above 24,576 bytes. These are compile-time limits;
behavioral comparisons assume enough EVM gas to finish execution.

`ethereum/evm.py` assembles the instructions and adds a fixed ABI envelope. It does
not implement the contract's arithmetic semantics. The artifact records source
hashes, init code, runtime code, ABI, runtime Keccak hash, and PLAN examples.
Local source compilation is trusted build-time execution; this compiler is not a
sandbox for hostile Foil modules or hostile serialized PLAN graphs.

## ABI and event envelope

Every contract has `evaluate(uint256,...)` and `record(uint256,...)` functions.
Both return `(uint256 status, uint256 value)`: status 0 carries a result; status 1
carries the restricted PLAN fault code. Arithmetic faults are returned data, not
EVM reverts. `record` additionally emits `Result(uint256,uint256)` with those two
words as unindexed data. `evaluate` emits no event.

The runtime rejects unknown selectors, incorrect calldata length, and nonzero
ETH value. The constructor also rejects ETH value. The envelope has no fallback,
external calls, storage writes, or self-destruction. Adding effects requires an
explicit profile extension; a result event does not imply a settled application.

Selectors, word encoding, and event topics follow the
[Ethereum contract ABI](https://docs.soliditylang.org/en/latest/abi-spec.html).
The backend uses the standard [EVM instruction set](https://ethereum.org/developers/docs/evm/opcodes/).

## Wallet and I/O boundary

The wallet is a host driver with a typed Foil transport module,
`ethereum_driver.foil`. A Shrine foot can call it through the native `Fetch`
operation. The host listens only on loopback and requires a bearer capability.
Requests with a browser Origin are refused. The driver is not exposed to public
network clients. The capability belongs in local driver configuration, outside
application records and contract programs.

The v0 driver supports `status`, `prepare`, `broadcast`, `receipt`, `call`, and
`events`. It uses standard
[Ethereum JSON-RPC](https://ethereum.org/developers/docs/apis/json-rpc/), so an
Infura endpoint can replace the default public Sepolia endpoint. All operations
check the configured chain identity. The public CLI fixes that identity to
Sepolia, 11155111. Tests inject a local Ethereum VM.

`prepare` builds and signs an EIP-1559 transaction locally. It records the exact
signed bytes and transaction hash in SQLite before allowing broadcast. Reusing
an intent id with identical contents returns the existing transaction; changing
its contents fails. A process lock serializes nonce allocation. A journal is
bound to one chain and one account. The account must be dedicated to this driver.

`broadcast` sends the saved bytes. If the provider accepts them but loses its
reply, a retry looks up the same hash and otherwise resends the same bytes. It
never allocates another nonce to recover an uncertain broadcast. Receipt reads
check the current block hash and report a confirmation count; inclusion does not
claim finality. Replacements, cancellation, and recovery from externally consumed
nonces remain future wallet work.

The test wallet only sends zero-value transactions. Each transaction is limited
to 1,000,000 gas, a maximum fee of 30 gwei per gas, and at most 0.002 ETH in
reserved gas cost. These limits reject a transaction before signing. The
implementation uses `eth-account` for secp256k1 signing and encrypted keystore
encoding; it does not implement cryptography.

The keystore and its generated automation password live outside the repository
with owner-only permissions. Keeping both on one machine is local file custody,
not a hardware wallet or a separate password security factor. Keys and signed
transaction journals never become deterministic PLAN inputs.

## Event delivery

`events` polls Result logs in batches of at most 128 blocks. A stream binds its
address, start block, topic, and confirmation delay. It stores block hashes and
log identities, checks ancestry during each scan, and reports removals when a
previously observed block leaves the chain. Its default delay is two blocks;
this is a latency setting, not finality.

Each batch has an acknowledgment token. The driver persists the batch before
returning it and repeats it until acknowledged. A Shrine consumer must commit
that batch to its world before acknowledging it. This gives at-least-once
delivery across driver restarts; the consumer must deduplicate by batch and log
identity. This slice tests the transport and durable host protocol. It does not
yet install a wallet namespace application or couple acknowledgment to a Shrine
world commit.

## Validation

The Python gate executes emitted bytecode in Py-EVM. It compares six binary
operations against PLAN over 49 boundary pairs and 30 seeded random pairs each:
474 comparisons. Further cases cover the Foil example, lazy helpers, invalid
conditions, first-failure ordering, expansion limits, malformed ABI calls, and
result events. The existing restricted PLAN and 42 Foil foundation checks remain
regression gates.

Wallet tests recover the signer from saved raw bytes, reopen the journal, retry
a transaction whose broadcast reply was lost, reject conflicting intent ids and
wrong chains, and replay acknowledged/unacknowledged event batches across a
simulated reorganization. A compiled Foil probe calls the authenticated driver
through the native Fetch operation.

The final gates passed 11 compiler/EVM tests and five wallet/transport tests.
The wallet gate includes a reorganization between cursor validation and header
loading: the scan fails without acknowledging its pending batch, then reports
the removed event on retry. The standard contract and restricted PLAN suites,
42 Foil foundation checks, and five slot-catalog checks also passed.

## Sepolia evidence

The deployed contract is
[`0xECc70FEBFbd8D81dD8840DE466B455138a13f061`](https://sepolia.etherscan.io/address/0xECc70FEBFbd8D81dD8840DE466B455138a13f061).
The deployment transaction is
[`0xd761cb4213f96ef21e829a053ae42f0cfe76ab6b950b66486ee87fb507ba78a0`](https://sepolia.etherscan.io/tx/0xd761cb4213f96ef21e829a053ae42f0cfe76ab6b950b66486ee87fb507ba78a0).
The event transaction is
[`0xad9d48262568a6118164eaa14a16acdb7ea7a3d750d2f15a240c9461a03a8f73`](https://sepolia.etherscan.io/tx/0xad9d48262568a6118164eaa14a16acdb7ea7a3d750d2f15a240c9461a03a8f73).

The 379-byte runtime matched the compiler artifact byte for byte. Three calls
returned `(0,7)`, `(0,0)`, and `(1,2)`, matching PLAN for normal arithmetic,
the zero-denominator branch, and multiplication overflow. The event listener
returned the Result log from `record(6,7,7)` with `(0,7)` as its data.

The build artifact is `ethereum/artifacts/checked.json`. Receipts, exact call
arguments, and the durable event batch are in
`ethereum/deployments/checked-sepolia.json`. These are observations through the
configured RPC provider, not independently verified execution proofs or a
finality claim.

The remaining risks are compiler coverage, host key custody, dependence on the
RPC provider's chain view, and application integration of event acknowledgments.
These tests establish a small testnet path, not production contract assurance.
Privacy and settlement remain deferred.
