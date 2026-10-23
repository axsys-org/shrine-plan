# Reflective flows and a shared headless Goo harness

Status: concept-authoring implementation, October 23, 2026. The
[Semidoc flow harness](../../extras/mounts/flows/README.md) now includes a reusable
judgment step, native revision requests, editable drafts, working overlays and
a native Codex provider hand. `cooperate` and flows share `native_work`
activity state, captures, frozen results, trace metadata and provider contracts. General extraction, branching,
reflective composition assistance and wall-clock scheduling remain future work.
Nenex now supplies source authoring, publication and maintenance attachment
through native page tools; those forms reuse the published harness operations.

The shared native harness now also implements live context lenses and persistent
subject-owned holes. Investigations publish a selected live `lens` alongside
their frozen captures. Flow revisions retain a demand on the concept itself,
with a question, expected shape, reason and current attempt. A native hole hand
watches its context cell and notifies the existing maintenance activity when
relevant evidence changes. The provider can leave a concept unresolved; changed
evidence creates a new attempt while older captures remain intact. Completed
holes stay attached and may reopen. This is evidence-driven resumption through
cells, crew and hands; it adds neither a Python scheduler nor clock-based retry.

The handbook and Cells now share one world. Nenex embeds the existing Cells
renderer over a readable native work cell. That cell projects controller state,
concept requests, evidence and holes without owning another lifecycle. Native
filesystem capture replaces the standalone Python observer. The Codex bridge
remains external protocol I/O; the shared hands own dispatch and admission.

## Ian's bare loop: inspected integration points

Inspected `origin/ic-bare-loop` through `ca15e747e7f80fd85d30caf7e84173e2ca40b6b6`
after fetching on October 23, including its delta from `06eb23b`.
This is an architectural comparison, not a merged implementation.

* `extras/mounts/mcp/hands/agent.py` makes a gather cell the agent's next-turn
  lens. Each turn reads that live lens plus the current message; the model
  proposes records and rewrites its references for the next turn. This supplies
  a concrete pattern for an investigation's changing context. A flow attempt
  still needs frozen captures of the lens actually used, so a later live read
  cannot silently change the evidence under which a result was accepted.
* `hands/web.py` treats an ask as a shaped hole and fills it with sourced rows.
  Shared native work requests can use this demand/result pattern for additional
  providers. The current prose revision provider does not implement research or
  a general model-directed write loop.
* `hands/source.py` retains source locators, materializes demanded regions and
  checks markers/digests before refreshing or writing back. This is relevant to
  external-format loading: a source adapter can supply addressable evidence
  without imposing a new document/editor model or a slot for every paragraph.
* `hands/refresh.py` represents volatile facts with refresh recipes. A failed
  refresh retains the current fact and records the broken recipe. That maps to
  explicit producers and invalidation; it does not require model calls for
  deterministic refreshes.
* The latest `agent.py`, `web.py` and `crawl.py` retain an unanswered question at
  `<record>/holes/<slot>`, alongside the thing it concerns. `unknown` retries
  with backoff; `watch` repeats; `until` waits for a date. Asks retain their
  destination record/slot, requested shape and search query. This is a useful
  ownership contract for authored flows: unresolved work should remain attached
  to its subject and carry an explicit retry policy. In our harness that policy
  can be a typed work value with captured evidence and guarded admission. Native
  clock-driven scheduling is still a gap; this inspection does not install it.
* The latest web provider adds optional Firecrawl search, site mapping for
  collections and rendered-page fallback, then uses the same extraction path.
  The live queue also displays persistent holes. These are source/provider and
  work-presentation patterns to reuse; network adapters and credentials remain
  outside the native work lifecycle.

The branch calls external MCP client processes hands; our `form`/crew hands run
inside native namespace admission. Its stream filtering and batch-to-individual
write fallback have different completion semantics from a guarded flow
publication. Reuse the context, demand and producer contracts while keeping
external I/O at the provider boundary and work admission in the shared harness.
Do not import another Python agent scheduler alongside the native lifecycle.

## Implemented handbook slice

The canonical Semidoc recipe contains concept briefs with declared source
dependencies. `inventory → revise → evidence` validates source envelopes,
authors concept documents, then composes a compact evidence index. The old
bounded Markdown importer remains an optional format loader; it is not the
handbook's organizing principle or a layer between Nenex and the editor.

A revision operation produces typed tasks. Evaluation suspends until matching
resolutions exist. The ordinary maintenance `spun` binds source inputs and
resolutions; its hand creates missing work and resumes downstream operations.
A resolution is reusable only for the exact brief and source evidence. Each
request retains the captured definition, native Semidoc instructions and draft,
frozen evidence/prior cells, and a spun overlay of the same working state.
Native editor operations edit the physical draft that the overlay binds.

The provider-neutral submit operation checks current task identity, controller
state, draft revision and inert Semidoc structure. The native Codex hand
dispatches an existing bridge command and watches a stable turn result. The
flow hand admits that result through the same domain checks. Python handles
filesystem/process I/O and command-line transport; it does not coordinate work. Syntax and freshness validation
do not prove that generated claims are true. Failed responses remain inspectable.

After all required concepts are ready, the existing pure Nenex writer applies a
complete tree. It protects edited generated prose, named annotations and existing
work; competing destination maintainers, collisions and implicit page removals
refuse. Completed generations retain inputs, step traces and typed results.

The default controller lives beneath the authoring document's named `work` child.
The handbook includes external-format loading and address/OSM representation
guidance. The earlier address-book/Austin demo was removed; address/OSM is
proposed representation guidance. Runtime metadata uses cohesive typed values
instead of a slot for every struct field.

The filesystem mount captures evidence, with stable-change detection in its native foot; the native hand owns
invalidation and publication. Missing files block while retaining the last good
handbook. Model and filesystem I/O require their companions to remain running.
Eden saves and restores the complete namespace through the runtime's native
continuation store before acknowledging writes. I/O services reconnect with fresh
host arguments; interrupted model attempts retain terminal outcomes without
automatic replay. The full shared virtual namespace and
arbitrary write-through overlay discussed below are broader design work.

## Purpose

A flow is a reusable, inspectable procedure with explicit bindings, steps,
branches and results. It can be authored directly in Semidoc, composed from other
flows and existing programs, extracted from a trace of user or agent work, or
developed through a mixture of these. Extraction is one authoring route.

An extracted flow retains its relationship to the source actions and extraction
decisions. An authored flow retains its source and composition history. Both
produce execution evidence when invoked; subsequent attempts can inform a
proposed revision without silently changing the definition already in use.

This belongs in shared harness infrastructure. Nenex and other documents can
author, present, bind and compose flows. Semidoc can own a flow's canonical source;
an occurrence elsewhere can reference that definition. Publication and execution
use the same definition identities and attempt records across documents, native
clients and agents.

Language/PLAN reflection makes program structure available to authoring and extraction:
declarations, types, generic schemes, retained code and referenced definitions.
Goo declarations supply an interaction structure over those programs. Shrine
supplies identity, history, derivation, dependency notification and write admission.

## Existing mechanisms and precise boundaries

| Area | Source evidence | Consequence |
| --- | --- | --- |
| Type reflection | `src/reaver/reflect-demo.rvr`, `foil-type-core.rvr`, `foil-new-elab.rvr` | `(^ expr)` reifies the static elaborated type without evaluating the expression. Function, record, sum, generic and nominal descriptors are available. |
| Program inspection | `src/reaver/compiler-inspect.rvr` | Descriptions include declaration values, retained source, reflected types, references and optional law rendering. Descriptions alone are not restorable compiler artifacts. |
| Generic object presentation | `extras/mounts/explorer/goo_reflection.foil` | Exact nominal brands select descriptors; a generic inspector already works without an app-specific renderer. Unknown shapes remain bounded fallbacks. |
| Cells | `src/foil/lain_peek.foil`, `sys/view.foil` | Pinned behavior, primary/secondary input references, live bindings, cycle checks, derived output and context diagnostics already exist. |
| Pure transformations | `src/foil/sys/view.foil`, `grove_sewn.foil` | `dyed`, `knit`, `felt`, `sewn`, `spun` and `cell` provide several transformation shapes. Grove `@sewn` publishes a `spun` value with captured norm contracts for `/x`. |
| Reactive behavior | `src/foil/sys/hand.foil`, `lain_poke.foil` | `form` laws receive state and activation context, return new state and cards; named crew dependencies drive `hear`. `dead`/`goof` remain vocabulary only. |
| Atomic commands | `src/foil/namespace_command.foil`, `helm.foil` | A trusted `namespace_op` plans multiple writes against one state; supervisor admission validates and commits without a client read/write gap. MCP already exposes this. |
| Goo interaction | `src/foil/goo_runtime.foil` | Controls resolve against published declarations, with receiver/role, argument, selection capture, revision and publication checks. Invocation IDs have receipts. |
| Headless operation | `src/foil/tests/goo_runtime.foil` | Registered tests invoke the same native Goo runtime directly against namespace values, including actions, captures and retries, without a browser. A separate creation fixture is also present in the source. |
| Portable semantics | `extras/mounts/goo/PORTABLE.md`, `extras/mounts/explorer/goo_bridge.foil` | Prepared surfaces expose semantic roles, inputs and control bindings, declaration routes, capture requirements and presentation status. |
| Work traces | `extras/mounts/cooperate/main.foil` | Captures, parent/reply edges, append records, typed frozen artifacts, stale completion checks and retry identities exist. Arbitrary actions are not automatically captured as executable steps. |
| Documents | `extras/mounts/nenex/main.foil`, `src/foil/semidoc.foil` | Named work/cell children survive prose edits; legacy reference transclusion exists. General retained interactive flow occurrences are still separate integration work. |

Two gaps must not disappear behind the word "reflection":

* Published Grove action schemas describe slots/presence but do not yet provide a
  complete machine codec schema. Native type descriptors and exported codecs can
  ground this extension; reflecting a broad static `pail`/`any` does not recover
  every possible runtime contract.
* Compiler reference edges describe code dependencies, not all data read during
  execution. Extraction needs declared captures or instrumented namespace reads,
  plus explicit records of external observations. A type signature cannot reveal
  every effect or establish that two procedures are equivalent.

## One interaction adapter for declared Goo applications

A headless client can implement the same interaction contract as a visual client:

1. Obtain a checked presentation of a subject at a declared view/slot and retain
   its snapshot and publication identities.
2. Inspect semantic inputs, control routes and selection sources. Resolve local
   selection and draft state without relying on pointer coordinates.
3. Freeze the chosen control, typed values or their supported wire encoding,
   selection evidence and expected revisions into one invocation.
4. Submit through the ordinary admission boundary. Retain the receipt; refresh
   the presentation after a change, and inspect the resulting namespace state.

The native harness may call these operations directly. Remote clients can use a
shared transport adapter. MCP is an optional transport, and each application
needs only its ordinary domain declarations and Goo interface, provided the
adapter supports the primitives that interface uses.

The headless client still needs selection, encounter identity, draft and retry
semantics. `presented:false` describes an absent prepared control; a client must
not manufacture an interactive widget from it. Browser inspection captures are
observations, not replayable action authority. Layout/visibility constraints and
domain contracts have different purposes and must remain distinguishable.

This is concrete semantic application use. It does not imply automatic support
for arbitrary external applications or undocumented custom interactions.

## Shared operation admission

Goo can invoke a published `namespace_op` through the same bound-control checks
as ordinary record actions. Nenex's block editor uses this path. Native harness
clients can invoke the same domain operation through namespace admission. Keep
single-record action adapters and creation checks where they apply.

Capture the operation identity, definition moment, receiver, concrete arguments,
relevant reads and outcome at this shared boundary. Add the trace write to the
same admitted batch where possible. Record namespace commit references so that
downstream effects of hands can be inspected without confusing them with another
user command. Do not assume today's Goo receipt journal is already a complete,
durable execution trace.

Goo currently restricts writable subjects to the local `/app` subtree. Cooperative
work can live under other permitted roots. A shared adapter needs explicit
receiver scope, rather than silently broadening the existing Goo restriction.

## Author or compose a flow in Semidoc

The proposed authoring contract has three entrances: write a definition, compose
existing definitions, or extract a candidate from recorded work. They converge on
the same checks and publication path. An authored definition requires no invented
demonstration trace before it can run.

A Semidoc definition should be able to contain:

* Purpose and domain guidance, including when the flow is useful.
* Named inputs/holes, their contracts, defaults and live or pinned references.
* Steps referencing Foil programs, cells, overlays, declared operations, other
  flows or explicit external-worker requests; branches and producer bindings.
* Named results, intended writes and ownership, completion conditions and example
  fixtures. Pure previews and state-changing steps remain distinguishable.
* Optional activation policy: manual invocation, or dependencies and stateful
  transitions managed by a hand. A hand is not required by the word "flow".

These are semantic requirements, not an implemented Semidoc syntax. Descriptive
prose alone does not become executable. An explicit definition region is parsed,
elaborated against retained language context, checked and published. If that
region lives in Semidoc, it is the canonical authored source; a compiled artifact
and namespace projection are derived publications, not independently edited
copies. Editing an ordinary embedded occurrence changes its bindings unless the
user enters the definition's authoring view.

Reflection can offer compatible declarations, expose missing inputs, instantiate
generics and explain type errors while composing. It cannot infer every read,
effect or intended domain rule. Those remain explicit or are captured at runtime.
Example checks qualify particular behavior rather than proving general intent.

Runtime state, attempts and dependency subscriptions live separately from the
authored definition. A document save cannot silently replace the definition of
an active attempt. Removing an occurrence is also distinct from deleting an
owned definition or cancelling work; those require defined document operations.

## Extract a flow from an observed trace

The initial extractor should support explicit selection and parameterization.
Automatic abstraction can follow once the records and checks are adequate.

1. **Capture actual work.** Store the operation and its pinned definition,
   receiver/input bindings, captured observations, outcome and relevant commit or
   artifact references. Record a producer relationship when an argument comes
   from an earlier result. Keep temporal, dependency and branch edges distinct.
2. **Select a result and trace region.** Walk required producer/capture edges
   backwards. Preserve state reads and effect ordering, including reads whose
   values influenced a decision without appearing in the final output. Incomplete
   capture remains explicit; do not silently claim a complete dependency slice.
3. **Expose the boundary.** Incoming values become constants or named parameters;
   outgoing values become results. Keep an observed choice fixed until a person
   or a separately recorded extraction step proposes a predicate or agent step.
4. **Reflect referenced programs.** Consult signatures, nominal definition
   moments, role/norm contracts, generic schemes and codecs. Construct typed Foil
   calls and bindings against the retained compiler context. Use retained typed
   structure/source for authoring; keep actual code/pins for execution identity.
5. **Publish a composition.** Reuse existing cell constructors, transformations,
   declared actions and commands. Optional Grove templates can install instances.
   Rebase only explicit instance references, preserving shared definitions.
6. **Check the candidate.** Replay pure transformations over captured inputs and
   compare the selected results. Exercise writes against an isolated fixture or
   explicit preview plan. Preserve external effect steps and their recorded
   observations; inspecting an old trace must not repeat those effects.
7. **Invoke with new bindings.** Create a fresh attempt tied to the chosen flow
   revision. Later attempts can support another proposed revision, with provenance
   back to both the source trace and the extraction decisions.

A compressed group retains its constituent action identities. It may expand in
an inspector or be referenced by another flow. Grouping does not delete evidence
or equate separate executions merely because their visible outputs match.

This is ordinary typed composition and explicit state. A new general graph
interpreter is unnecessary until a concrete requirement demonstrates otherwise.
Loom supplies ideas for branch selection, alternative inspection and grouping;
its selected text thread is not the dependency specification for execution.

## Cells derive; hands and admitted commands advance state

A useful implementation division is:

| Mechanism | Proposed responsibility |
| --- | --- |
| `felt` | Produce trace summaries and extraction diagnostics from a finite input tree. |
| `sewn` / Grove `@sewn` | Restructure selected trace material into a proposed composition or document projection. |
| `knit` | Expand a bound definition into a visible plan or instance description. |
| `/x` cells | Bind parameters and referenced inputs; derive results and previews. |
| `/c/x` | Expose missing bindings, faults and extraction diagnostics. |
| `form` / `crew` | Respond to dependency changes and advance explicit execution state. |
| `namespace_op` | Validate and commit a proposed state/document update, including associated records. |
| External worker | Perform model/tool I/O and submit recorded observations to the native continuation. |

The live dispatcher rejects writes to `/o` and `/x`. Optional `patch` fields in
transformation types do not establish general write-through overlay support.
Goo has a narrow `tack`/`sys/from` mapping for identity-preserving projections.
Joined, summarized or synthesized output needs an explicit command mapping to
the canonical records it intends to change.

For self-maintenance, a crew notification can make an execution eligible to
refresh; a native transition chooses the next step; pure cells produce a
candidate; an admitted command commits it. A model call uses explicit suspended
state and a worker response. Define overlap/coalescing behavior before installing
automatic refresh. Native world restoration preserves this state and its compiled
definitions. Date/backoff scheduling remains separate design work.

## Block sewing and embedded authoring

A sewing can derive a new block tree or a proposed change set. Applying it should
be a document operation that validates stable block/occurrence identities,
expected document revision and ownership, then commits the affected records.
The sewing itself remains previewable as a value.

A flow block binds a canonical subject and a published Goo presentation. The same
subject can appear as input controls, result, trace, source or plan. Source editing
targets the canonical authoring region, which may be in Semidoc or a registered
Foil/Grove draft. Its source adapter compiles and publishes a new definition;
ordinary prose and arbitrary code blocks do not implicitly execute.

The current draft adapter provides useful preview/publication machinery but
recompiles at publication and uses instance replacement. Active flow instances
need explicit successor publication/migration instead of destructive replacement.
The existing document plan also identifies stable occurrence identity, retained
interactive hosts and historical captures as required inline integration work.

## Proposed starter flows

These are candidate shipped definitions for the shared harness, not existing
installed flows. Nenex is their initial document destination and authoring
surface; inputs and output operations should remain explicitly bound.

### Build and maintain a system handbook

Inputs: a source manifest for Grove, Foil/PLAN, cells/overlays, hands and Goo;
published definition roots; a target Nenex root; audience and editorial rules.
The manifest can include README/tutorial files and executable fixtures as well
as namespace references. Missing files or unpublished definitions are reported.

Compose inventory -> reflect declarations -> organize concepts and tasks ->
draft pages -> derive a proposed document tree -> check references and examples
-> admit a revision. Drafting explanatory prose can be an external model step;
inventory, binding checks, tree construction and admission should use ordinary
native operations where possible. Example execution is an explicit fixture step,
separate from rendering an authored expected result.

A useful output outline is:

```text
handbook/
  start-here
  concepts/       namespace, Foil and PLAN, Grove, cells, overlays, hands, Goo
  recipes/        compose a cell, author a flow, sew a document, maintain a section
  domains/        research, projects, contacts
  reference/     links to published declarations, source and example fixtures
  maintenance/   source versions, open gaps, proposed updates, run evidence
```

This is a logical outline, not an installer path specification. Each page uses
Nenex's actual source/record contract. Named direct children hold harness state;
numbered prose children remain owned by Semidoc.

The existing `goo-documentation` mount already reads `/sys/lede`, `/sys/help`,
`/sys/mold` and `/sys/src`, and can inspect source from the exact pinned compiler
artifact. Reuse that material and link definitions instead of inventing a second
authoritative API catalog. Label evidence as implemented contract, observed test,
documented convention or proposed design; preserve disagreements for review.

Refresh only sections owned by the flow. Keep authored notes separately or merge
against the last generated version with explicit conflict handling. Stable source
identities support page matching; source revision/digest supports freshness.
Filesystem changes need an importer or worker to publish new source observations
before namespace crew dependencies can notice them. Namespace subscriptions alone
do not watch README files on disk.

### Shape a tree for a domain

Inputs: domain, intended work, a few representative records, existing tree and
applicable conventions. Output: a proposed structure, reasons for the choices,
reusable templates, bound views and a concrete creation/migration plan.

Teach containment as lifecycle ownership, and references as relationships that
can cross that ownership. Reuse published slots and roles where their meaning
fits; identify new domain definitions explicitly. Role matching does not itself
enforce foreign-key integrity or reject arbitrary writes. Domain commands must
enforce any such requirements. Keep evidence, canonical editable records and
derived presentations distinguishable.

Offer domain recipes rather than one mandatory hierarchy:

* Research: sources/evidence, claims, questions and syntheses; one source may
  support several claims and appear in several document projections.
* Projects: deliverables, tasks and decisions; status and overview blocks derive
  from the underlying records rather than keeping separate editable counts.
* Contacts: people, organizations, addresses and explicit associations. These are domain
  examples for the shared harness, not an installed address-book application.

For an existing tree, preserve subject identities where possible and preview
reparenting/reference changes. Do not turn a recommendation into an implicit
destructive reorganizer. The proposal can itself be a Semidoc containing bound
examples and an operation that applies the reviewed plan.

### Author a flow with guidance

Inputs: a task description, available subjects/declarations, optional example
work and the intended output. Output: an authored Semidoc definition with named
holes, composed steps, result presentations, examples and explicit write targets.

The guide chooses mechanisms by what the task needs:

| Need | Starting mechanism |
| --- | --- |
| A pure calculation over explicit values | Foil function. |
| A live bound result or reusable projection | Cell and appropriate overlay/sewing. |
| A validated state change | Declared action or admitted namespace command. |
| A reusable task with bindings, branches or composed steps | Flow definition, even if initially small. |
| Dependency-triggered work or a stateful continuation | Hand with explicit crew and transition state. |
| Model, network or other external I/O | Worker step with captured request/result and native continuation. |
| An interactive presentation | Goo controls/views bound to the same subjects and operations. |

Start with manual invocation. Add a hand when persistent state or reactive work
requires it; pure live derivation does not require a second refresh loop. Specify
coalescing, self-trigger suppression, stale completion and retry policy when
adding automatic maintenance. Logical hand time is not a wall-clock scheduler.

The handbook flow is a good first authored example: compose existing pieces,
publish it, then use its real attempts as evidence to improve the definition.

### Supporting starter flows

| Flow | Concrete result | Activation |
| --- | --- | --- |
| Review this tree | Findings tied to subject identities: unresolved references, missing bindings, unsupported writes through projections, duplicated canonical data candidates and departures from selected conventions. Heuristic findings remain suggestions. | Manual; optional bounded dependency checks. |
| Keep this section current | A derived result or a revision-checked update to an owned summary/table, linked to its input versions and attempt. | Live cell for a pure view; hand plus command for persisted updates. |
| Turn this work into a reusable flow | A selected trace slice with parameters, preserved branches/evidence and a checked candidate definition. | Explicit selection followed by extraction and publication. |

The initial library should ship the handbook builder, domain-tree guide and flow
authoring guide first. They explain and exercise the same primitives that users
will compose, and their run records make later extraction useful rather than a
prerequisite for authoring.

## First implementation proof

1. A headless client discovers and invokes an existing Goo control. The browser
   and headless routes enforce the same declared binding, stale-state checks and
   outcome. No app-specific tool adapter is introduced.
2. Extend the shared command path so one declared control can invoke an atomic
   multi-record command, and capture its typed inputs, definition and result as
   trace evidence. Confirm rejection leaves neither partial writes nor a success
   trace, and retry cannot duplicate the operation.
3. Author a concrete calculation using existing filter/aggregate cells followed
   by a command that writes a summary record. Publish it with explicit collection
   and predicate parameters. Separately extract a candidate from recorded work
   for the same task. Check both authoring routes against a second fixture through
   the same publication and invocation contracts.
4. Add a declared crew dependency and refresh transition. Changed input produces
   a new attempt/result with provenance; merely reading a result launches nothing.
5. Author a definition region in Semidoc and consume its published flow from a
   separate document occurrence. Reordering or removing that occurrence preserves
   the definition; a document sewing uses the same admitted write path. Runtime
   state survives unrelated prose edits.

This sequence establishes the harness independently of a document application,
then proves that document maintenance is one ordinary consumer.

## Validation performed

On the working tree based on `ec502f7`, the following focused existing suites
passed with the installed Wisp runtime:

```sh
WISP=/nix/store/gz0i0k6ja79q2k3y020frl7bdsr6d8an-enki-pgo-0.1.0/bin/wisp \
  python3 x/test_runner.py foil:tests/goo_runtime \
  foil:tests/namespace_command --jobs 1
```

The Goo suite reported 46 passing assertions and the namespace-command suite 26.
Results are in `.check/run-kemkw58v/results.json`. These qualify the existing
native invocation and admission paths, not the proposed generic headless client,
trace extractor, automatic refresh scheduler or document sewing integration.
Those checks preceded the handbook implementation. Flow-specific validation is
documented with the implemented harness; these earlier checks alone do not qualify it.
