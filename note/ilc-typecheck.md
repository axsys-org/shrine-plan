# Differentiating the production Foil expression checker

`ilc-typecheck.rvr` sends the existing `foil-new-elab:elab-value` through the
generic PLAN ILC transformation. Its input is `[NewCompiler, SurfaceAST]` and
its output is the complete `[updated-NewCompiler, TC_IR]` pair. There is no
checker-specific derivative, dependency graph, module cache or alternate
typechecker implementation.

```scheme
(define df (ilc:derive-with structural:rules tc:check))
(define dy (df old-input input-delta))
(define new-output (ilc:apply-change old-output dy))
;; new-output == tc:check (ilc:apply-change old-input input-delta)
```

This is a different experiment from `ilc-compiler.rvr`: that earlier module
cache supplied a handwritten compiler derivative. Here the checker laws
themselves are transformed by `ilc.rvr`, using the law inspection/construction
facilities from `pe.rvr`. The normal production compiler remains unchanged.

## Generic data rules

`ilc-structural.rvr` supplies sparse, fixed-shape product changes and derivatives
for projection, row operations, primitives, lazy conditionals and collections.
For example, `at-path [1 2 0 1] (replace-change 42)` changes the left literal of
an application in the input's AST field. A projection of an untouched field
returns zero without traversing the changed subtree. Shape-changing edits
fall back to replacement.

The `map` and `gen` rules differentiate their callbacks using generic ILC too.
They do not recognize compiler functions. Derivative/rule metadata is passed
to `Memo`, but profiling below found those calls uncacheable on this runtime;
typechecking inputs and outputs have no explicit memo table. Lazy
branches and overwritten fields have demand-preservation tests. The rule
interface is trusted, and the tests are not a proof for every PLAN program.

## Evidence and scope

`ilc-typecheck-tests.rvr` compares complete outputs for literal changes,
applications, changed callees, annotated expressions, lambdas and conditionals.
It also checks an unchanged reference under a changed binding environment and
exact type-error diagnostics for an invalid application. Both the derivative
with no rules and the derivative with generic structural rules are checked.
`ilc-typecheck-demo.rvr` walks through two consecutive sparse updates.

`ilc-audit.rvr` is an optional dispatcher that records which laws the generated
derivative enters, which registered rules it uses and where it falls back to
opaque recomputation. The audit propagates through collection callbacks. The
benchmark requires observed transformation of both `elab-value-go` and
`subtype-go`; merely differentiating the outer wrapper would fail this check.
This instrumentation runs separately, outside all timed regions.

The experiment covers the production expression-checking entry point and the
paths exercised by these tests. It does not claim coverage of every checker
feature, whole-module elaboration, incremental parsing, declaration scheduling,
lowering, publication preparation or the entire compiler. Surface-AST changes
are supplied explicitly; there is no text-to-AST incremental parser here.

## Benchmark protocol

```sh
WISP=/path/to/wisp x/check pe-tests ilc-tests ilc-typecheck-tests ilc-compiler-tests ilc-watch-tests
WISP=/path/to/wisp x/bench-ilc-typecheck --samples 5 --updates 8 --depths 0,1,3
```

The workload is a balanced tree of actual `add` applications. Each update
changes its leftmost literal to a fresh number. The input compiler environment
stays fixed, while the updated input and full output are carried to the next
edit. The full baseline checks the updated expression from scratch. Raw ILC
has an empty rule table; structural ILC has only the generic rules above.
The harness now also measures staged ILC with the same generic rules and
staged derivatives for collection callbacks.

In-VM timing includes delta application and full checking, or generated
derivative execution and output update. The entire output pair is deeply
forced. Fixture creation, initial checking, initial derivative construction/warming and
exact equality validation are outside the timers. Mode order reverses on
alternate samples. Each mode/sample starts from the same original state;
there are eight successive edits per sample, and reported times are medians
of sample time divided by eight. These are small expressions in the test
compiler environment, not a production-project throughput measurement.

The harness freezes sources and saves their hashes, runtime identity, raw
timings, audit counts and logs under `.check/ilc-typecheck-*`.

## Measured result

On macOS 26.3 arm64 with the local `enki-pgo-0.1.0` Wisp runtime, five samples
of eight fresh edits gave the following median milliseconds per edit:

| Literal leaves | Full checker | Raw ILC | Structural ILC | Structural / full |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 0.0079 | 1.0408 | 0.7215 | 91.62x |
| 2 | 0.0776 | 49.5826 | 44.2792 | 570.43x |
| 8 | 0.5052 | 399.5007 | 347.2301 | 687.24x |

The derivative is correct on these cases but dramatically slower. The
single-literal baseline is especially short/noisy; the raw report includes
all samples and their ranges. Structural rules improve on raw ILC here but
do not approach the ordinary checker.

The separate one-application audit recorded 792 transformed-law dispatches,
1,746 generic-rule dispatches and two opaque fallbacks. These are invocation
counts, not distinct functions. Observed laws include `elab-value` (1),
`elab-value-go` (4), `check-value` (2), `ensure-subtype` (2),
`consistent-subtype` (2), `subtype-with-cache` (2) and `subtype-go` (2).
The two opaque calls occur within `Unpin`; there were no changed-function
fallbacks. Eliminating opaque fallback alone therefore cannot explain away
this slowdown. The relative costs of dispatch, allocations and primal
recomputation have not been individually profiled.

Raw report: `.check/ilc-typecheck-hf1lhxge/results.json`; its sibling `out.log`
contains the audit and `src/` contains the measured source snapshot.

Validation passed `pe-tests`, `ilc-tests`, `ilc-typecheck-tests`,
`ilc-compiler-tests` and `ilc-watch-tests` (including Merkle watcher tests).

## Staged dispatch

`ilc:derive-staged-with` has the same old-arguments/argument-changes interface
as `derive-with`, but resolves fixed calls while constructing derivative laws:

```scheme
(define staged-rules (structural:rules-with ilc:derive-staged-with))
(define df (ilc:derive-staged-with staged-rules tc:check))
(define next-output (ilc:apply-change old-output (df old-input input-delta)))
```

The transform inspects syntactic application spines using the law predicates
and quoting facilities from `pe.rvr`. Literal heads and original self are
known unchanged. At saturation, registered rules become direct calls;
ordinary laws become direct calls to shared generated derivatives. Recursive
self calls target the generated law's self slot, while escaping/primal self
values retain the original function identity and arity. Literal PAP captures
are passed explicitly with zero changes. PAP-specific rules retain precedence
over rules for the underlying head.

Unsaturated known applications construct APP changes directly. Unknown heads,
let-bound functions, and calls through the result of a saturated application
still use runtime dispatch. That dispatcher generates staged derivatives when
it discovers a law. Changed callees preserve the existing fallback, including
changes of arity. Newly constructed partial applications retain their APP
changes even when the components are zero; staging does not normalize those
changes and alter runtime rule selection.

There is no source-call evaluation during static-head discovery, recursive
inlining, or new broad constant-folding policy. Known opaque primitives emit
direct replacement computations; staging does not eliminate the primitive
work. The transform requests metadata sharing through `Memo`, which does not
cache these calls on the measured runtime (see the profiling findings below).
No primal intermediate
results or execution traces are retained, and the ordinary dispatcher is
unchanged.

`ilc-staged-tests.rvr` installs a dispatcher that throws to verify that fixed
rule calls, nested laws, literal PAPs and direct recursion do not dispatch at
runtime. Separate cases cover dynamic fallback, arity changes, forward and
cyclic lets, escaped self, overapplication, custom rules, and unused errors.
The structural-rule and production-checker suites run in both modes.

The staged audit reports only remaining runtime dispatch events. It does not
count direct generated calls; both audits exclude PAP-peeling steps. A lower
count is evidence of dispatch removal, not of eliminated typechecking work.

With the same runtime/host, five samples of eight successive edits produced
these median milliseconds per edit (all modes rerun together):

| Literal leaves | Full checker | Raw ILC | Structural ILC | Staged structural ILC | Structural / staged |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 0.0070 | 0.9055 | 0.6082 | 0.1802 | 3.37x |
| 2 | 0.0831 | 50.3396 | 45.4579 | 31.7492 | 1.43x |
| 8 | 0.5178 | 413.0126 | 345.0695 | 246.4829 | 1.40x |

Staging reduces the eight-literal update time by about 29%, but still takes
476 times as long as full checking. It is a useful dispatch optimization,
not yet a competitive incremental checker. These are warmed update timings;
generation/first-use latency and retained metadata memory were not measured.

On the separately audited one-application edit, non-peeling runtime dispatch
events fell from 2,540 (792 law, 1,746 rule, 2 opaque) to 120 (all law), a 95.3%
reduction. Fixed rule/opaque calls still execute directly, outside the staged
dispatcher. Both audited outputs exactly matched full checking.

Raw report: `.check/ilc-typecheck-ivgym1cl/results.json`, with frozen source,
individual samples and both dispatch traces alongside it. The baseline and
staged modes share the same generic rules; `map`/`gen` callback derivatives
use their corresponding transform. There are no checker-specific rules or
retained primal computations in either mode.

## Retaining intermediate computations

`ilc-retained.rvr` is a separate, experimental cache-transfer transform. It
generates initialization and update laws from the same production checker:

```scheme
(#bind cache (#module ilc-retained))
(define rules (structural:rules-with ilc:derive-staged-with))
(define program (cache:prepare rules tc:check))
(define state (cache:start program [compiler ast]))
(define checked (cache:value state))

(define result (cache:advance state input-delta))
(define output-delta (_0 result))
(define next-state (_1 result))
;; cache:value(next-state) == tc:check(updated-input)
;; apply-change(checked, output-delta) == cache:value(next-state)

(define compacted (cache:reset next-state))
```

The public entry point accepts unary functions; multiple inputs can be packed
into a row. States carry the program, current input, and a lazy cache node.
Every node contains a result and internal trace metadata. Generated law
initializers retain let bindings, nested application children and nested law
caches. Generated updates read those old nodes, propagate argument changes,
and return both an output delta and a new cache. Fixed calls use generated
initialization/update functions directly; dynamic calls resolve their callee
at runtime and rebuild an incompatible inner cache when necessary.

This retains primal intermediate computations, rather than just memoizing
generated code or storing the previous final output. A targeted white-box
test seeds a sentinel into an internal cache and verifies that update loads
that saved value. Separate equivalence tests use unmodified, valid states.
No checker-specific derivative or module dependency cache is involved.

Registered derivative rules remain opaque boundaries. In particular, the
current generic `map`/`gen` rules use staged callback derivatives; this version
does not retain intermediate computations inside those callbacks. Retention
also does not yet prune arbitrary unchanged law calls: eagerly inspecting
all argument deltas could force an unused error. It still traverses demanded
update nodes even when many of their values can be shared.

Only demand `cache:value state`. Do not deeply force, print or compare an
entire state: its trace intentionally includes suspended, possibly erroneous
or recursive computations from unselected branches. `advance` is lazy too;
a caller should demand the required output before committing the new state.
A failed edit leaves the last accepted state available for a corrected edit.

`reset` initializes a fresh cache from the current input. Dropping previous
states then permits old cache histories to be collected. This is an explicit
reset operation, not an automatic byte limit or a proven bounded-memory
policy. Lazy update chains and retained metadata can still increase memory
use between resets. No runtime heap instrumentation was added.

Tests cover successive edits, cached intermediate loads, sparse edits,
forward/recursive lets, cyclic data observed lazily, escaped self, dynamic
callee/arity changes, unused errors, reset equivalence, changed environments,
and production expression-checking results and output deltas.

Parsed-to-parsed invalid edits also match the full checker's diagnostics.
An expanded test exposed an existing ILC limitation: changing an unlocated
fixture AST into a located, invalid parsed AST can produce a different
diagnostic from full checking. Both staged and retained ILC report an invalid
TC annotation in the tested case, while full checking reports a lambda goal
arity error. Resetting the cache does not fix it; initialization without an
update produces the full-check diagnostic. This is recorded as a limitation
of the existing derivative/rule behavior, not a claim of universal diagnostic
equivalence. Both update modes still reject the invalid input.

Reproduce the retained comparison with:

```sh
WISP=/path/to/wisp x/check pe-tests ilc-tests ilc-typecheck-tests ilc-retained-tests
WISP=/path/to/wisp x/bench-ilc-retained --samples 5 --updates 8 --depths 0,1,3
```

The workload and output forcing match the staged benchmark. Each trial starts
from the same initial state and carries its updated cache through successive
fresh literal edits. Complete outputs and output deltas are validated outside
timing. Validation/reset run in a separate function returning only a Boolean,
so validation-only cache histories do not remain in the timed runner's scope.
All modes run in the same process with warmed metadata; this is not an
isolated per-mode heap or cold-start comparison.

The harness also records one initialization and reset observation per size,
forcing the output rather than the trace. Retained initialization includes
code generation demanded on first use; later sizes share generated metadata.
Full initialization runs first. Those single observations must not be treated
as repeated cold-process medians.

Five samples of eight successive edits on the same macOS arm64/Wisp runtime
gave these median milliseconds per edit:

| Literal leaves | Full checker | Staged ILC | Retained ILC | Retained / staged |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 0.0055 | 0.1776 | 0.2289 | 1.29x |
| 2 | 0.0765 | 35.5746 | 70.6655 | 1.99x |
| 8 | 0.4941 | 253.4285 | 600.5225 | 2.37x |

The retained version loses on this workload. The eight-literal update is
about 1,215 times slower than full checking. Retaining intermediate values
is working, but the implementation does not yet make that reuse economical.
These results do not isolate the costs of allocations, collection, cache
lookups, change propagation or callback derivatives.

Single initialization/reset observations, in milliseconds:

| Literal leaves | Full initialization | Retained initialization | Reset after 8 edits |
| ---: | ---: | ---: | ---: |
| 1 | 0.683 | 4.141 | 0.134 |
| 2 | 1.667 | 34.496 | 37.903 |
| 8 | 0.549 | 296.367 | 15517.950 |

The large reset cost is a material limitation. The old history remains
available while the reset output is demanded and verified. Although reset
produces a fresh cache, it is not evidence of cheap compaction or bounded
retained memory. Heap/GC costs were not separately measured.

Raw report: `.check/ilc-retained-9yeonfo1/results.json`, with frozen sources,
the input script, individual samples and logs alongside it. The measured
implementation passed `pe-tests`, `ilc-tests`, `ilc-typecheck-tests` and
`ilc-retained-tests`.

## Profiling the retained implementation

`x/profile-ilc-retained` freezes sources and records observable-value phase
timings. It can export runtime zones, sample its own Wisp process with macOS
`sample`, or instrument call/cache/code-construction counts in the disposable
source copy. It does not modify the production transform for instrumentation.

The eight-literal/eight-edit benchmark was reproduced with only phase-start
markers added: reset took **17.316 s**, and the retained update batch took
**5.197 s** (about 650 ms/edit). This agrees with the earlier slow reset and
update timings. Native sampling was enabled only during the retained batch.

Native stack samples distinguish the two costs:

| Sampled main-thread stack category | Reset window | Retained update window |
| --- | ---: | ---: |
| Allocation slow path / copying GC | 2240/2240 (100%) | 616/2240 (27.5%) |
| Direct PLAN evaluator execution | 0/2240 | 1256/2240 (56.1%) |
| Other execution, including JIT/native operations | 0/2240 | 368/2240 (16.4%) |

Each sample window lasted three seconds. These are fractions of sampled
main-thread stacks, not whole-run CPU accounting; idle helper threads are
excluded. Reset samples were dominated by `pl_gc_reserve_slow`,
`pl_gc_collect`, `pl_collect_into`, and copying/memory-management underneath
them. The process footprint was about 925 MB during that reset sample and
2 GB during the separate update sample. Footprint includes runtime/store and
semispace overhead; it is not a measurement of live cache bytes.

The explicit-zone run made reset slower (64.183 s), illustrating how sensitive
this allocation cliff is to instrumentation and live roots. Within that
reset, all native store/compiler spans together occupied only **0.081 ms**,
with one `store.compile.law` span. Native bytecode compilation or store I/O
does not explain that reset pause.

Liveness experiments on the same fixture isolate its cause:

| Reset preparation | Reset time |
| --- | ---: |
| Original benchmark scopes, phase markers only | 17.316 s |
| Profiling scopes; explicitly force current input, retain old history | 54.782 s |
| Return only program/input/output from setup, then rebuild outside its scope | 0.406 s |

Forcing the current input in the middle experiment took **0.012 ms**. The
pause is not deferred input evaluation. The old cache history is still rooted
while the new cache is allocated in the slow cases; releasing those roots
before rebuilding avoids the pathological pause. The wrappers deliberately
change liveness, so these single observations are diagnostic ablations, not
an optimized production benchmark or a universal speedup ratio.

The detached experiment fully normalizes this valid fixture's input/output.
That must **not** be copied blindly into the general API: arbitrary callers
can have unused erroneous inputs, and forcing those would violate laziness.
A production solution needs a demand-preserving detach/rebuild boundary or
smaller retained state, not indiscriminate `DeepSeq` of inputs or traces.

There is also an important correction to the earlier metadata-cache claim.
The native `Memo` optimization requires canonical hashed pin arguments and
caches only small-natural results. Calls such as `(Memo (compile rules) f)`
pass a partial application as the function and return a program pair, so they
run as ordinary applications. Inspection of the measured binary's `op_memo`
guard agrees with the local runtime source. Existing references inside one
generated body can be shared, but this does not provide a cross-call program
cache.

Separate counting runs confirm repeated construction after warmup. Counters
are not timings: printing changes execution cost, so native samples and wall
measurements above used uninstrumented transform code. The native evaluator
samples cannot by themselves separate checker execution from PLAN-level code
construction; no percentage of evaluator time is attributed to either here.

For the eight-literal fixture, an update-only run with two edits counted:

| Phase | `compile` entries | Initializer laws constructed | Transfer laws constructed | Call-cache updates |
| --- | ---: | ---: | ---: | ---: |
| Initial retained check | 15,944 | 4,045 | 0 | 0 |
| First edit | 15,459 | 153 | 4,058 | 17,678 |
| Second edit | 14,929 | 0 | 4,052 | 17,678 |
| Reset after two edits | 16,081 | 4,059 | 0 | 0 |

These are construction/invocation counts, not distinct laws or live nodes.
The second edit still constructs 4,052 transfer laws, including 546 each for
`type-is-tag?` and `type-node-tag`, 221 for `drop`, and 158 for `cmp-total-in`.
The initial check and reset initialize 17,587 and 17,726 call-cache nodes,
respectively. Retaining intermediates currently introduces substantial
generic bookkeeping even for this small expression.

Reproduction commands (native sampling may require OS profiling permission):

```sh
WISP=/path/to/wisp x/profile-ilc-retained --variant benchmark --no-trace --native-sample --sample-phase timed.retained
WISP=/path/to/wisp x/profile-ilc-retained --native-sample
WISP=/path/to/wisp x/profile-ilc-retained --variant input-forced --no-trace
WISP=/path/to/wisp x/profile-ilc-retained --variant detached --no-trace
WISP=/path/to/wisp x/profile-ilc-retained --variant updates-only --updates 2 --no-trace --counts
```

Evidence directories under `.check/`:

- `profile-ilc-retained-qzcdwfbr`: original benchmark scopes, update stack sample.
- `profile-ilc-retained-ruc7tk81`: reset stack sample, zone trace and `trace-summary.json`.
- `profile-ilc-retained-52vcm59i`: input forcing with history retained.
- `profile-ilc-retained-uo3y2j3_`: detached rebuild.
- `profile-ilc-retained-j_av8_qv`: two-edit construction/call counts.

The next fixes should establish a real generated-program cache keyed by bare
law and rule configuration, reduce the retained roots alive during reset,
and reduce per-edit cache traversal/allocation. The local runtime's collector
growth policy also merits attention: it grows only when collection cannot
satisfy the immediate allocation, which can leave very little headroom and
permit repeated copies of a nearly full heap. That policy is consistent with
the sampled allocation/GC cliff; heap occupancy and collection counts were
not directly instrumented in this binary.

## What remains

Semantic differentiation alone does not ensure an efficient incremental
checker. The original and staged modes may reconstruct old intermediate
values; the retained mode trades that work for storing and updating a lazy
trace. All three still allocate changes and perform some runtime dispatch.
The structural rules express local changes without automatically eliminating
the work of traversing unaffected parts of a computation.

Known derivative calls and primitive rules now use direct residual code, and
the retained prototype stores primal intermediates. Further work should
reduce cache metadata/transfer overhead, retain collection callback caches,
and skip unaffected subcomputations using demand-safe evidence. These are
improvements to generic ILC, not a handwritten checker dependency cache.
A blanket eager scan of every
argument delta for zero is unsafe: it can force an unused error/branch that
the original lazy program never demanded.
