# Published evidence and demand policies

This optional library publishes ordinary Foil functions, Grove tree
transformations and native demand constructors. It has no activation, HTTP route, provider, watcher, index or
worker. Loading its source publishes declarations; it does not install work or
change another document. Nenex, flows and other applications can select its
published implementations through ordinary cells and overlays.

`references.foil` extracts typed references from an explicitly supplied tree.
`graph_references/edges scope tree` returns numbered records containing `source`
(the original scope), `holder` (the record inside that scope), `slot` and `target`.
The target retains its care, version and full path. A pinned scope produces
historical holder addresses selecting within that scope's snapshot, rather than
reusing its local case number as a child's case. The caller must supply a scope
that describes the supplied tree; this pure function cannot authenticate that
association. It neither reads nor widens that scope.

`graph_references/read scope result` preserves native `unknown` and `null`;
only a `known` tree becomes a known edge collection. A known empty tree is
therefore different from unavailable evidence. `prose_edges` is a separate,
opt-in bracketed-path parser. Text never silently becomes a native relationship.

The native `/r/<width>/<target...>` reader supplies incoming edge metadata from
the selected local store. It has no local care clock; freeze it with an epoch
reference. Its `holder` and `slot` fields are paths, and its `target` is the
complete asserted safe. Reading that set never reads holder contents. Missing
retained index metadata remains unavailable, including through a frozen reader.

`incoming_bindings scope incoming` deliberately turns a supplied reverse-lens
result into live x-care holder bindings for an ordinary context lens. It selects
only holder names beneath the explicit scope, deduplicates multiple edges from
one holder, and length-delimits aliases so a parent and its child do not collide.
This operation is pure; it does not subscribe, resolve references, or treat a
frozen set as a frozen reading of holder contents. Selecting live bindings is an
explicit policy choice. Capture the resulting context when retaining an attempt.
An authored native hand can apply these bindings with `native_work_ops/lens`.
When aliases disappear it emits an explicit native replacement for its owned
context; ordinary hand out-values are patches and cannot remove omitted slots.
That replacement retains the context's selected constructor and unrelated
annotations; only the hand's owned evidence aliases are reconciled.
The hand watches membership, while existing cell dependency expansion supplies
content subscriptions to context consumers. No second watcher registry is used.

`policy.foil` interprets explicit assertion records. Each record has a `subject`
safe, a `property` path, a `value`, a `source` safe and a numeric `accepted` marker.
The policy selects exactly marker `1`; other numbers are not accepted. `report`
first selects accepted assertions, then annotates conflicts between unequal
values for the same exact subject and property. The derived `conflicting` marker
is `0` or `1`. Every original assertion, source and qualifier survives; the
policy never picks a winning value or merges opposing qualifiers.

Reference equality includes care, version and the complete historical address.
`group_report subjects tree` is an explicit alternative: its caller supplies the
subjects to treat as one identity group for this projection. Original subjects
remain on the result records. It does not infer equivalence from slots named
`same`, prose, path spelling or namespace placement. The ordinary `report`
operation does not perform that grouping.

The Grove publication at `/gov/graph` provides a one-level `claims` norm for
text-valued assertions, plus `accepted`, `conflicts`, and `report` transformations.
`report` composes the selected `accepted/run` and `conflicts/run` implementations
within one published law. Their input/output norms use existing native values.
The general Foil functions also accept non-text values; the Grove example
deliberately chooses a narrower, inspectable contract.

For example, supply two accepted records about the same supplier's delivery
period, one saying “two days” and the other “five days”, with distinct source
references and reasons. The composed report retains both records and marks both
conflicting. A third rejected assertion stays in the original evidence but is
excluded from this report. Selecting another implementation is ordinary explicit
publication/binding, not a string dispatched by the current kernel. A captured
cell keeps its selected implementation while another cell can select a later
publication. Publishing this library does not update retained cells by itself.

The reference and assertion operations above are eager supplied-tree transformations. Reference extraction visits the
supplied records and slots once. Conflict annotation groups assertions in an
invocation-local native `axal`, keeping a representative value and disagreement
bit per exact subject/property key. A second pass annotates the original records.
Keys include care, version and length-delimited complete subject/property paths;
historical addresses cannot collapse into current names. Explicit identity groups
use property keys after selecting their explicitly supplied members. These trees
are transient computation values, not persistent indexes or watch registrations.
Work scales with input size, key traversal and value equality cost rather than
all assertion pairs; long keys and large values still cost work. Selecting a
virtual child does not promise selective evaluation of this whole-tree report.
There is no authority-wide reverse scan, implicit identity closure, navigation
layout, complete-component claim or traversal budget in these policies.

`demand.foil` additionally supplies `children_card` and `gather_card`, ordinary
records containing native `woven` constructors. Publish a chosen record at an
ordinary definition address and bind a cell's `/sys/weft` to that record's pinned
x-care reference. `children` grafts its explicit tack; `gather` places explicit
secondary safe references beneath their authored slot names. Neither invents
relationships from prose or names. Constructor publication does not rewrite
existing cell bindings.

These constructors return the existing `view_plan` protocol. Selecting one
placement reads that branch; requesting names does not read member contents.
The native reader resolves reads and grafts, records actual observations, and
uses ordinary dependencies. Graph policy owns placement and missing-member
presentation. Native `unknown` is marked `unresolved`; native `null` is marked
`absent`. These states depend on the requested care: an exact x-care read of a
culled record returns `null`, while a z-care subtree read whose root is no longer
a node remains `unknown`. Neither becomes an apparently current empty evidence
record. A pinned subtree's child is selected inside that snapshot, never by
borrowing its local case as a child's case.

The evaluator contains no graph-name registry or graph-specific provenance
rewriting. Its constructor contracts are retained in `sys/demand`, independently of the
unchanged `sys/view` cell contracts. Changing that native implementation is a core runtime update;
publishing this optional policy cannot replace the reader in a saved service.
The supplied collection and assertion policies do not claim parity with every
connected-world navigation or equivalence policy previously supplied in main.

Tests live in `tests/` and run through the existing mounted test infrastructure.
Publication tests separately exercise actual compiled Grove laws and retained
bindings; direct function tests alone cannot establish publication fidelity.

Run `python3 extras/mounts/graph/check.py` from the repository, with `WISP` set
to the native runtime (or available on `PATH`). `TEST_TEMPLATE` may select an
existing compiler fixture. The runner stages disposable sources and snapshots
under `.check`; it never attaches to an existing world. It includes the shared
flow test dependencies only in the test fixture, not the graph mount's runtime
dependencies.

The authored-flow fixture supplies the report through an ordinary cell, then
uses the existing revision operation, controlled provider, maintenance hand,
persistent hole and Nenex writer. Conflicting evidence suspends work; a claim
edit resumes it while preserving the old attempt and report capture. This is a
native lifecycle test, not a live Codex or browser demonstration. The separate
publication fixture compiles the real Grove source, publishes a changed law,
and checks retained versus explicitly updated bindings.
The same fixture now selects its report inputs from a native reverse lens through
the shared work context. A new incoming claim reopens the retained work; retargeting
it removes its alias, and later edits to that released holder cannot retrigger the
context or completed controller. The input scope excludes the flow's own work.
Returning to an earlier supported report can reuse its retained result. The same
publication settles the reopened hole, releases obsolete failed jobs and preserves the
failed attempt. A later return to rejected evidence allocates a new head instead
of reviving that old failure.
Its controlled provider inspects the actual frozen assertion report. Matching a
readiness phrase anywhere in the prompt would incorrectly accept a previous
draft's prose as evidence for a newly conflicting set.

## Cost and selection proof

`graph-cost-tests.rvr` is a native test module using the existing bootstrap and
test fixture staging. It warms the transformation laws on distinct input, then
uses native `Now` nanosecond timestamps and `DeepSeq` to force each result before
closing its measurement. Compilation and input construction are excluded.
It prints `GRAPH-COST` rows for 32, 128 and 512 supplied assertions: the actual
input/output record counts and elapsed nanoseconds for typed-edge extraction and
conflict reporting. Each broad input is compared with an explicitly selected
one-record subtree. There are two typed references per input assertion.

Every assertion in this fixture has the same value. The former pairwise baseline
examined n² pairs, including self-pairs; a recorded warm run took 27.82 seconds
for 512 assertions. This finding motivated replacing that loop, without adding a
demand evaluator. `pairwise_report` remains only in the test fixture as a small
conformance oracle. The grouped implementation performs two group lookups per
valid record and n-1 value comparisons for this single-group, equal-value input.
Logged operation counts are derived from the fixture and algorithm, not runtime
instrumentation. Fresh timings report the grouped implementation; there is no
timing threshold and no claim that one machine's result predicts general latency.

The baseline evidence is retained in
`.check/overlay-refactor/publication1/reaver/out.log`, with its frozen fixture
sources alongside it. That run measured 117.58 ms, 1,744.12 ms and 27,821.65 ms
for 32, 128 and 512 assertion reports. It also exposed repeated output-tree
counting during reference extraction (4,392.86 ms for 512 records / 1,024 edges).
Extraction now carries its next output index in the existing local fold instead
of recounting all previous edges. Both changes remove identified repeated work;
they add no retained state or demand-driven execution.

A subsequent warm run with the grouped implementation measured:

| Supplied assertions | Conflict report | Typed-reference extraction |
| --- | ---: | ---: |
| 32 | 16.93 ms | 19.84 ms |
| 128 | 89.60 ms | 105.65 ms |
| 512 | 438.04 ms | 477.02 ms |

The selected one-record report took 0.26–0.59 ms. These are single-run
observations on the development machine while other validation was running,
not latency guarantees. The complete log is
`.check/graph-qlvi9fbn/publication/out.log`. These measurements come from the
successful cost suite; publication correctness is validated separately.

These transformations issue zero namespace reads: they only consume supplied
trees. Their input record counts must not be presented as a trace of dynamically
discovered reads. Narrowing is performed before the timed transformation, and
the benchmark does not measure namespace retrieval or the cost of selecting that
input. The native `tests/queries` suite separately establishes that binding a
cell directly to a narrow tack avoids the sibling dependency; selecting a child
inside an already supplied broad tree still receives the broad input. A safe
found in supplied data remains a reference, not an implicit reader effect.
Declared secondary inputs are resolved eagerly. A caller can explicitly rebind
an existing cell to a selected source using ordinary writes, but this is a
deliberate binding update, not a hidden read-time evaluator or dynamic traversal.
