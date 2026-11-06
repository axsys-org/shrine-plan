# Ethereum application foundations

Status: common foundation accepted; settlement protocol undecided.
Date: 2026-11-06.

## Application boundary

Paramutuel is an ordinary Shrine namespace application. Its rules module is the
deterministic part of that application, not another operating system. Shrine
provides records, persistence, drivers, presentation, and application execution.
The future rollup commits a defined application state projection and a fixed
program version, rather than the entire local world or its UI and driver state.

The rules module takes explicit inputs and returns values. A later namespace
adapter admits signed commands and applies the resulting writes atomically.
Network reads, clocks, key custody, and transaction broadcasts remain driver
operations. Ethereum observations become consensus inputs only through a defined
authentication and ordering rule.

## Compiler boundary

The intended pipeline is Foil contract DSL -> executable restricted PLAN -> EVM.
PLAN is an intermediate program, not merely the platform running the compiler or
a container for an unrelated contract AST. The restriction checker must reject
unsupported dependencies and effects before bytecode emission. Types, layouts,
evaluation order, failure behavior, and resource bounds require specifications.

The modules introduced by this first slice are ordinary Foil reference code. They
do not establish the contract subset, provide an EVM backend, or prove compiler
equivalence. Their checked arithmetic and economic fixtures supply requirements
for those later stages. In particular, Foil's unbounded naturals must not erase
Solidity's checked uint256 intermediate multiplication failures.

## Privacy constraint

The user accepts either restricted disclosure during an adversarial challenge,
costly challenges, or both. A free mechanism that forces public disclosure is not
an accepted default. The disclosure audience, challenge cost, and enforcement
mechanism remain open decisions.

Private evidence exchanged between a bookie and challenger does not by itself
give Ethereum a way to adjudicate their disagreement. Publicly verifiable private
adjudication needs a proof mechanism, or an explicitly trusted adjudicator. If a
challenger receives plaintext, cryptography cannot prevent that challenger from
republishing it; distinguish protocol disclosure from recipient confidentiality.

A refundable bond is not necessarily an economic cost. Any priced-disclosure
design must specify nonrefundable charges, bond forfeiture, reimbursement for
valid challenges, and whether the attacker's benefit can exceed the cost.
Cost deters some attacks; it does not guarantee secrecy against a willing payer.

Proof-on-challenge remains a candidate. It must handle every batch being
challenged, protect the dispute transcript, and preserve access to private state
and withdrawal witnesses. Proofs establish valid execution, not data availability
or the truth of a resolver's real-world answer. No settlement mechanism is chosen
by this foundation work.

## Reference application

The reference is autarkenterprises/paramutuel at
`d4e2998da8fc11224f79a12a62bf84b99ade346c`, specifically
`src/ParamutuelWagerV3.sol`. Its five enumerated policies are SINGLE_WINNER,
ANY_OF, EXACT_SET, AT_LEAST_K, and WEIGHTED_OVERLAP. Freeform answers use exact
bytes and `keccak256(0x03 || answer)`. The bookie is an operator/sequencer; this
application pools stakes instead of guaranteeing fixed-odds liabilities.

Preserve fee charging on resolution, retraction, and expiry; per-ticket flooring
before claim summation; exact arithmetic failures; separate resolver and closer
roles; and rejection of resolution with no winning stake. Fee-recipient splitting,
freeform hashing, custody, authorizations, lifecycle state transitions, and
one-shot claims require further slices. The configured deployment is Base
Sepolia; the new settlement target is Ethereum.

## First implementation slice

Add reusable checked uint256 arithmetic and pure Paramutuel payout helpers. The
word boundary rejects out-of-range operands rather than silently truncating
them. Addition and multiplication reject overflow; subtraction rejects
underflow; division rejects zero. Multiply-then-divide checks the product before
division, matching the source contract even when the mathematical quotient fits.

Policy helpers compute a ticket's payout weight. Their inputs are already
admitted masks and policy parameters: they do not replace wager construction or
ticket admission. Claim inputs contain one line per distinct user ticket mask,
after repeated stakes on the same mask have been aggregated. Flooring each
individual deposit would change the source contract's economics.

Payout helpers return typed results and perform no I/O. Tests cover arithmetic
limits, each policy, checked intermediate overflow, fees on refund amounts, and
per-ticket rounding. A raw zero result remains a mathematical result; the future
state reducer must enforce each entry point's NothingToClaim behavior.

These helpers do not authenticate the pool denominator, enforce conservation
across accounts, validate every policy configuration, or authorize claims. They
are not a deployable wallet, complete application, or settlement contract.

## Next records and acceptance gates

1. Specify the restricted PLAN subset and test it against reference execution.
2. Specify canonical application state and signed command encoding; port state
   transitions and check them against Paramutuel's existing Solidity tests.
3. Specify the Ethereum driver and signer protocols; test crash recovery around
   nonce reservation, signing, broadcast, and receipt recording.
4. Emit EVM bytecode and compare behavior with the same PLAN program.
5. Measure disclosure and private-proof dispute prototypes on identical batches.
6. Choose settlement, availability, exit, and upgrade rules from that evidence.

Existing saved-world code is a persistence foundation. It does not establish
crash-safe external effects. A rollup program must stay pinned across restarts,
even though ordinary Shrine mounts can reload from the current checkout.

## Validation record

The tests were added first and failed because both implementation modules were
absent. After implementation, 42 checks passed through the repository's Foil test
runner: 14 word checks, 12 policy checks, and 16 accounting checks. The standard
slot-catalog checks also passed. The final native run completed in 5.8 seconds
using the runtime pinned by this checkout's Nix environment.

Reproduce from the repository root:

```sh
nix develop .#eden --command sh x/check foil:tests/ethereum_word foil:tests/paramutuel_rules
```

The implementation required an explicit result-type annotation inside the
payout loop; the compiler otherwise could not infer its relative result
constructors. No runtime or compiler behavior was changed.

The slice establishes executable reference helpers, not complete protocol
coverage. No Solidity differential run or cryptographic security claim follows
from these source-derived fixtures. The next implementation record should define
the restricted PLAN subset before adding an EVM backend or driver effects.
