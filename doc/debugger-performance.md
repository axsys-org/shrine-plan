# Debugger read performance

The debugger remains a Grove-declared interface. Mash owns component behavior;
the browser bridge selects data, binds authored fragments, and manages requests.
No client-side document factory or standalone debugger renderer was introduced.

## Read path

Ordinary `/debug` GETs use `helm/card/debug` and `feet/gift/debug`. They do not
create, update, or cull `/io/http/r…` records. The supervisor returns a captured
read result without advancing its sovereign or hive. Finite selection is forced
inside the read error boundary before transfer; lazy selectors must not carry a
captured sovereign into the renderer's mailbox.

A persistent HTTP renderer owns the published Grove registry. It renders outside
the foot/coordinator mailbox, without spawning and copying a renderer closure
for every request. The normal application `/ns` transport is unchanged.

Physical debugger reads select at most 40 immediate child keys and 40 own slots
using ordered-map continuation queries (plus one lookahead). Fixed semantic
metadata, including the mani, remains available on each slot page. Children do
not hydrate grandchildren, generic application faces, or request crew views.
Operations are read directly from the relevant ancestor `/op` registries.

Continuations carry lossless slot/path keys and a captured epoch. A changed
namespace rejects the old cursor rather than mixing snapshots. Grove declares
the next-path/next-slot links. Navigation preserves their query in the address,
recent visits, and back/forward history; explicit refresh starts a fresh page.

## Rendering scopes

- A direct browser request receives the full document.
- `scope=workspace` supplies the main panel, inspector, and path metadata without
  recreating the application shell.
- `scope=outline` supplies path metadata without record/operation rendering.
- `scope=preview` requests authored record preview content explicitly.

Ordinary document/workspace responses no longer carry two hidden copies of the
record for reference and path previews. Reference inspection moves the requested
Grove-authored sections into the declared inspector container.

## Browser scheduling and retention

Navigation, tree expansion, locator menus, and previews share one coordinator:
three active requests maximum, at most two background requests, and foreground
priority. Compatible concurrent readers share immutable response text, never a
mutable Document. Each reader has independent cancellation. A queued reader
cancels immediately; the last subscriber cancels the fetch. Body reads have a
20-second timeout and 4 MiB wire budget.

New navigation supersedes older navigation; stale results cannot replace newer
content. Namespace writes retain their existing exclusion lock. Tree collapse,
navigation, and inline-preview closure cancel obsolete reads and suppress late
cache updates.

Sidebar snapshots are bounded to 128 entries / 30 seconds, summaries to 2,048
entries / 60 seconds, and expansion amounts to 128 entries. Preview and locator
caches keep their existing independent bounds. Snapshot child matching uses a
Set rather than a per-child linear scan.

## Collection algorithms

`sov/y_at` now uses a linked worklist, sharing its pending tail rather than
copying the whole remaining row on every pop and append. Live records still
terminate their branch; transparent and tombstoned paths pass through. Tests
cover historical barriers, missing roots, and exact frontier contents.

Query splitting and structural-key decoding accumulate list entries before a
single row conversion, removing repeated growth copies for maximum-size keys.
Slot partition counting uses an index rather than repeatedly dropping row heads.

## Verification and boundaries

Run the native selector regressions with:

```
python3 x/test_runner.py foil:tests/debug_read foil:tests/physical_read foil:tests/physical_key --jobs 1
node x/debug-preview-queue-test.mjs
```

Use `x/debug-grove-runtime.py` for a separately owned fresh runtime; never restart
or copy a user's live namespace for profiling. The declaration and HTTP browser
gates cover real Mash controls, mani rendering, case lanes, and narrow layouts.
`python3 x/debug-read-http-test.py <owned-runtime-manifest>` checks repeated
documents, scoped fragments, rejected epochs, disconnects and concurrent reads
without changing the epoch or retained HTTP-request count. Run this without a
concurrent write workflow. `x/debug-grove-workflow-test.mjs` separately verifies
real installation, rejected duplicate installation, exact slot bytes, reference
inspection and case-qualified derived/history reads in that disposable runtime.

### Measured verification, 2026-09-15

Observed locally, not cross-machine latency targets:

| Measurement | Previous audit | Fixed implementation |
| --- | ---: | ---: |
| `/hello` document median | 273 ms | 121 ms across 21 reads |
| SRS response used for navigation | 72,418 bytes | 34,511 bytes |
| SRS workspace / outline read | Full document route | 311 / 135 ms |
| 10,000-child browser parser | 194 ms | 11.5 ms |
| Epoch / retained requests after repeated debugger reads | +2 / +1 per read | Unchanged across 45 reads, including disconnect |

The new HTTP measurements came from a separate fresh native runtime. The old
audit used an instrumented runtime, so these are directional comparisons, not
a controlled universal speedup. The first cold SRS document still took 1.54 s;
large cold values are not made free by bounded collection selection. Three
concurrent SRS fragments finished in 346, 526 and 703 ms. Rendering is still
serialized by its persistent renderer; browser deduplication avoids repeating
identical concurrent reads from one debugger instance.

The maximum-size physical path/cursor regression completed in 9.2 s rather than
timing out at 20 s. Its full 631-request run returned all 10,000 children and all
10,000 slots exactly once across 250 pages per collection. Native regressions
also cover frontier barriers, transparent nodes, tombstones and historical reads.

These are selection and retention bounds, not a promise that arbitrary values
are cheap. A cold record pin, a large typed manifest, or user-defined derived
overlay can still be expensive. Derived x/y/z addresses continue through their
actual resolver; physical child paging must not silently change care semantics.
Operation registries are not yet paginated.

### Read-descriptor verification, 2026-09-16

Grove now supplies a bounded read descriptor instead of a hidden source tree and
browser-reconstructed record model. In paired inert-fixture measurements, model
parsing fell from 0.073 to 0.019 ms; the small leaf document grew from 24,771 to
25,128 bytes. These measurements ran under host load and are not end-to-end
navigation speedup claims. The native release gate, nine isolated browser
scenarios, and real Mash controls/responsive-layout checks passed.

The maximum-size physical path/cursor gate remains unresolved on this build:
controlled reads returned the correct `404 path_missing` but took 28.29 and
28.28 seconds, exceeding the unchanged 20-second limit. An active stack sample
found 9 of 11 samples in copying garbage collection. Neither the allocation
source nor a causal link to the descriptor is established; physical transport
does not invoke its renderer. This is a release-verification failure, not a
passing performance result or a reason to increase the timeout.
The 10,000-event journal fixture also exceeded its unchanged 900-second startup
guard after the fixture-ready marker, including a serial rerun. Those logs did
not isolate the slow startup phase. A later unmodified-source, startup-only
control listened in 280.091 seconds; it did not run the journal HTTP checks or
explain the earlier timing spike. The value fixture
completed 56 HTTP checks before its first edit exceeded 20 seconds during the
concurrent run; its remaining mutation and saved-artifact checks are unverified.
All disposable workers were stopped; these gates still require successful reruns.

The existing `/x/...` grammar treats its entire tail as the defining datum;
appending a rendered result-child key is not a valid way to address that child.
Case-qualified `/h/z/<case>/<target-length>/...target/...child` reads do work.
The workflow verifies that explicit form; automatic child-link canonicalization
for bare `/x` results remains separate UI/resolver integration work.

Browser cancellation is not native computation preemption. Once pure work is
running, the actor API does not expose a safe interruption primitive. The new
transport prevents aborted debugger reads from mutating or retaining namespace
history, but does not claim that an already-running native evaluation stops at
disconnect. Hard preemption requires a separate runtime protocol.
