# Merkle subtree watcher specialization

`src/reaver/ilc-watch-merkle.rvr` implements an alternative to the flat watcher
specialization in `ilc-watch.rvr`. It uses the actual `axal` child pins as content
identities. It does not change the production driver.

The cover is hierarchical: each node owns its local subscription bucket and
delegates descendant regions to its compiled children. These ownership regions
are disjoint, so ancestor subscriptions and intentional duplicate subscribers
are preserved without deduplicating notifications.

`pe.rvr` specializes a shared dispatcher against the static runtime API. Each
compiled subtree closes this dispatcher over a source pin, a precomputed care
partition table and a child-plan index. Rebuilding identical dispatcher code at
every node adds cost without eliminating more dynamic work. The top-level
residual has one argument: the incoming sign tree.

An ILC custom derivative transfers the previous specialization cache:

```scheme
(define old (merkle:specialize api eyes))
(define next (merkle:update api old (watch:watch-change api edits)))
((merkle:program next) signs)  ; [notifications remaining-watchers]
```

Edits use the same format as the flat implementation: `[path 0]` deletes a local
bucket, `[path [subscribers]]` replaces it, and `[path [[]]]` installs an empty
bucket. Deletion preserves descendants. Repeated paths have last-write
semantics. Unknown ILC change forms fall back to full specialization.

The update first groups edits into a trie, then patches and repins their shared
ancestors once. Compilation visits only affected branches. An unchanged source
pin retains its old plan; a source pin in the history cache reuses its entire
compiled subtree. Other nodes reuse unchanged local tables and child plans.
The memo belongs to the returned cache, not a process-global memo table. Its
scope includes the compiler, dispatcher, PE implementation and runtime API.

The default history limit is 4096 entries. If history exceeds this soft limit,
the next update discards it while retaining the active compiled tree. One batch
can exceed the limit; this is not a byte-level memory bound. Use
`specialize-with-limit api 0 eyes` to discard history before each update. Active
subtree reuse still works. A generic replacement change starts a new default
cache. `stats` returns `[built unchanged-reuses history-hits tables-built]` for
the last compilation; untouched branches are not traversed or counted.

The extended API retains the flat implementation's first nine slots and adds
`bee/get`, `bee/tap`, and `axal/kid_put`. The fixture resolves these from the real
Foil runtime. The implementation relies on the current `axal`/`axal/k` layouts.

## Reproducing the comparison

```sh
WISP=/path/to/wisp x/check pe-tests ilc-tests ilc-watch-tests specialize-tests
WISP=/path/to/wisp x/bench-ilc-watch-merkle --samples 7 --cycles 32 --events 10
```

The benchmark freezes its sources and retains input, raw logs, source hashes,
runtime identity, per-sample timings and JSON summaries under `.check/`.
It compares production `react`, the committed flat specialization (`cbc4cabf`),
Merkle specialization, and Merkle specialization with history disabled.

Every strategy starts from the same 128 buckets: 16 regions of eight buckets,
with 16 subscribers each. Every cycle replaces 32 genuine buckets and then
handles ten events, each touching two buckets. Clustered edits replace all
eight buckets in four regions; scattered edits replace two in each region.
Subscriber identities include bucket and revision, preventing accidental
cross-bucket content deduplication.

Three revision streams separate different kinds of reuse:

- **Fresh:** all 32 edited buckets have never-seen contents.
- **Revisited:** all 32 alternate between two configurations. After two cycles,
  the whole root can hit history; a whole-state memo could exploit this too.
- **Subtree-revisited:** 31 buckets alternate, while one always has fresh
  contents. Whole roots never repeat, so hits require proper subtrees.

Lifecycle timings include edits, hashing, compilation, history maintenance and
event dispatch. The entire updated cache is forced before events. Initial
construction is timed separately. Validation checks notifications and remaining
subscriptions against production outside the timing windows. Timed dispatch
forces notifications only, matching the production caller's demand. Fixture
compilation, input generation, hive/lens processing and the rest of the
sovereign cycle are excluded. Each sample begins from the initial cache; the
explicit memo is not warmed by earlier samples or semantic validation.

There is a separate update-only timer for each strategy. Lifecycle and update timing order reverses
on alternating samples. These are controlled microbenchmarks, not production
latency measurements or a universal crossover threshold.

## Measurements

Seven samples of 32 cycles each, ten events after every 32-edit batch. Medians
in milliseconds per cycle; initial cache construction excluded. Every reuse
case includes its first two cold updates.

| Edit distribution / contents | Production f | Flat ILC | Merkle ILC | Merkle, history disabled | Flat / Merkle |
| --- | ---: | ---: | ---: | ---: | ---: |
| clustered-fresh | 21.610 | 10.565 | 17.021 | 11.412 | 0.62x |
| scattered-fresh | 21.537 | 10.680 | 21.618 | 13.634 | 0.49x |
| clustered-revisited | 21.689 | 10.589 | 3.262 | 11.422 | 3.25x |
| scattered-revisited | 22.396 | 11.162 | 3.750 | 14.601 | 2.98x |
| clustered-subtree-revisited | 22.269 | 10.698 | 5.451 | 11.351 | 1.96x |
| scattered-subtree-revisited | 21.962 | 10.838 | 6.640 | 13.675 | 1.63x |

Initial construction: flat **23.643 ms**, Merkle
**38.919 ms**. Merkle lost all seven paired samples for
fresh contents and won all seven for both revisit workloads. History-disabled
Merkle remained slower than flat: batching shared ancestors alone did not pay
for the extra hashing and compiled-plan maintenance on this workload.

The stricter subtree-revisited workload is the evidence for subtree caching:
31 buckets reuse prior configurations while one is fresh, so the whole root
never hits. After its first two updates, only four compiled nodes and one care
table are rebuilt per batch. Fresh clustered batches rebuild 38 nodes and 32
tables; fresh scattered batches rebuild 50 nodes and 32 tables.

| Workload | Flat update-only ms/batch | Merkle update-only ms/batch |
| --- | ---: | ---: |
| clustered-fresh | 9.372 | 16.353 |
| scattered-fresh | 9.615 | 21.123 |
| clustered-revisited | 9.016 | 2.757 |
| scattered-revisited | 9.984 | 3.261 |
| clustered-subtree-revisited | 9.813 | 4.968 |
| scattered-subtree-revisited | 9.464 | 6.316 |

The tradeoff is content recurrence as well as edit locality. These measurements
do not establish a universal cache-hit-rate cutoff. Whole-configuration reuse
can also be handled by a whole-state memo; the subtree-revisited cases isolate
the benefit that requires finer caching.

Runtime: `/nix/store/y4y0hwcwg7d8g7rvksb9md05jwa1w2w8-enki-pgo-0.1.0/bin/wisp`. Host: `macOS-26.3-arm64-arm-64bit-Mach-O`.
Raw report and frozen sources: `.check/ilc-watch-merkle-ujtnn56e/results.json`.
The frozen source snapshot was checked against the finished implementation.
The earlier checkpoint is commit `cbc4cabf`; `ilc-watch.rvr` is unchanged from it.

Validation passed: `pe-tests`, `ilc-tests` (including the demo),
`ilc-watch-tests` (including the new Merkle tests), and `specialize-tests`.
The Merkle tests cover all 27 care-grade combinations, root/empty/overlapping
paths, duplicate subscriptions, insertion/deletion, last-write behavior,
no-op reuse, unaffected sibling pins, root and proper-subtree history hits,
history eviction, API invalidation, generic-change fallback and ILC cache
transfer without evaluating the old watcher input.
