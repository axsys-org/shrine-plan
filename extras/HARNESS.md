# Harness, documents, and applications

The harness is the shared native work protocol plus the procedures and provider
adapters that use it. It is not a second world, a Python runner, or a replacement
for Nenex. Nenex is a document application in that world. The handbook is an
authored procedure and its maintained documents, not another application runtime.

## Ownership

| Location | Owns | Does not own |
| --- | --- | --- |
| `src/foil` and `src/reaver` | Namespace reads/writes, admission, reactions, cells/views, filesystem I/O, publication, Semidoc and native persistence | Application-specific work policies and handbook recipes |
| `mounts/cooperate/work*.foil` (`native_work`, `native_work_ops`) | Captures, activities, events, provider dispatch receipts/outcomes, context lenses and persistent holes | Document structure, source polling, provider transport |
| `mounts/cooperate/main*.foil`, `answer*.foil` | Investigation and question-answering policies over native work | Another attempt lifecycle or private work store |
| `mounts/flows/flow*.foil`, `runtime*.foil` | Semidoc procedure compilation, pinned operation selection, evaluation, preview and guarded commit | Browser state or provider processes |
| `mounts/flows/maintenance*.foil`, `request_ops.foil` | Reactive procedure maintenance and generic suspended requests using native work | Polling, a work queue, or a second retry receipt |
| `mounts/flows/work*.foil`, document operations in `operations.foil` | Document-revision policy: briefs, drafts, accepted revisions and evidence | A second provider lifecycle; arbitrary executable content generation |
| `mounts/flows/sources*.foil` | Evidence adapters and live source bindings using existing filesystem ownership | Filesystem actors, Nenex pages, example installation |
| `mounts/flows/web*.foil` | Explicit HTTP request/result adapter and native transport foot | Automatic research, polling or application-specific crawling policy |
| `mounts/codex` | Native provider hand and app-server transport/process lifetime | Deciding when a flow runs or when a domain result is acceptable |
| `mounts/graph` | Optional Foil/Grove transformations over explicitly supplied evidence, reference projection and conflict-preserving assertion policy | Namespace reads, a graph store, implicit identity, source polling or a work lifecycle |
| `mounts/nenex` | Semidoc page ownership, source/Goo editing, reader, question/block context and page-tool contributions | The work lifecycle or a flow evaluator |
| `mounts/flows/nenex*.foil`, `interface.foil` | Flow/Nenex integration: source authoring, page evidence, guarded writer and forms | The generic command catalogue or filesystem-source lifecycle |
| `mounts/flows/install.foil` | Native flow command/law registration and retained-contract checks | Nenex routes or example catalogue |
| `mounts/flows/examples.foil`, `examples/`, `examples.json` | Optional authored recipes and their setup data | Runtime policy for all flows |
| `tests/fixtures/block-document` | Goo regression fixture with its own small bounded block model | Nenex's document representation |

`install.foil` can assemble native commands without importing Nenex. The shipped
`flows` **mount still bundles** that backend with the Nenex integration and declares
Nenex as a dependency. Module separation is not a claim that there is already an
independently installable headless flow mount. Existing pinned module ownership,
logical names, public commands and retained contract definitions are unchanged by
this cleanup. We do not move contracts between publishers to tidy directories.

Each mount activates its own behavior records. A flow refresh updates the flow
commands and its Nenex contribution; it cannot reinstall an older captured
Cooperate hand or Nenex document form. Dependency installation remains with the
existing mount ordering and each dependency's own activation.

The flat source bags are a deliberate Eden publication boundary. Keep logical
responsibilities clear inside them instead of adding a new directory loader,
umbrella service, or compatibility mount. Runtime modules stay flat; examples and
test assets can live in subdirectories and are staged by the existing host/gate.
The flow native suites and transport fixtures are grouped under `flows/tests/`;
`mount.json` retains their existing logical suite names.
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

A Nenex page can select a published flow into an ordinary captured cell and embed
an independently bound occurrence. The occurrence is the existing maintenance
controller under the page's named `work` child. A Semidoc `doc/embed` reference
projects that controller's work, cells and controls; it does not own the activity.
Removing the reference leaves the activity and history intact. Explicit detach
releases its claim and subscriptions. Selected occurrences retain the exact
definition publication while their input bindings remain live; existing live
maintenance attachments continue to follow publication.

The hand reconciles its existing crew from current jobs and live owned hole heads,
selecting the corresponding requests, workers, drafts and guards. It does not
subscribe to the whole retained work tree. Retained controllers use the same
derivation; their attempt identities do not need to be rewritten. Allocation checks
temporarily select the exact prospective attempt subtrees through that same crew;
the native wake operation resolves those probes before creation. Superseded
attempts remain retained but cannot block current dispatch or authorize a late
result. Detach also withdraws the context subscriptions of holes owned by that
controller, leaving other consumers and historical captures intact.
Direct adoption and detach derive that same selection before acting, even when a
retained controller has not reacted yet. The Cells history projection reads
retained requests independently; displaying completed attempts does not add them
back to the hand's current jobs or subscriptions.

A complete evaluation may reuse a matching retained resolution. Publication
settles only owned demands actually fulfilled in its accepted trace, then
withdraws their live subscriptions. The failed attempt remains failed and its
captures remain intact. Completion removes obsolete failed job selections while
retaining the allocation serial and accepted completed jobs. A later unresolved
demand gets a fresh attempt head.
An unrelated question or another controller's hole is not a completion.

Authored domain libraries sit above these contracts. The cartography examples
compose HTTP evidence, cited assertions and document maintenance as captured
Semidoc child flows. Their optional operations are supplied by the example
catalogue, not native flow installation. They select an ordinary Grove projection
instead of copying graph policy. A task can capture a pure `flow/operation`
validator; the existing acceptance boundary applies it before resolving a hole.
Validated results use ordinary frozen value cells and retained native receipts.

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
The optional `graph` library follows this boundary: it derives references and
assertion reports from supplied trees, without a special evaluator or default Eden
installation. Its explicit assertion policy is not a namespace identity rule.

Ordinary cells resolve their declared inputs eagerly. A narrow tack can avoid a
sibling dependency; selecting a branch after receiving a whole tree does not make
that computation lazy. A reference discovered in a result remains a reference.
Following it requires an explicit binding or an existing authored operation, not
an implicit namespace read during a pure transformation. Historical virtual-child
selection must identify its defining root and snapshot; it cannot borrow a local
case number independently from each possible ancestor. Multi-input overlays do
not gain a synthetic public case counter.

## Compatibility with the November 2026 main merge

The integration reconciles main `d0deab2` with the shared harness. Raw
`/sys/if_case` preconditions are checked and consumed by the existing native
kernel, including mixed batches. Namespace-operation planning, exception
containment, reacting hands and transaction notifications still use the shared
admission boundary. MCP accepts only nonnegative integer case guards on make
and poke; guarded deletion requires a native operation with its read-set guard.

Main's assertion and care-clock history sealing is retained. Sealed chunks are
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
There is no kernel demand evaluator, implicit prose relationship, or new kernel
read budget. Optional graph policy remains ordinary published Foil/Grove
over explicitly supplied evidence. It currently has narrower capabilities than
main's connected-world graph policy. Explorer can save workspace bindings without
that optional policy; it reports the missing definition instead of claiming an
empty connection graph. Backlinks use the current world's native query, with no
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

Opening a workspace only reads its view. Explicit binding edits retain its
selected constructor, use native compare-and-set, and refuse to replace unrelated
authored fields or an inline captured constructor. Removing the final standing
releases its live references without deleting the record or history. Changing a
definition remains a separate publication/selection action.

MCP references for computed views pin a complete computation epoch. A later live
read can therefore return a new snapshot URL for identical values. Retain and
read the returned epoch reference to inspect the exact original computation;
this transport reference is not a new native cell case counter.

The upstream research scripts and registry schemes under `mcp/hands` remain
standalone source, not installed shared-harness hands. Their private `asks`
records and queues are not consumed or converted by native work. Reusing a parser
or registry adapter does not imply adopting its scheduler, model loop, or
write-back policy. Porting those domain capabilities into authored flows is
separate work; this integration does not claim feature parity with those scripts.

## Python and source adapters

Keep Python at host/process/transport and test boundaries:

- Eden's mount launcher and scan bridge stage files for the native filesystem foot.
- Codex's bridge owns app-server bytes and process cleanup. Native hands own work.
- `cooperate/client.py` is an optional thin MCP client for external callers.
- `flows/tests/client.py` is a transport helper for disposable regressions. The old
  production `flows/client.py` handbook workflow has been removed; use Nenex's
  author/publish/attach operations.
- `flows/host.py` stages the exact bytes of repository files declared in
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

Composition reuses native dispatch and holes, captures child definitions and bindings,
and gives effects an admitted writer. Evaluation is bounded to eight nested calls
and 128 executed steps across the whole invocation. Child publication takes effect
for live-path callers only when they are explicitly republished; explicit native
historical references remain pinned. Nenex composition controls author these
references and repeated bindings in Semidoc itself. Selected executed steps from
retained runs can become new Semidoc procedures with external dependencies exposed
as inputs. Arbitrary exploratory traces, ambient inherited bindings and independently
scheduled child controllers remain outside this implementation.

Declared Goo actions reuse the existing request interpreter and receipt journal.
A flow requests native work; its hand emits a native namespace command. Shared
admission checks current work and evidence before planning the declared Goo
action and its receipt together. The hand observes that receipt before accepting
the result. Existing emitted moves carry these commands; no action foot, polling
loop or second interpreter is added. Nenex reflects compiled controls into
captured cells and exposes their bindings for deliberate selection. Source authoring and extraction belong to the Nenex flow adapter;
the action work provider belongs to the shared harness.
Flow publication and authoring controls are declared in `flows/authoring.grove`
and embedded through the existing Goo presentation host. Source editing, callable
inspection/selection, composition, occurrences, source bindings, lifecycle controls
and investigation delegation adapt the existing native operations. Browser and
agent invocation use those same declarations and admission guards. Rich source
inputs preserve Semidoc newlines through Goo's existing text codec. Existing forms
remain usable; the declarations do not replace the native command contracts.
The same declaration walk identifies each input's binding group. Browser actions
submit only their declared inputs; drafts belong to authored control routes, so
sibling actions can use the same argument names without sharing or clearing drafts.
Headless reflection uses those bindings to distinguish plain and rich text inputs.

The opt-in Codex surface provider connects an investigation to those controls.
Its three transport tools read native state, discover declared actions and invoke
them. Requests, replies and trace links use existing work and bridge records;
native hands in the worker’s retained trace subscribe to the exact worker, command
and original I/O request. `/io` remains transport evidence, outside native observer
indexes. The bounded prose-revision provider remains inert. Interactive authority
currently belongs to explicitly delegated investigations, not arbitrary automatic
flow requests; namespace authority and action guards are not a per-document
sandbox. See `mounts/codex/README.md` for protocol and lifecycle boundaries.

## Validation and saved worlds

Use `extras/x/check --mount flows` for native suites and mounted entrypoint checks;
`flow_install_tests` exercises native installation and a Semidoc composition without
importing the Nenex integration. The flow suites cover suspension, freshness,
retries, source ownership and document publication. Nenex's suites own source/Goo
fidelity and question context. Codex's suites own provider transport and dispatch.
The fixture catalogue can be supplied to both Eden and `extras/x/check` with
`--extras-root`, following `tests/fixtures/tree-pages/README.md`.
The full flow check also compiles the production authoring Grove declaration and
compares browser-request decoding, reflected invocation and direct native
publication. `node extras/mounts/nenex/tests/publication.cjs` checks publication
frame cleanup and protection of unsaved source drafts.
The optional `flow-work-cost-tests.rvr` check isolates current crew hydration from
compilation and world construction. Its comparison with whole-work-tree reads is
not an end-to-end latency benchmark: the hand still reads its destination view,
and explicit retry still checks retained retry links.

Validate refactors in disposable worlds. Captured implementations, attempts and
x/y/z history belong to the saved world, not the source checkout. This cleanup does
not activate modules, patch a bootstrap, migrate a world or clean its storage.
Reference projection is an ordinary supplied-tree computation and does not change
the core `sov` storage contract. Reader fixes still change executable behavior;
publishing a mount does not replace the retained service/compiler in an existing
world or establish a safe activation path for it.
