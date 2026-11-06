# Restricted PLAN v0

Status: pure word profile implemented and acceptance tests passing.

## Purpose

Restricted PLAN v0 defines an executable, pure, first-order word profile for the
future Foil-to-PLAN-to-EVM pipeline. Its artifact contains actual PLAN laws and
pins. A checker reads those laws' bodies; it does not accept a separate language
AST in place of the executable program. Privacy and settlement remain deferred.

This profile establishes a small admission boundary. Contract storage, external
calls, events, ABI decoding, loops, aggregates, and the EVM backend require later
profiles. Ordinary Foil output may need specialization and normalization before
it fits this profile. Acceptance is not a claim that every Foil function compiles.

## Artifact and types

An artifact is the row `["restricted-plan/0", entry, definitions]`. Each
definition is `[function, argument_types, return_type]`. Functions are bare PLAN
laws or one pin around a law. A definition's declared arity must equal its actual
firing arity. There are two types: `WORD = 1` and `RESULT = 2`.

WORD is a natural less than 2^256. RESULT is either `[0, word]` (success) or
`[1, code]` (failure). Failure codes are 1 for range, 2 for overflow, 3 for
underflow, and 4 for division by zero. These rows are an internal reference
convention, not an Ethereum ABI, commitment format, or settlement wire format.

The entry must appear in definitions, take WORD arguments, and return RESULT.
Helpers may take or return either type. Every definition is checked, including
unused definitions. Duplicate definitions of the same underlying law are
rejected, including pinned and unpinned duplicates. Declared types are checked
against the actual body and each call; they are not trusted certificates.

## Admitted law bodies

The checker follows the current runtime's PLAN body encoding:

- Naturals 1 through the law's arity refer to arguments.
- Reference 0 is self and is rejected in this profile.
- A natural above the arity is a literal, subject to the WORD bound.
- `(0 value)` quotes a literal WORD, including constants that would otherwise
  collide with references.
- `(0 function argument)` applies a function. Nested applications form a call.

A call must have a statically identifiable law or trusted library function as
its head and supply exactly its declared argument count. Helper laws must be
listed in the artifact. Calls through arguments, partial applications,
overapplications, raw primitive calls, reflection, self-reference, and recursive
dependencies are rejected. Lets and other application-shaped literals are also
rejected. A frontend must normalize them before admission.

Only WORD literals are admitted as executable expression values. A quoted pin,
law, arbitrary result row, or closure cannot introduce an unchecked function or
forge a RESULT. Function constants are admitted only as static call heads.

Both branches of a conditional must typecheck and satisfy admission. Selecting a
safe branch at runtime cannot hide an I/O primitive in the other branch.

## Trusted pure library

Library membership compares the complete function value against the module's
canonical functions. A matching name, arity, or declared type is insufficient.
Artifacts cannot extend the library. Its functions use the pinned runtime's pure
arithmetic operations; they perform no I/O. These definitions are the v0 trust
boundary, not an axiom-level proof of all runtime implementations.

| Function | Signature | Meaning |
|---|---|---|
| lift | WORD -> RESULT | Construct a successful result |
| plus | RESULT, RESULT -> RESULT | Checked addition |
| minus | RESULT, RESULT -> RESULT | Checked subtraction |
| times | RESULT, RESULT -> RESULT | Checked multiplication |
| quotient | RESULT, RESULT -> RESULT | Checked integer division |
| equals | RESULT, RESULT -> RESULT | Success containing 0 or 1 |
| less | RESULT, RESULT -> RESULT | Success containing 0 or 1 |
| choose | RESULT, RESULT, RESULT -> RESULT | Select one branch using a successful 0/1 condition |

Binary functions inspect the left result before the right. The first failure
propagates unchanged. Arithmetic rejects overflow before subsequent division;
it never silently wraps or saturates. `choose` propagates a failed condition,
rejects a successful condition outside {0,1}, and evaluates only the selected
branch. Unselected, admitted arithmetic failures remain unevaluated.

All helper calls retain ordinary PLAN demand semantics. Returning an unused
argument does not force the other arguments. A future EVM backend must preserve
this behavior or prove a transformation equivalent; it cannot indiscriminately
evaluate every argument before a call.

## Bounds and rejection

An artifact contains 1–64 definitions. Each law takes 1–16 arguments. Validation
allows at most 128 nested expression/definition visits and 4,096 expanded visits
across the complete artifact. Helper bodies are charged again at each call site,
so repeated calls cannot hide an exponentially expanded graph behind a small
declaration count. This conservative budget is an admission bound, not EVM gas
or a formal runtime instruction count.

Rejection returns a diagnostic rather than evaluating the rejected program.
Diagnostics distinguish version, shape, signature, duplicate, missing entry,
entry type, self-reference, dynamic call, unknown callee, arity, expression type,
literal, recursion, depth, and budget errors. The exact diagnostic text is a
developer interface, not a consensus format.

The checker consumes fully materialized PLAN values from trusted construction
or structural decoding. It is not a sandbox for evaluating arbitrary live host
thunks handed to its API. A bounded untrusted byte decoder and canonical artifact
serialization remain separate work.

## Reference execution

The reference runner first validates the complete artifact, then verifies the
entry argument count and each argument's WORD range. It applies the admitted
entry law using the existing PLAN runtime, rather than interpreting a replacement
AST. Its result records validation failure, input failure, or the program's
RESULT separately. No transaction is sent and no chain state is consulted.

Acceptance tests must cover executable laws, helper dependencies, small quoted
constants, arithmetic limits, left-to-right failure propagation, lazy selection,
and the rejection boundaries above. Tests also construct a law through the
existing codegen backend and execute the admitted result. The earlier Foil word
and Paramutuel suites remain regression checks. EVM equivalence is deferred
until an EVM backend exists.

## Validation record

The checker and reference runner live in `src/reaver/restricted-plan.rvr`.
The acceptance suite lives in `src/reaver/restricted-plan-tests.rvr` and runs
through the normal test inventory. Its 63 assertion groups cover admission,
execution, rejection, and resource bounds. Two groups expand into 14 arithmetic
fixtures and 196 comparisons with independently compiled Foil arithmetic helpers.
The Foil adapter lives in `src/foil/test_fixtures/ethereum_word_reference.foil`.

The initial acceptance run failed because the implementation module was absent.
The implemented suite passed in 3.6 seconds. The existing word and Paramutuel
suites passed all 42 checks in a separate regression run. These results use the
checkout's pinned Enki runtime, revision
`8961a1dc96742b16f4309e0cf99ad180408e0099`.

Reproduce from the repository root:

```sh
nix develop .#eden --command sh x/check restricted-plan-tests foil:tests/ethereum_word foil:tests/paramutuel_rules
```

This evidence establishes admission and PLAN execution for the pure word
profile. It does not establish EVM equivalence, safe decoding of hostile bytes,
or a general Foil contract frontend. The next compiler slice should lower a
small Foil contract expression into this profile and compare its PLAN result
with emitted EVM bytecode. Storage and transaction effects need their own
specified extension. Privacy and settlement remain independent decisions.
