# Biparser project plan

Branching the biparser work into a focused project: binary serialization for foil, with a witness/diff layer that lifts raw memory ops out of structural diffs.

## Goals

- **Bare minimum**: binary serialization (Liam's ask).
- **Schema-driven**, not self-describing.
- **Little-endian** integer primitives.
- **Witness/trace** so structural diffs can be pushed through a biparser to produce a bag of byte-level memory writes.

## File structure

```
reaver/src/reaver/
├── biparser-tr.rvr          [keep as-is]    CPS plumbing
├── biparser-k7.rvr          [keep as-is]    Cassette record + structural combinators
├── biparser-run.rvr         [extract]       parse / pretty entry points
├── biparser-bytes.rvr       [extract]       Byte-stream substrate
├── biparser-combinator.rvr  [trim]          Generic structural combinators
├── biparser-bin.rvr         [new]           Binary-width primitives
├── biparser-layout.rvr      [new]           Binary layout combinators
├── biparser-witness.rvr     [new]           Witness-emitting interpretation
├── biparser-diff.rvr        [new]           Structural diff + push-through-witness
└── tests/
    ├── biparser-test-bin.rvr
    ├── biparser-test-layout.rvr
    ├── biparser-test-witness.rvr
    └── biparser-test-diff.rvr
```

## Module contents

### biparser-tr.rvr — _unchanged_

CPS combinators (host-agnostic).

- `tr-id`, `tr-empty`, `tr-compose`, `tr-alt`
- helpers: `tr-compose-success`, `tr-alt-fail`

### biparser-k7.rvr — _unchanged_

Cassette record bundling sideA (pretty) and sideB (parse).

- `k7-mk`, `k7-sideA`, `k7-sideB`, `k7-id`
- `k7-compose`, `k7-alt`, `k7-cons`
- con helpers: `k7-b-done`, `k7-b-con-success`, `k7-con-B`, `k7-a-con-success`, `k7-con-A`

### biparser-run.rvr — _extracted from biparser-prim_

Top-level entry points. Split out so they aren't entangled with primitive definitions.

- `parse-ok-k`, `parse-fail-k`, `parse`
- `pretty-ok-k`, `pretty-fail-k`, `pretty`

### biparser-bytes.rvr — _extracted from biparser-prim_

Byte-stream substrate. Generic over text/binary — these primitives only know about bytes.

- Stream ops: `str-head`, `str-tail`, `str-empty?`
- `satisfy` (recast as byte-predicate, not char) + impls
- `eof`, `nothing`, `empty-k7`
- `set` / `unset` (constant-injection pair) + impls

### biparser-combinator.rvr — _trimmed_

Structural combinators that apply to any element type. Drop the text-grammar combinators (`sepBy`, `between`, `chainl`).

- `choice`, `many`, `some`, `option`
- existing helpers for `many` (`many-A-step`, `many-A-impl`, `many-B-impl`, etc.)

### biparser-bin.rvr — _new_

Binary-width primitives. Little-endian.

- `any-byte` — accept-any single-byte cassette
- `u8`, `u16-le`, `u32-le`, `u64-le` — width-typed integer cassettes
- `take-n` — opaque N-byte blob
- pure helpers: `int-of-bytes-le`, `bytes-of-int-le`

### biparser-layout.rvr — _new_

Binary layout combinators. These own enough trace structure that diff replay falls out automatically.

- `replicate-n` — fixed-count repetition (parses N, prints N)
- `length-prefixed` — owns BOTH the length prefix and the payload, so re-emits the prefix when payload size changes (Dr. Sarkon note 2)
- `tagged-alt` — emits a discriminant byte then dispatches; sum-variant changes re-print the whole region (Dr. Sarkon note 1)
- `fixed-array` — convenience: `replicate-n` with a static count

### biparser-witness.rvr — _new_

A third interpretation of the cassette. Pretty-printing instrumented to record per-substructure byte ranges.

**Design choice — pick before writing:**

- **(a) sideW**: extend `k7-mk` to a triple `(k7-mk sideA sideB sideW)`. Every primitive supplies a witness-emitting variant.
- **(b) instrumented sideA**: keep the cassette binary; run sideA in a tracing mode that threads `(offset, span-tree)` alongside the byte buffer.

Default recommendation: **(b)**. Fewer touch-points; primitives don't grow a third side; witness is a runtime mode of pretty rather than a parallel structure. Decide with Liam.

- `pretty-with-witness` — runs sideA in tracing mode, returns `(bytes, witness-tree)`
- `witness-tree-mk`, `witness-tree-leaf`, `witness-tree-cons`, `witness-tree-alt-pick`
- `witness-lookup` — `(witness, structural-path) → (offset, length)`

### biparser-diff.rvr — _new_

Structural diffs and their push-through-witness machinery. This is the foil / raw-memory-ops payoff.

- Diff constructors: `diff-refl`, `diff-replace`, `diff-cons`, `diff-variant`, `diff-list`
- `push-diff` — `(cassette, witness, value, diff) → list-of-splices`, splice = `[offset old-length new-bytes]`
- `apply-splices` — apply splices to a byte buffer (debug/test helper)
- Internal: walks diff + witness in lockstep, only re-runs `pretty` on changed substructures

## Build order

1. **tr → k7 → run → bytes → combinator** — refactor + extract; no behavior change. Existing tests pass throughout.
2. **bin** — test: `u8`/`u16-le`/`u32-le`/`u64-le` roundtrips on hand-written byte literals.
3. **layout** — test: length-prefixed string blob, tagged sum.
4. **witness** — test: structural path → offset matches hand-computed values for a known struct.
5. **diff** — test: change one field of a struct, observe the correct single splice.

Steps 1–3 unblock Liam's bare-minimum binary serialization goal. Steps 4–5 are where the foil/raw-memory-ops vision lands.

## Open questions for Liam

- Witness design (a) vs (b) above. Affects whether every primitive grows a third arm, or whether the witness lives entirely in the runner.
- Diff representation shape — do we need a typed `Diff` parametrized by the schema, or is a generic structural diff enough at this stage?
- Length-prefix encoding: does the prefix width get parameterized per-call (so `length-prefixed u32-le inner` is distinct from `length-prefixed u16-le inner`), or do we pick one canonical width?
