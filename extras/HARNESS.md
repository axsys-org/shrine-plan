# Harness, documents, and applications

The harness is the shared native work protocol plus the procedures and provider
adapters that use it. It is not a second world, a Python runner, or a replacement
for Nenex. Nenex is a document application in that world. The handbook is an
authored procedure and its maintained documents, not another application runtime.

## Ownership

| Location | Owns | Does not own |
| --- | --- | --- |
| `src/foil` and `src/reaver` | Namespace reads/writes, admission, reactions, cells/views, filesystem I/O, publication, Semidoc and native persistence | Application-specific work policies and handbook recipes |
| `mounts/codecs` | Shared Grove value codecs and explicit retention of the core Semidoc artifact used by Flows and Nenex | Another Semidoc implementation or automatic type matching |
| `mounts/cooperate/work*.foil` (`native_work`, `native_work_ops`) | Captures, activities, events, provider dispatch receipts/outcomes, context lenses and persistent holes | Document structure, source polling, provider transport |
| `mounts/cooperate/main*.foil`, `answer*.foil` | Investigation and question-answering policies over native work | Another attempt lifecycle or private work store |
| `mounts/flows/flow*.foil`, `runtime*.foil` | Semidoc procedure compilation, pinned operation selection, evaluation, preview and guarded commit | Browser state or provider processes |
| `mounts/flows/maintenance*.foil`, `request_ops.foil` | Reactive procedure maintenance and generic suspended requests using native work | Polling, a work queue, or a second retry receipt |
| `mounts/flows/work*.foil`, document operations in `operations.foil` | Document-revision policy: briefs, drafts, accepted revisions and evidence | A second provider lifecycle; arbitrary executable content generation |
| `mounts/flows/sources*.foil` | Evidence adapters and live source bindings using existing filesystem ownership | Filesystem actors, Nenex pages, example installation |
| `mounts/flows/web*.foil`, `mounts/flow-web` | HTTP work contracts and the optional native transport foot | Automatic research, polling or application-specific crawling policy |
| `mounts/codex` | Native provider hand and app-server transport/process lifetime | Deciding when a flow runs or when a domain result is acceptable |
| `mounts/graph` | Published evidence projections, demanded placements and explicit conflict policy | The native read interpreter, a graph store, source polling or a work lifecycle |
| `mounts/nenex` | Semidoc page ownership, source/Goo editing, reader, question/block context and page-tool contributions | The work lifecycle or a flow evaluator |
| `mounts/explorer` | Shared Goo presentation, declared action reflection, document/tree hosts and namespace browsing | Agent scheduling or an MCP transport dependency for rendering |
| `mounts/mcp` | Direct native read, write, history and admitted-operation transport | A private agent loop, work queue or browser application |
| `mounts/inspector` | Optional read-only `/live` records, cells, overlays and history over MCP | Chat, task execution, raw writes, cursor records or workspace binding |
| `mounts/flow-authoring` | Flow/Nenex integration: source authoring, page evidence, guarded writer and declared Goo controls | The generic command catalogue or filesystem-source lifecycle |
| `mounts/conversation` | Conversation turn bindings, scoped graph context and inline Nenex projections | A message-body model, provider loop, attempt lifecycle or store |
| `mounts/flows/install.foil` | Native flow command/law registration and retained-contract checks | Nenex routes or example catalogue |
| `mounts/flow-examples/examples.foil`, `examples/`, `examples.json` | Optional authored recipes and their setup data | Runtime policy for all flows |
| `flow_library` in `mounts/flow-examples/examples.foil` | Pure native-capture and format adapters for the learning, atlas and ingestion recipes, under the existing examples publisher | Work ownership, a parser implementation, instruction adoption or scheduling |
| `tests/fixtures/block-document` | Goo regression fixture with its own small bounded block model | Nenex's document representation |

`flows` is independently installable with Cooperate and its native dependencies.
`flow-authoring` adds Nenex, the document writer and declared Goo controls;
`flow-web` adds the HTTP provider foot. `conversation` arranges native Nenex
messages and shared flow occurrences as a chat/composer surface. `flow-examples`
selects these integrations for its authored recipes.
Persistent contract artifacts stay owned by `flows`, including the small document
and web contracts. Logical module names and public operation addresses stay the
same. Splitting source ownership does not move or convert retained world data.

Semidoc's artifact is explicitly pinned by `codecs`, a common dependency of
Cooperate/Flows and Web/Nenex. Its `snode` and `sval` types cross those boundaries.
Compiling a separate copy in each branch of that dependency graph creates
different contracts, even when the source bytes match. Validate this boundary
with separately published mounts; a combined test compilation cannot establish
that their imported type identities agree. Existing worlds retain their selected
artifacts; changing a mount manifest alone is not a historical-data conversion.

The document adapter supplies a captured draft writer using the existing writer
contract. Draft completion calls that selected materializer; generic maintenance
no longer imports Nenex's document implementation. Final publication still uses
its separately captured destination writer. A document form without its required
draft writer is refused, rather than silently selecting current behavior.

Each mount activates its own behavior records. A flow refresh updates the flow
commands and its Nenex contribution; it cannot reinstall an older captured
Cooperate hand or Nenex document form. Dependency installation remains with the
existing mount ordering and each dependency's own activation.

The flat source bags are a deliberate Eden publication boundary. Keep logical
responsibilities clear inside them instead of adding a new directory loader,
umbrella service, or compatibility mount. Runtime modules stay flat; examples and
test assets can live in subdirectories and are staged by the existing host/gate.
Flow fixtures remain grouped under `flows/tests/`; the execution and integration
manifests select the relevant logical suites without changing their names.
`flow_test_world` and `flow_request_fixture` provide reusable disposable setup
without importing executable flow suites. Setup admissions fail visibly; negative
tests explicitly require rejection and an unchanged world. Pure graph reference
checks import the production types they use rather than the cell test suites.

## How the pieces meet

An authored Semidoc definition selects operations or published child flows and binds
named inputs. Publishing captures those laws and selected child definitions.
Cells read evidence and expose the computation. The maintenance
hand reacts to dependency changes. A suspended step opens native work and a hole;
a provider returns a retained outcome. Domain acceptance checks freshness and shape.
The chosen writer admits changes through the same namespace admission as other tools.
The policy that permits adopting an unwritten document containing only its owned
holes lives with that Nenex writer, not in the shared native work module.
Nenex exposes those records, drafts and commands to a person.

A [conversation](mounts/conversation/README.md) uses that same boundary: its
authored response is a Nenex document projected inline. The conversation retains
message order and explicitly selected context; an ordinary published flow owns
the response work. Source/Goo edits address the same response document, and the
conversation wiki is an ordinary named Nenex descendant.

Nenex uses the shared Goo document and tree surface. The separately selected
`inspector` mount retains `/live` for read-only inspection of the same world; its
assets and HTTP route belong there, rather than to the document host. It depends
on `explorer` and `mcp`, while ordinary Goo rendering does not force MCP. The
existing `/goo-inspector` application is a declared Goo namespace view and remains
separate from that low-level history/cell inspector. Direct MCP operations remain
available to external agents without either interface. Agent actions and flow
invocations use native work, selected hands and declared controls; the retired
`/live` chat, queue, workspace-mutation and port 8311 paths are not harness entrypoints.

A Nenex page can select a published flow into an ordinary captured cell and embed
an independently bound occurrence. The occurrence is the existing maintenance
controller under the page's named `work` child. A Semidoc `doc/embed` reference
projects that controller's work, cells and controls; it does not own the activity.
Removing the reference leaves the activity and history intact. Explicit detach
releases its claim and subscriptions. Selected occurrences retain the exact
definition publication while their input bindings remain live; existing live
maintenance attachments continue to follow publication.

The controller's existing crew selects current requests, workers, guards and live
owned hole heads. Retained attempts remain inspectable without becoming dispatch
candidates. Replacing work or detaching releases obsolete subscriptions; it retains
captures, failed outcomes and history. A provider outcome must still pass the
selected domain's acceptance policy. See the [native work lifecycle](mounts/flows/README.md#one-native-work-lifecycle)
for dispatch, settlement, resumption and current-work selection.

Authored examples compose these contracts. Their recipes, evidence selection and
pure helper laws belong to the optional [flow-examples mount](mounts/flow-examples/README.md).
Learning proposes instruction edits; atlas maintains concept documents; format
ingestion reuses native decoders without a model. None owns a separate work loop.

Nenex's page/block question interface uses the shared answering policy directly;
it does not need to manufacture a flow. Cooperate investigations use the same
captures and provider protocol without requiring a document editor. A document
revision flow adds editorial and publication rules to that protocol.

Overlays and cells are views, not writable branches or ambient process namespaces.
Reads do not dispatch providers. An attempt's frozen evidence and definition remain
separate from its live context lens. An authored `/flow/invoke` evaluates the captured
child in the same invocation, with explicit inputs and scoped step identities.
Suspended child work uses the parent's native requests, holes and resolutions.
The parent's selected writer owns final publication. Captures, child step results
and final call results remain distinct events in the ordinary trace.
Lens authoring rejects aliases that overlap its primary subject, constructor
coordinates, or another alias. An intentional replacement belongs in an explicitly
selected transformation rather than an accidental context name.

Pure calculations compose as Foil functions or published Grove `@sewn`
transformations with captured input/output norms. Expose an intermediate result as
an ordinary cell or overlay when it needs an address, subscription or inspection.
The optional `graph` library provides supplied-tree reference/assertion operations
and demanded `children`/`gather` constructors. Its explicit policy is published
normally; the native evaluator has no graph-name registry or default graph
installation. Identity/grouping rules belong to the chosen policy.

Ordinary cells resolve their declared inputs eagerly. A narrow tack can avoid a
sibling dependency; selecting a branch after receiving a whole tree does not make
that computation lazy. A reference discovered in a result remains a reference.
A demand constructor instead returns an explicit native `need` or `graft` plan.
The existing reader supplies those reads and retains their observations, including
missing values and selected slots/names. The published constructor chooses what
to read; it does not receive a private namespace or watcher registry. Historical virtual-child
selection must identify its defining root and snapshot; it cannot borrow a local
case number independently from each possible ancestor. Multi-input overlays do
not gain a synthetic public case counter.

## Native boundaries

Raw `/sys/if_case` preconditions are checked and consumed by the existing native
kernel, including mixed batches. Namespace-operation planning, exception
containment, reacting hands and transaction notifications still use the shared
admission boundary. MCP accepts only nonnegative integer case guards on make
and poke; guarded deletion requires a native operation with its read-set guard.

Assertion and care-clock history sealing uses the native store. Sealed chunks are
native pins; reads follow those chunks rather than interpreting only the open
tail. This preserves x/y/z history and is separate from arena compaction.
Native arena compaction remains an explicitly requested offline prototype
maintenance strategy. It preserves the reachable world and retained history,
requires downtime and temporary disk space, and does not resolve automatic
reclamation or its performance characteristics.
Saving still uses `eden_store` and the retained native service/state continuation,
before acknowledgement or notification. There is no second save callback,
automatic remount on restore, or launcher-owned hand scheduler. These core shape
changes are validated in fresh disposable worlds. They do not upgrade an existing
saved service; restarting a world resumes its captured core and selected contracts.

The incremental native reference index is derived metadata over typed `safe`
values. `reference_index/lookup` distinguishes a known empty result from an
unavailable retained snapshot and rejects future epochs. Epoch zero selects the
supplied store boundary, including a frozen boundary, rather than the latest
index's edges. It retains at most 64 index snapshots; older index queries can be unavailable even though
the original world and x/y/z history remain retained. `reindex_references`
rebuilds metadata on an already compatible store without replacing its journal,
assertions or case ledgers; it is not a type conversion or a running-world upgrade.

MCP's incoming-reference query and `/r/<width>/<target...>` use the same native
index reader. The reverse lens is read-only and has no local x/y/z case counter.
It enumerates the selected local store's incoming edges to the target subtree;
it does not discover every external authority's references. Each edge carries
its holder path, slot path and exact asserted target safe. Those holder names
are data, not dereferenced source contents. Epoch pins select the whole incoming
set through the existing frozen reader, including its availability limits.
Membership notifications use the existing native signs and lens/crew machinery;
they create no record, journal assertion or clock for `/r`.
The native demand protocol supports selected reads, grafts and observations;
ordinary published modules supply graph policy. Protocol constructors live in the separate `sys/demand` contract and use exact
pinned artifacts. The existing `sys/view` cell contracts stay unchanged. An
unavailable pinned constructor uses native dependency watches until its selected
case arrives; a resolved immutable pin releases that temporary watch. Cyclic resolution
is checked across live, pinned and historical references, without a user-facing
read budget. This detects structural cycles; it does not establish termination
of arbitrary authored functions. The optional collection/assertion policies do
not claim to reproduce all of main's connected-world navigation or equivalence
policy. The read-only inspector uses an installed
graph overlay when available; inspecting a page does not install one or save
workspace bindings. Backlinks use the current world's native query, with no
separate links service or in-memory mirror.

A hand can select holder names from a reverse lens and rebind an ordinary
`native_work_ops/lens`. Existing cell dependency expansion then watches the
selected contents. Membership and contents are separate dependencies: an edited
source with unchanged references does not change the incoming set. The graph
library's pure `incoming_bindings` helper bounds selection to an explicit holder
scope, deduplicates holders and creates nonoverlapping live aliases. Removing an
alias releases that live content dependency; retained captures and attempts stay.
Hand out-values retain their native patch semantics. A selection hand removes
owned aliases with the existing explicit replacement card; omission from a patch
does not delete a slot. It need not change dispatch or invent a removal protocol.
The authored graph-review regression composes these existing pieces and tests
new membership, content edits, release, persistent holes and guarded publication.

MCP references for computed views pin a complete computation epoch. A later live
read can therefore return a new snapshot URL for identical values. Retain and
read the returned epoch reference to inspect the exact original computation;
this transport reference is not a new native cell case counter.

Research procedures belong in the optional [flow examples](mounts/flow-examples/README.md).
Their authored steps use the same native requests, captures, holes and hands as
other flows. Current web evidence starts with explicitly supplied URLs; registry
search and external CSV write-back are not provided. Existing historical records
remain readable; no compatibility worker consumes old private queues.

## Python and source adapters

Keep Python at host/process/transport and test boundaries:

- Eden's mount launcher and scan bridge stage files for the native filesystem foot.
- Codex's bridge owns app-server bytes and process cleanup. Native hands own work.
- `cooperate/client.py` is an optional thin MCP client for external callers.
- `flows/tests/client.py` is a transport helper for disposable regressions.
  User authoring, publication and attachment use Nenex's declared controls.
- `flow-examples/host.py` stages the exact bytes of repository files declared in
  `examples.json`. Each file uses an ordinary native source hand; the existing
  merge cell combines their named evidence. Missing files disappear from the
  current scan while native captures and history remain. There is no bundle
  adapter, aggregate evidence format or compatibility decoder.

A source adapter may decode an input or perform an explicitly requested external
operation. It must not privately decide retries, watch ownership, or completion.
Those decisions belong to existing native records and reactions.

## Examples, fixtures, and remaining boundaries

`mounts/` contains optional application and capability mounts. Demonstrations such
as `hello-grove`, `goo-moodboard`, `life` and `patch-demo` are optional examples,
not dependencies of the harness. Browser/native conformance specimens belong in
`tests/fixtures/`; block-document is now there alongside panes and tree-pages.
Do not delete a regression merely because its fixture resembles an application.

The revision policy in `work_ops.foil` constructs Semidoc draft records. The selected
writer may declare an existing native `kook` in `flow/document`; attachment captures
that declaration from the writer's exact retained record, and each revision request
keeps it for completion. The Nenex writer opts into its document form there. Without
the declaration, drafts carry source only. Form paths retain ordinary native form
resolution semantics; this is not a new behavior publication mechanism.

`flow/definition` still carries optional document pages in its pinned contract.
Ordinary compositions leave that payload empty. The contract remains unchanged;
this work does not rebrand retained values or claim to remove that historical field.
Trace extraction keeps that recipe only when a selected binding consumes the
implicit `document` input. It retains the complete recipe in that case because an
opaque selected law may use any part of it.

Source editing, Goo editing, native flow authoring and the document writer share
Nenex's attachment invariant. Structural source replacement cannot relocate named
work beneath positional prose. Safe text edits and independent page-level named
children retain their existing behavior. The guard complements each entry point's
freshness and ownership checks; it adds no parallel document representation.
The generated writer also checks Nenex's existing authored-source reconciliation,
so an unresolved native edit cannot be overwritten merely because `src` stayed
unchanged. Explicit source editing remains the way to resolve that conflict.

Flow composition, trace extraction and declared-action execution use the same
native work and admission boundaries. The [flow reference](mounts/flows/README.md)
owns their syntax, bounds, freshness rules and retained-receipt semantics.
`flow-authoring/authoring.grove` declares the controls. `author_controls.foil` decodes their
inputs once and builds arguments for existing native operations. Source text uses
Goo's rich-text codec; dynamic bindings are checked JSON objects. Browser and
headless callers use those same declarations and guards.

Input drafts belong to authored control routes. Sibling actions may reuse argument
names without sharing drafts. The declaration walk identifies each binding group;
browser submission and headless reflection use those same declared inputs.

The opt-in Codex surface provider connects investigations and explicitly authored
interactive flow requests to those controls.
Its three transport tools read native state, discover declared actions and invoke
them. Requests, replies and trace links use existing work and bridge records;
native hands in the worker’s retained trace subscribe to the exact worker, command
and original I/O request. `/io` remains transport evidence, outside native observer
indexes. The bounded prose-revision provider remains inert. Interactive authority
belongs to explicitly delegated investigations and flow requests that select the
interactive constructor and provider; namespace authority and action guards are not a per-document
sandbox. See `mounts/codex/README.md` for protocol and lifecycle boundaries.

## Validation and saved worlds

Use `extras/x/check --mount flows` for native execution suites and mounted
entrypoint checks, and `--mount flow-authoring` for the document integration.
`flow_install_tests` exercises native installation and a Semidoc composition with
Nenex and Explorer absent from the staged source closure. The flow suites cover suspension, freshness,
retries, source ownership and document publication. Nenex's suites own source/Goo
fidelity and question context. Codex's suites own provider transport and dispatch.
The fixture catalogue can be supplied to both Eden and `extras/x/check` with
`--extras-root`, following `tests/fixtures/tree-pages/README.md`.
The full flow check also compiles the production authoring Grove declaration and
compares browser-request decoding, reflected invocation and direct native
publication. Shared `goo-document` browser tests cover independent document
drafts, uncertain outcomes and refresh without repeating admitted writes. The
optional `/live` inspector has its own native route suite (`tests/inspector`),
read-only adapter tests under `mounts/inspector/tests/`, and packaged-asset host
checks. Its tests do not stand in for headless declared-action conformance.
The optional `flow-work-cost-tests.rvr` check isolates current crew hydration from
compilation and world construction. Its comparison with whole-work-tree reads is
not an end-to-end latency benchmark: the hand still reads its destination view,
and explicit retry still checks retained retry links.

`flow-boundary-cost-tests.rvr` measures complete evidence-change through controlled
provider completion and writer publication, varying retained attempts, destination
records, unselected holes and the width of one bound source subtree separately.
It also measures the actual work-history cell, the provider's negative recovery
scan with no Codex jobs, and Nenex document-manifest
serialization. Fixture creation and compilation are outside each timed interval.
Samples are single executions over forced fixtures, without a separate operation
warm-up or statistical repetitions; they do not establish steady-state scaling.
Counts describe actual fixture trees and committed events, not an instrumented
count of every internal read. Source width does not measure independent dependency
fan-out or overlay depth; retained fixture activities increase history filtering
without necessarily increasing visible rows. These are local native measurements, not live-model latency,
browser layout/network timing, or a native Save/restart benchmark. There are no
machine-specific timing assertions. Run it explicitly with
`extras/x/check --mount flow-authoring --suite flow-boundary-cost-tests`
with `WISP` set, or in the native development shell; cost checks are not part of
the default functional gate.

A local disposable run on 2026-11-04 produced the following observations. Other
disposable compilation was running; these are illustrative measurements, not
latency targets or a statistical performance claim.

| Boundary | Fixture growth | Observed time |
| --- | --- | --- |
| Maintenance through publication | 17 → 529 retained work records | 709 → 765 ms |
| Work-history cell | Same retained work growth | 5 → 25 ms |
| Maintenance through publication | 1 → 129 destination holes | 684 → 865 ms |
| Document serialization | 0 → 128 paragraphs; 1,316 → 27,336 bytes | 9 → 168 ms |

The current-work projection stayed at two records and each maintenance sample
committed six events. That bounds this selection, not the complete transaction:
destination inspection, history filtering, authority recovery scans and document
serialization still have costs that grow with their inputs.

Unit state-machine tests may simulate write application or use fixture input
shorthand. They supplement native admission and compiled Grove tests; they do not
replace them. Controlled provider results establish lifecycle behavior, not a
fresh end-to-end live Codex run. Keep regressions for retained capabilities beside
the implementation, including pinned cycles and occupied allocation descendants.

Validate refactors in disposable worlds. Captured implementations, attempts and
x/y/z history belong to the saved world, not the source checkout. This cleanup does
not activate modules, patch a bootstrap, migrate a world or clean its storage.
Reference projection is an ordinary supplied-tree computation and does not change
the core `sov` storage contract. Reader fixes still change executable behavior;
publishing a mount does not replace the retained service/compiler in an existing
world or establish a safe activation path for it.
