# Foil compilation performance roadmap

## Measured checkpoint: 2026-07-13

The immediate performance problem has changed. The current Milestone 1 work
puts fresh `lain` and `helmapp` compilation inside their original wall-clock
targets in the forced profiling harness. Persistent artifacts do not yet make a
new process faster: the measured `helmapp` artifact paths are substantially
slower than a fresh source build.

The roadmap therefore prioritizes artifact observability, replay cost, and
snapshot footprint before any further type-lattice redesign.

### Status summary

| Area | Current status |
| --- | --- |
| Milestone 1 type/elaboration changes | Implemented; performance gate passed; final semantic validation pending |
| Fresh `lain` target (`<= 30s`) | Provisionally passed: 22.25s median wall, 6.37s median elaboration+WF |
| Fresh `helmapp` target (`<= 55s`, 50s stretch) | Provisionally passed: 30.00s median wall |
| Persistent artifact representation | Implemented and previously exercised on smaller module graphs |
| Warm `helmapp` artifact target (`10–20s`) | Failed: fully forced resumed path measured about 70s wall; hit/miss attribution pending |
| Clean artifact refresh | Failed relative to fresh source: 56.8s versus 30.0s median source build |
| Full Forge/Buddy/Helm regression gate | Not complete; earlier runs were interrupted after long stalls |

“Provisionally passed” means the performance result is measured, but the
current worktree has not yet completed the full correctness and launcher test
matrix after its final nesting-cache-key change.

## Clocks and measurement method

Four clocks must remain separate:

1. **Active Foil compilation**: parse/split, imports, elaboration and
   well-formedness, const materialization, and lowering. Explicit RPLAN zones
   measure this clock and pause while the PLAN thread is yielded or blocked.
2. **Compiler process wall time**: snapshot restore, RVR module restoration or
   compilation, active Foil work, output, and snapshot save.
3. **Artifact warm/replay time**: artifact validation, dependency traversal,
   subject reconstruction, merge/mount work, and any persistent-cache save.
4. **Application startup**: compilation or artifact replay plus actor call-graph
   warmup, boot mirroring, namespace seeding, and coordinator/listener startup.

The current profiling harness is opt-in and does not change the normal
`compile-mod` path:

- `src/reaver/profile-zone.rvr` wraps the direct op-83 `ZoneStart` and
  `ZoneEnd` primops;
- `src/reaver/foil-profile.rvr` deep-forces compiler phase boundaries while
  their zones are live;
- each benchmark process starts from a copy of the same clean, preloaded base
  snapshot;
- the final compiled result is deep-forced;
- output is scanned for `"ERROR"` independently of process status.

Chrome traces split a live zone into many begin/end segments at runtime
scheduling boundaries. The measurements below aggregate those segments by
logical PLAN thread and opaque zone handle. Raw traces were 245–503 MB, so
event count is not a call count.

Phase zones are nested because the compiler is lazy. For example, the lowering
zone forces materialization, which in turn forces elaboration. Inclusive phase
times must not be added together. Where useful, the tables report the
incremental time between nested phases.

## Fresh compilation results

### Three-run wall-clock gates

| Benchmark | Run 1 | Run 2 | Run 3 | Median |
| --- | ---: | ---: | ---: | ---: |
| Fresh `lain`, process wall | 21.99s | 24.28s | 22.25s | **22.25s** |
| Fresh `lain`, active module zone | 12.11s | 12.79s | 12.15s | **12.15s** |
| `lain` elaboration + WF | 6.37s | 6.75s | 6.37s | **6.37s** |
| Fresh `helmapp`, process wall | 27.98s | 30.35s | 30.00s | **30.00s** |
| Fresh `helmapp`, active module zone | 17.88s | 21.57s | 19.88s | **19.88s** |

No Foil `"ERROR"` was emitted in these runs.

### `lain` phase attribution

The median standalone `lain` profile is approximately:

| Work | Time | Interpretation |
| --- | ---: | --- |
| `lain` parse and split | 1.05s | Root module only |
| `lain` elaboration + final WF | 6.37s | Largest individual root phase |
| Const materialization after elaboration | 0.34s | Incremental, excluding nested elaboration |
| Lowering after materialization | 0.43s | Incremental, excluding nested work |
| `sept` module | 1.90s | Inclusive dependency module |
| `shrine` module | 1.74s | Inclusive dependency module |
| Complete `lain` active zone | 12.15s | Includes dependencies, merges, checks, and harness overhead |

Elaboration is still the largest optimization candidate inside `lain`, but the
old 41.95-second elaboration baseline is obsolete. Further semantic lattice
work is not justified by the current acceptance target alone.

### `helmapp` attribution

The median active `helmapp` build is dominated by its dependency cone:

| Module zone | Median inclusive time |
| --- | ---: |
| `helmapp` | **19.88s** |
| `helm` | 15.40s |
| `lain` within the `helmapp` build | 13.56s |
| `lainapp` after its shared imports hit the process-local cache | 3.90s |

The root `helmapp` module itself spends less than approximately 0.2 seconds in
parse, collision checks, elaboration, materialization, lowering, and direct
merge work. Optimizing `helmapp` declarations is not a material opportunity.

## Artifact and snapshot results

Artifact results are not yet three-run acceptance measurements. They are hard
single-run or diagnostic measurements and are marked accordingly.

| Measurement | Result | Confidence |
| --- | ---: | --- |
| Cold creation of the `helmapp` artifact closure | **56.8s wall** | One complete run |
| Fully forced resumed artifact compile | **69.9s wall** | One unprofiled complete run |
| Fully forced artifact outer zone | **63.1s active** | One profiled complete run |
| Cache-only warm/rebind path | **84.8s wall** | One complete run; internal hit/miss attribution still required |
| No-op process, pre-artifact snapshot | **16.85s wall** | One directional sample |
| No-op process, artifact-bearing snapshot | **22.47s wall** | One directional sample |

The two no-op samples suggest that the artifact-bearing snapshot adds about
5.6 seconds before useful cache work begins. This is not an acceptance result
until both snapshots have three controlled runs and their reachable sizes and
save times are measured.

The artifact compiler token is stable across snapshot resume: the stored token
and a freshly computed token compare `Equal`. Human-readable pin labels may
change between processes and must not be used as evidence of invalidation.

An attempted detailed artifact-hit trace was empty because Reaver served a
stale cached profiling module. That trace is invalid and contributes no timing
claim. The next artifact benchmark must expose an explicit hit/miss result from
code that is known to be loaded in the benchmark snapshot.

## Implementation checkpoint

The current worktree contains the intended Milestone 1 mechanisms:

- a phase-local type context with subject, type-environment generation,
  nominal expansion memo, and top-level nesting-pair memo;
- context-threaded expansion, nesting, join, meet, and module elaboration;
- operand-preserving join/meet fast paths;
- case-arm metadata that reuses scrutinee and pattern expansions;
- reverse-recovery shape and constructor/arity prefilters;
- native pinned per-module artifacts and requested public cache APIs;
- snapshot-backed cache warming and cached launcher entrypoints.

Earlier clean runs passed the Foil type, integration, and execution suites and
exercised artifact equality, runtime equality, diamond imports, mounted
imports, const-generic materialization, and invalidation cases. Those results
precede the final change that pins the nesting-cache key. The final key change
and the complete Forge, Buddy, and Helm suites remain unvalidated.

## Revised milestones

### Milestone A: freeze and validate the current semantic checkpoint

Do not add another type-system optimization until the current implementation
has a trustworthy correctness baseline.

#### Work

1. Re-run type, integration, and execution suites from a clean snapshot after
   the final pinned nesting-cache-key change.
2. Compare normal and profiled compilation for `lain` and `helmapp` using
   `Equal` subjects and representative executed values.
3. Run Forge, Buddy, Helm, HTTP, and launcher suites with an external
   `"ERROR"` scan and explicit timeouts.
4. Repeat the fresh three-run wall gates after semantic tests pass.
5. Record interrupted or timed-out suites as failures to validate, not passes.

#### Gate

- all semantic and runtime comparisons pass;
- no emitted `"ERROR"`;
- fresh `lain <= 30s` median wall;
- fresh `helmapp <= 55s` median wall, with `<= 50s` retained as the stretch
  gate.

The present timing data passes the performance portion only.

### Milestone B: make artifact behavior directly observable

Before changing cache representation, prove whether every module in a warm
`helmapp` closure is a hit and attribute all work on that path.

#### Required zones and counters

- cache normalization and its invalidation reason;
- source-byte read and comparison;
- direct-import metadata load;
- dependency artifact validation;
- explicit per-module hit or miss;
- merge and mount work;
- local delta replay;
- construction of legacy process-local cache entries;
- full result forcing;
- snapshot restore and save wall time in the shell driver.

The benchmark result must include module hit count, miss count, replayed entry
count, merged entry count, and artifact-cache binding size. A warm result is
invalid if any source compilation occurs silently.

#### Gate

- a second process reports a hit for every unchanged module in the `helmapp`
  closure;
- hit/miss counts agree with the source/import graph;
- cached and fresh subjects and executed results compare `Equal`;
- three no-op pre-artifact and artifact-bearing snapshot runs establish the
  restore/save baseline.

### Milestone C: make a hit avoid cumulative reconstruction work

The current artifact resolver recursively reconstructs imported subjects,
merges them into cumulative subjects, creates legacy cache entries, and then
replays the parent delta. That work can exceed fresh compilation even when
parsing and elaboration are skipped.

#### Work

1. Separate artifact graph validation from subject reconstruction. Validate
   source bytes, compiler/flags/initial-subject tokens, and ordered direct pins
   before building cumulative subjects.
2. On an all-hit closure, avoid building the legacy `compile-mod-go` cache.
   Construct it lazily only at the boundary of an actual descendant miss.
3. Replay ordered module-local deltas directly into the requested initial
   subject. Do not reconstruct every imported cumulative subject as an
   intermediate value.
4. Apply each unmounted module-local delta once in dependency order. Preserve
   merge/mount collision semantics; a module imported under distinct mount
   paths may require distinct contextual applications.
5. Split cache validation/warming from compiled-subject materialization. A
   cache-only warm should not reconstruct the root subject merely to return an
   unchanged cache value.
6. Skip rebinding and snapshot saving when validation finds no cache changes,
   if the Reaver launcher protocol permits this without runtime changes.

#### Gates

- fully materialized warm `helmapp <= 20s` median wall in a new process;
- cache-only unchanged warm is no more than 2 seconds above the matched no-op
  snapshot median;
- zero parse, elaboration, WF, materialization, and lowering calls on an
  all-hit closure;
- exact subject and runtime equality with a fresh build.

### Milestone D: control persistent snapshot size and save cost

Persistence is only useful if the cache does not make every Reaver process
materially slower to restore and save.

#### Work

1. Measure snapshot root size, reachable store bytes, restore wall time, and
   save wall time before and after each warmed module closure.
2. Confirm that the persistent binding contains only artifact-local data and
   no cumulative compiled subject or legacy cache.
3. Pin/share source bytes and repeated metadata deliberately rather than
   embedding avoidable copies in artifact bodies.
4. Keep one current artifact per module and verify that replacing a leaf does
   not keep the old reverse-dependency cone reachable from the current cache.
5. Avoid reserializing or rebinding an unchanged cache during launcher warmup.

#### Gates

- artifact-bearing no-op median is within 2 seconds of the matched pre-artifact
  snapshot median;
- unchanged warmup does not grow the reachable snapshot;
- changing one leaf retains only the current reverse dependency cone;
- malformed or incompatible cache data remains a miss or explicit error.

### Milestone E: remove cold artifact-build duplication

Cold artifact creation currently takes about 56.8 seconds versus a 30.0-second
median fresh source build. Artifact creation should add bookkeeping, not repeat
the compiler pipeline.

#### Work

1. Compile each dependency once and carry its already parsed import metadata,
   imported keys, local keys, and local delta forward.
2. Do not resolve the artifact import graph and then invoke a second root
   pipeline that reparses or remerges the same imports.
3. Derive declared keys from the local delta or elaboration result rather than
   rescanning the complete cumulative subject.
4. Attribute pinning and delta derivation separately; remove whole-subject
   comparisons from the cold hot path where local-key information is already
   available.
5. Preserve transactionality: refresh cache entries only after successful
   compilation and artifact construction.

#### Gate

- cold artifact refresh is at most 1.2 times the matched fresh source-build
  median;
- the refreshed artifact reconstructs an `Equal` subject in a second process;
- leaf changes rebuild only their reverse dependency cone.

With the current 30-second fresh median, the provisional cold-artifact gate is
36 seconds.

### Milestone F: revisit fresh compiler algorithms only from a new profile

The remaining 6.37-second `lain` elaboration is real, but it is no longer the
blocking acceptance failure.

Potential later work includes:

- a semantic decision on whether lattice operations may recover nominal
  identity by subject order;
- removing internal reverse recovery or adding a compatibility index;
- reusing well-formedness expansions from elaboration;
- local-key materialization and lowering;
- generic-instantiation memoization;
- separate `cgen:compile-expr` attribution.

Do not implement these solely to satisfy the already-passed fresh-build gate.
In particular, changing nominal recovery semantics is a language decision, not
a cache optimization.

### Milestone G: application startup after artifact replay is under control

The 2–5-second goal remains a startup/image target, not a cold Foil source-build
target. Measure it only after Milestones B–E make the artifact clock reliable.

The remaining startup work includes the RVR actor dependency graph, boot
mirroring, namespace seeding, and coordinator/listener startup. Candidate
architectures remain:

1. a precompiled application image;
2. a compiler service or shared immutable code cache for actors;
3. explicit build-time actor dependency bundles.

#### Gate

- precompiled image to listening: 2–5 seconds;
- warm incremental rebuild plus restart: 5–10 seconds;
- no missing compiler/code dependency is deferred into a child actor.

## Revised execution order

1. Complete the semantic checkpoint and rerun the fresh gates.
2. Add unambiguous artifact hit/miss and replay instrumentation.
3. Establish three-run no-op snapshot restore/save baselines.
4. Remove cumulative-subject and legacy-cache construction from all-hit paths.
5. Prevent unchanged warmups from rebinding or growing the snapshot.
6. Remove duplicate work from cold artifact creation.
7. Re-run cross-process equality, invalidation, launcher, and application
   suites.
8. Profile full application startup and choose an actor-code deployment model.
9. Return to type-lattice optimization only if a new fresh profile or a new
   product target justifies it.

The next decision point is now the artifact trace, not another elaborator
optimization. A cache change is successful only when a verified all-hit
`helmapp` process is faster than the current 30-second fresh source build and
the persistent snapshot does not erase that gain during restore or save.
