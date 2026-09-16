# Physical read selection

The debugger's physical selection layer, also used by the separate
[bounded wire projection](debugger-physical-wire.md). The namespace adapter
selects the path's authority before calling the sovereign selector below.
This does not make ordinary namespace or derived evaluation bounded.

## Contract

`physical_read/read(request, sovereign)` returns either an explicit error or
one page captured from that immutable sovereign value. It neither executes a
view nor creates a task, commit, journal entry, or operation.

| Request field | Meaning |
| --- | --- |
| `pax` | Absolute physical namespace path. The walk is proportional to this supplied path, not to its subtree size. |
| `epoch` | Omitted on an initial page, or exactly the current sovereign `top`. Required with any `after` cursor. |
| `collection` | `children` for immediate physical child keys; `slots` for opaque keys within the own record. |
| `after` | Exclusive structural key, not an offset or display label. One iota wrapped in a path for children; an arbitrary path for slots. `some []` is a valid slot cursor and differs from no cursor. |
| `limit` | 1–40 displayed entries. The selector requests one additional entry for lookahead. |

Pages include the request identity, captured epoch, collection, limit, exact
collection total, own-node metadata, selected entries, and an optional next
cursor. The cursor is the **last displayed key**, never the lookahead key.
Its absence means the selected collection is exhausted at that epoch. There
is no sorting by rendered strings or truncation of the structural cursor.

Both collections currently require an exact current epoch, including initial
requests which explicitly supply one. A later commit returns `epoch_conflict`
before inspecting the index. The caller must request a fresh initial page;
it must not silently mix pages. Historical assertions alone cannot reconstruct
the old child set from the current physical index. A future immutable-slot
transport could safely offer historical record paging as a separate contract.

### Children

Ordering is the namespace's ascending `lt_iota`, through the seekable
`bee/range_after`. The total is the cached physical key count, **not a count of
live records or a y-frontier count**. Transparent, empty, and history-retained
child keys occupy ordinary page positions and remain expandable.

Each selected child has its exact key and own-node metadata:

- The floor assertion at the captured epoch, or no assertion.
- The assertion's actual epoch, if present.
- Its cached physical child count.

A live assertion retains the original pinned record. A tombstone retains its
own version metadata. No assertion is not an invented empty record. The
selection does not unpin any child record, inspect its slots, or enumerate its
descendants. Child-history resolution happens only for displayed entries, not
the lookahead entry. Resolving the parent's own metadata is one additional
history lookup.

### Slots

Ordering is ascending `lt_pith`, through `mop/range_after`. A slot such as
`['a', 'b']` remains one opaque record key, not namespace children `a/b`.
The empty slot key is preserved. The cached record size is the exact total.
Selected entries retain their original pails; neither the selector nor the
page determines how to render them.

Unknown own assertions return `record_missing`; tombstones return
`record_deleted`. They are not represented as successfully empty records.
An actual empty live record returns an empty successful page.

### Errors and interpretation

Invalid limits, collection names, or cursor shapes fail before reading the
index. Absent physical paths return
`path_missing`, distinct from existing transparent nodes. `/h`, `/o`, and `/x`
targets return `derived_path`; this API never substitutes physical keys for
their actual historical or computed output. The existing resolver and its
x/y/z meanings are unchanged.

## What is and is not bounded

This layer bounds **selection and traversal**, not arbitrary stored data or
serialized bytes. Its primitives seek to the exclusive cursor and stop once
the requested number of entries is selected. They do not flatten a collection
and discard a prefix. Zero-limit primitive calls do not inspect the map.

The internal page is deliberately **not a wire response**. Do not pass it to
generic `show`, JSON conversion, HTML rendering, or an actor message that
would serialize its arbitrary pails. In particular:

- A single slot pail or key can be arbitrarily large.
- A history or whole record is held behind a pin; cold pin loading does not
  become bounded merely because the subsequent walk is bounded.
- Comparison cost depends on key sizes and common path prefixes, not only on
  entry count.
- B-tree work also depends on its height and retained structure after lazy
  deletion. Cached empty limbs can be skipped, but reaching those limb headers
  still has a cost; this is not a constant-time database read guarantee.
- Internal paths and cursor keys are preserved without depth/byte clipping,
  so a selected deep slot key remains a usable continuation. A transport must
  design its request/response budgets together rather than emit cursors it
  cannot accept back.
- Seek semantics assume the stored comparator/index invariants. An inherited
  overwidth `rs`/`rd` defect can cycle after-seeks and break ordinary lookup;
  [the reproduced limitation](debugger-ordering-limits.md) remains unresolved.
  Preserving those raw identities does not prove complete pagination for them.

The internal API is pure and lazy, with no exception-forcing boundary of its
own. Tests must inspect selected keys and metadata, not just the outer success
tag. The separate wire adapter forces its entire bounded encoding inside an
error boundary so malformed stored data cannot strand a supervisor reply.

The wire layer adds explicit byte budgets for keys and summaries, lossless
identities, honest oversized/opaque outcomes, and bounded authored metadata.
Unrestricted traversal position, oversized-key access, and integration remain
separate work, including the inherited ordering limitation above.
Full values must remain separately
accessible under the [typed-value contract](debugger-value-read.md). Operation
registries, local-case links, derived evaluation, and large mounted tree DOMs
remain independent release gates.

## Verification and activation

Permanent native tests live in `tests/bee_range_after`,
`tests/mop_range_after`, and `tests/physical_read`. They run against disposable
compiler-bootstrap copies, never the live SRS namespace. Traversal guards use
deliberately inaccessible branches and values: a limited read must avoid them,
while a larger or unbounded control must reach them. Large fixtures verify
complete multi-page access, native ordering, and exclusive cursors.

The initial verified slice passed 154 new native checks across these three
suites, 309 existing index checks, and two existing Grove regression suites.
See the [performance report](debugger-performance.md) for current measurements
and limitations. These initial results are functional and
traversal checks, not cold-I/O or HTTP latency benchmarks.

The selector performs no live state migration. Verify changes in a disposable
namespace; an existing preview is not evidence of the current source build.
