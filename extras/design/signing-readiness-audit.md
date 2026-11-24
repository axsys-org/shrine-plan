# Signing readiness audit

The installed Wisp runtime can hash, sign and verify today. Shrine does not yet
authenticate its assertions. The useful type migration is to preserve assertions
at committed-read and dependency boundaries, while retaining `myth` for pending
writes, pure computations and presentation data.

This audit is dated 2026-11-24. It leaves the authority/key-registry choice open.
The inventory describes the source before the read migration below. Signing
remains disabled.

## Read migration

Stored and computed committed reads now share `axal[saga]`, including
`namespace_reader.page`, `store_page`, `store_visible`, `view`, `resolve_view`,
`peek`, `sovereign_view`, `sovereign_peek` and `sovereign_care`.
`sov/y_at`, `z_at` and their query/latest wrappers retain assertions too.
Single-record consumers can use `sov/assertion_at` and `assertion_query`; the
existing `x_at`/`x_query` helpers remain plain-value projections.

Physical reads preserve the original aeon and content pin, including through
historical views. Computed results receive their own unsigned aeon, using the
view's selected/current data case. Computed reads do not have a stored shape or
time ledger: their shape, time and block fields remain zero rather than copying
unrelated source metadata. Reverse reads use their reference snapshot epoch;
version-metadata reads follow the target authority's displayed top epoch.

`bowl.crew`, `crew_of`, `sovereign_crew_of` and `dispatch_reader.hydrate` now carry
`mop[path axal[saga] lt_pith]` for both physical and computed dependencies. There
is no stored/computed sum type. `saga/value`, `saga/values`, `bowl.crew_value` and
explicitly named value-read helpers provide plain data to existing handlers.
Pending reads, `bowl.kids`, cell constructors and computed payloads remain `myth`.

The recommendations below record the original investigation; the uniform read
contract above supersedes suggestions to distinguish physical and computed reads
with separate result variants.

## Signing model and recursion points

The intended signing unit is an x assertion. Subtrees and folders are deliberately
not signed as recursive commitments. To sign a y/z response, an explicit overlay
rolls it into an x value, which is signed through the x assertion mechanism.

A recursion point at P is opaque to descendant-driven version propagation: child
and descendant changes do not advance P's y/z versions. P's own x bumps can still
advance them. This prevents P's versions from exposing the timing of changes
below it. Conceptually `/` is a recursion point; declaring another allows the
global namespace to be glued to itself. This is the formal basis of overlays.
General recursion-point infrastructure is not implemented yet.

These are design constraints supplied by the system's author, rather than claims
that all of this infrastructure exists in the current implementation. The signing
design must preserve them: no mandatory ancestor digest or snapshot commitment
that changes whenever an opaque descendant changes. An overlay rollup is an
explicit observation, not automatic propagation through the namespace hierarchy.

Accordingly, an ordinary axal[saga] response is a collection of individual live
assertions, not a cryptographic completeness claim about its tree. This is
intentional, not a missing requirement for basic signing. If an aggregate response
needs attestation, the overlay's x value must express the aggregate being attested.
Tombstone representation remains a separate question from aggregate attestation.

## Crypto availability

The installed runtime was probed directly through Reaver operation 83:

`/nix/store/y4y0hwcwg7d8g7rvksb9md05jwa1w2w8-enki-pgo-0.1.0/bin/wisp`

| Operation | Observed interface | Live validation |
| --- | --- | --- |
| `Blake3` | Message bar → 32-byte digest bar | Empty, `abc`, one zero byte |
| `Sha256` | Message bar → 32-byte digest bar | Empty, `abc`, one zero byte |
| `Blake3Keyed` | 32-byte key bar, message bar → 32-byte MAC bar | Known-answer vector |
| `HmacSha256` | Key bar, message bar → 32-byte MAC bar | RFC 4231 test vector |
| `Ed25519PublicKey` | 32-byte seed bar → 32-byte public-key bar | RFC 8032 test vector |
| `Ed25519Sign` | Seed bar, message bar → 64-byte detached signature bar | RFC 8032 empty-message vector |
| `Ed25519Verify` | Public-key bar, message bar, signature bar → boolean | Valid signature; rejection of changed message, changed signature, short key/signature and invalid message bar |
| `BatHash` | BAT → SHA-256 digest bar | `abc` known-answer vector |

All **17 comparisons passed**. The probe source and individual results are in
[the inventory JSON](signing-readiness-audit.json), under `crypto_probe`; the
execution log is `.check/signing-probe/out.log`. Only public test-vector seeds
were used. These probes establish operation availability and these specific
behaviors; they are not a cryptographic implementation audit.

The local Enki checkout registers these operations in
`/Users/test/dev/enki/pkg/plan/src/op.c:1723`; implementations are in
`pkg/plan/src/rplan.c:853`. Byte inputs are canonical bars: payload bytes followed
by a `0x01` terminator, represented as a little-endian natural. Thus empty is `1`,
not `0`, and trailing zero bytes remain meaningful. Verification rejects malformed
bars with false; the other crypto functions raise on invalid input. Native
temporary secret buffers are cleared, but a seed passed as a PLAN value remains
ordinary managed data. This is not a key-custody interface.

There are two integration gaps:

1. [Foil's FFI registry](../../src/reaver/foil-builtins.rvr) exposes BAT creation,
   concatenation and flattening, but no typed crypto bindings, including
   `bat_hash`. Reaver already wraps `BatHash` in
   [bat.rvr](../../src/reaver/bat.rvr).
2. No secure-random/key-generation or protected signing-key service was found in
   the inspected operation registry. `Ed25519PublicKey` derives a public key from
   an existing seed; it does not generate entropy. `bowl.eny` has not been
   established as a suitable cryptographic entropy source.

The runtime links libsodium, BLAKE3 and OpenSSL. Linked libraries do not establish
that additional algorithms are exposed to Foil. This audit found no exposed
secp256k1 or X25519 operation in that registry, and makes no PKI-compatibility
claim. HMAC/keyed hashing are shared-secret MAC operations, not public-key
signatures.

Reproducibility also needs attention: `flake.lock` pins Enki
`8961a1dc96742b16f4309e0cf99ad180408e0099`; the inspected local checkout is dirty at
`3efc575dd298ec91df1fa8a15286a0ba54f11ebd`. The runtime tests establish what this
installed binary supports, not what a fresh build of the locked revision will
support. Confirm the dependency revision before wiring these operations into a
reproducible build.

## Current assertion lifecycle

[shrine.foil](../../src/foil/sys/shrine.foil) explicitly defines `oath` as unsigned
scaffolding: `sig=nat prev_hash=nat`, both zero. `saga` holds an `aeon` and a
`pin[myth]`; the `aeon` combines clocks (`yuga`) with the `oath`.

In [namespace.foil](../../src/foil/namespace.foil), `ass/next` creates both live
assertions and tombstones through `aeon/unsigned`. The path is
`sov/walk → sov/finish → sov/finish_tree → ass/next`. Content pins are shared on
version-only remints. Pin identity/content addressing is not signer authenticity.
The `sign` values used by the store are change grades/notifications, not signatures.

Do not insert an effectful signer directly into `ass/next`. `namespace/trial`
can build multiple candidate states, and `namespace/step` runs the store again
after deriving indexes and adding the journal record. Signing must operate on the
final accepted x assertions, accounting for index records, journal records and
tombstones under the chosen assertion contract. It must preserve content-pin
sharing and avoid re-signing unchanged history. Current clock propagation can
remint an ancestor's header without changing its record content; deciding which
header fields are signed must respect the recursion-point model rather than
requiring every descendant change to produce an ancestor signature.

`namespace_event` is also explicitly unsigned. `namespace/replay` checks the
selected system publication and predecessor epoch, then recomputes the commit.
A signed replay/import design must retain or supply original signatures and
verify them against recomputed assertions; it must not require possession of
the original authority's private key. The current event payload does not carry
that signature material.

## Audit of tree types

The lexical inventory covers **491 occurrences on 470 lines in 49 Foil files**.
It includes type signatures, local annotations, generated source strings and
comments, rather than 491 distinct call sites. Each matching line has its file,
line, enclosing declaration, source text and recommendation in
[signing-readiness-audit.json](signing-readiness-audit.json). Source hashes identify
the snapshot. Inferred tree values and `axal/new[myth]` are not counted by this
literal-type scan; the boundary analysis below also follows important direct
`myth` and existing `saga` paths.

| Area | Recommendation | Reason |
| --- | --- | --- |
| `sov/y_at`, `z_at`, query/latest wrappers; `store_page`, `store_visible` | Preserve `axal[saga]` in the physical-read API; provide explicit data projection | These read committed physical records and currently discard their headers. |
| `namespace/records`, `frontier`, `root`, `page` | Retain their existing `axal[saga]` interfaces | These already preserve live assertions. Root composition is a view, not a newly signed root assertion. |
| `namespace_reader`, `store_reader`, `sovereign_reader`, `view`, `resolve_view`, `peek`, `sovereign_peek`, `sovereign_care`, historical dispatch | Separate physical assertions from derived answers in a read envelope | These paths mix stored records, synthetic markers, transparent prefixes and computed views. A blanket `saga` result would misrepresent synthetic data. |
| `crew_of`, `sovereign_crew_of`, `dispatch_reader.hydrate`, `bowl.crew` | Preserve committed assertion/provenance evidence | This is the strongest migration target. Keep the outer map keyed by dependency slot; physical payloads can be `axal[saga]`, virtual ones need derived evidence. |
| `muck`, `read`, `sovereign_read`, `dispatch_reader.children`, `bowl.kids` | Keep `axal[myth]` | Pending notes can replace, merge or delete records; they have no final committed header yet. |
| Woven observations, memoization, evaluation results and overlay caches | Carry evidence beside plain values | Cache validity and dependency references currently establish versions, not cryptographic verification. Verify inputs and executable definitions before evaluation; retain evidence for reuse. |
| `apply_cell_ctor`, legacy cells, `knit`, `felt`, `sewn`, `spun`, `cell`, `cell_view`, `weft_std`, `graph` | Keep plain data inputs/outputs behind the checked read boundary | Constructors transform/readdress data. Output records cannot inherit signatures from their inputs. |
| History/version/reverse markers, origins, faults, `view_project` | Keep `axal[myth]`; describe derivation separately | These synthesize fields or remove slots. An original whole-record signature cannot validate the modified record. |
| Publication inputs, compiler documentation, boot seeds, Grove validation/generated code | Keep `axal[myth]` | They describe candidate records and pure checks before final commit. |
| Inspector, MCP serialization, debugger/web presentation | Add evidence to export contracts where verification is needed | Current output carries values, counters and pinned references, not a portable signed assertion contract. Renderers can still consume plain values. |
| Other mount consumers and tests | Keep pure consumers plain; adapt dependency adapters and fixtures | Authenticating once at the read boundary avoids threading signatures through every HTML builder or record transformation. |

The `bowl.crew` TODO already points toward this change, but its proposed shorthand
must not erase the outer map: the current type is
`mop[path axal[myth] lt_pith]`, where each key is a dependency slot, not a record
address. With only physical dependencies, the corresponding shape would be
`mop[path axal[saga] lt_pith]`. An overlay result attested as x can also carry its
own assertion. Virtual values that have not been attested must remain
distinguishable; they cannot borrow a source record's signature.

An assertion-preserving physical read must retain current semantics. In
particular, `peek`/`store_visible` work under transparent prefixes where
`namespace/page` can return unknown. Replacing their implementation with a call
to `page` would change behavior. Preserve the care-y frontier and case-to-epoch
translation rather than treating a data case as a store epoch.

## Boundaries a literal type replacement misses

- `ass/res`, `sov/x_at`/`x_latest`, `read_x`, `dispatch_reader.exact` and
  `resolve_access` handle individual `myth` records. Executable forms, schema
  definitions and weft definitions need the same trust policy as tree reads.
  In-flight local definitions remain proposals authorized by the transaction;
  they cannot be verified as already committed assertions.
- `helm/supervisor/access.page`, `feet/task` payloads, filesystem/HTTP feet,
  Hyp reads and Codex drivers already transport `axal[saga]`. That type currently
  carries zeroed oaths; it does not mean verification has occurred. Local
  capability-protected IPC can remain a trusted boundary, while remote ingestion
  needs explicit verification before data is treated as authoritative.
- `value_read`, `physical_read` and `physical_projection` also expose records
  through single-record or JSON contracts. The same export policy applies even
  though these APIs do not show up in the `axal[myth]` inventory.
- MCP `node_json`/`query_node` and the inspector's `versions` tree expose stable
  references or version metadata. Those are useful citations, but not signatures
  or proofs. Diagnostic JSON may also omit or abbreviate values; signing that
  projection would be a distinct claim from signing the stored record.

## What must be defined before enabling signing

The x assertion contract and its integration still need definition. Aggregate
attestation is handled by explicit overlays, not by signing subtree structure:

1. **Assertion identity and bytes.** Define a versioned, domain-separated canonical
   message binding the x assertion's identity, content or tombstone tag, relevant
   version information, predecessor digest and key identity/version. Specify the
   signed fields without introducing descendant-dependent commitments across a
   recursion point. `yuga` does not include path or authority, and `oath` does not
   currently identify a key. Neither printed Foil nor display JSON is an
   established signing encoding.
2. **Deletion and absence.** `ass/nul` retains an `aeon`, whereas `saga` only carries
   live records. `namespace/page` returns `.null` without tombstone evidence.
   Define an assertion envelope that can carry deletions, and distinguish a
   proven absence from an unresolved lookup.
3. **Overlay rollups.** A y/z response requiring attestation is rolled into x by
   an overlay. Define what that x value asserts, including selection and extent
   when relevant. Do not require raw y/z responses to carry signed folders,
   ancestor commitments or membership proofs. Historical validity and freshness
   remain distinct questions for the x assertion.
4. **Derived answers.** A signed overlay result has its own x assertion; it does
   not inherit input signatures. Preserve source assertions and derivation
   context where consumers need them, while allowing ordinary computation on
   plain `axal[myth]`. Signing attests the resulting x value; it does not by itself
   constitute a proof of the computation.
5. **Key and replay policy.** Define authority lookup, rotation/revocation behavior,
   genesis/predecessor semantics, and handling of existing unsigned history. Keep
   legacy unsigned data distinguishable from verified data; zero signatures must
   not silently become a successful verification result.

Storage signatures attest committed assertions. They do not by themselves
authenticate an incoming write request. Request admission remains a separate
capability/authentication boundary.

## Suggested implementation order

1. Pin a runtime revision with the probed operations. Add typed byte/key/signature
   wrappers and Foil FFI bindings, with known-answer and malformed-input tests.
2. Define the x assertion contract and a checked conversion to plain records.
   Preserve a distinct state for unsigned legacy assertions. Design the key
   lookup/signer interfaces without committing to a particular registry.
3. Preserve assertions through physical reads and dependency hydration; attach
   evidence to virtual-read evaluation and caches. Leave pure constructors and
   pending-write APIs as `myth`.
4. Sign only final accepted assertions and verify imported assertions before
   admission. Resolve replay and tombstone handling, then expose attested overlay
   rollups for y/z responses that require aggregate attestation.
5. Enable enforcement after tests cover altered content/path/clocks, incorrect
   keys, malformed signatures, deleted/recreated records, replay and overlay
   rollups. As recursion-point infrastructure is introduced, test that descendant
   changes leave P's y/z versions unchanged while P's own x bumps retain their
   intended effect. Benchmark signing against the final x assertion set.
