# Semidoc flows

See the [extras ownership map](../../HARNESS.md) for the boundary between the
shared harness, Nenex adapters, providers and authored examples.

A flow is a reusable procedure with explicit inputs, operations, dependencies
and results. Here, Semidoc authors that procedure alongside its explanation;
publication captures the selected native operation laws. An invocation binds
it to evidence and retains its attempts, intermediate values and effects.
Cells expose the work, overlays provide working views, and hands react to
dependencies. Holes keep unresolved work attached to its subject.
The current executor supports ordered compositions, captured child-flow invocations
and suspended provider requests. Retained flow runs can supply selected steps for
an editable new procedure; arbitrary exploratory activity is not inferred as code.
The generic installation publishes these capabilities without creating a
handbook, choosing its evidence, or attaching a provider.

## Author and run

With `flows` mounted, open Nenex and use **Page tools → Flows**:

1. Choose **Author a new flow**. **Composition** starts with an ordinary input
   and identity operation. **Document revision** explicitly selects the document
   adapter and its evidence/brief starter.
2. Use **Compose an operation or child flow** to select a callable and bind its
   ports, or edit and save the Semidoc source. Ordinary prose and literal examples
   stay inert. Only the marked definition is compiled.
3. Enter the authored definition's name in **Publish flow**. This Goo control
   captures the saved definition and selected native laws. Unsaved source must
   be saved before it can be published.
4. Bind the inputs to namespace paths, choose a destination and a published
   writer, and **Attach maintenance**. `/x/...` can bind a cell or overlay result.
   A document composition suggests the Nenex writer and installed Codex provider;
   a plain composition requires an explicit writer. Providers are optional.
5. Inspect the work cell, attempts and output. Pause, resume and detach use the
   same native operations as other namespace clients.

These forms call `namespace_command/plan` and supervisor admission. They do not
run Python commands or maintain a browser-owned work queue.
`authoring.grove` declares publication and the **Declared authoring actions**
view. Browser and headless clients invoke those declarations through the same
native planners. Existing contextual forms remain available beside them.
Accepted actions refresh the surrounding controls when local drafts allow it;
unsaved source and Goo input are retained.

### Declared authoring actions

Open **Page tools → Flows → Declared authoring actions**. The view is
`/0x11/gov/flows/authoring/author_flow`, selected by the
`/0x11/gov/flows/authoring/authoring` slot. Publication keeps its separate
`publish_flow` view and `publication` slot.

The declared controls cover these existing operations:

| Work | Controls |
| --- | --- |
| Author source | Create Semidoc page; Save Semidoc source |
| Compose | Inspect callable definitions; Select callable; Compose selected callable |
| Use a definition | Select published flow; Embed selected flow; Adopt selected publication |
| Bind evidence | Bind Nenex evidence; Bind filesystem evidence; Bind web evidence |
| Maintain work | Retry revision; Pause occurrence; Resume occurrence; Detach occurrence |
| Investigate | Open investigation; Delegate native work; Retain unresolved question |

**Create Semidoc page** takes a page name and complete source, and creates
`/0x11/app/nenex/w/<name>` only when that destination is empty. It does not append
`_flow` to the name. **Save Semidoc source** edits the current page. Source and
composition edits preserve the existing document attachment guards; publishing
and adopting a definition remain separate actions.

Composition's `bindings` field is a JSON object mapping each selected port to a
named input or prior step, for example `{"value":"evidence"}`. Embedding's
`bindings` maps each selected input to a namespace path, for example
`{"sources":"/x/0x11/app/nenex/w/research/cells/source"}`. Supply exactly the
selected ports: missing ports, extra ports, duplicate keys and non-string values
are rejected. Selection version and definition fields must identify the retained
selection cell. `new_inputs` is a space-separated list of explicitly named inputs.

**Open investigation** accepts `context` as a JSON object from evidence keys to
live namespace paths, or `{}`. It creates the existing document-local work and
context lens. **Delegate native work** takes an existing activity, a new worker
name, an explicit provider and an explicit guard path. Choose independently
guarded evidence whose changes should invalidate that worker, outside the work
it will edit. Select the Codex surface provider only for
an intentional interactive investigation; ordinary prose revision retains its
bounded response policy. **Retain unresolved question** uses the existing hole
operation with a live context path and an open activity to resume.

Headless callers discover control addresses, input fields and version tokens
from Goo, then submit those exact fields through its action protocol. Reinspect
after a mutation or stale result. The Semidoc `source` fields use the existing
multiline `rich-code` editor and are reflected as `rich_text`. Their wire value
is the JSON text produced by `goo_text/encode (goo/text/en source)`, for example:

```json
[{"myth":{},"lang":{"en":{"txt":";. /example\n  ;= Example\n    Authored source."}}}]
```

The browser supplies this encoding. A headless caller passes its serialized
text as `input:/source`; it must not pass raw Semidoc as that field. The adapter
requires empty run metadata and joins the text without discarding formatting
silently. `bindings` and investigation `context` remain ordinary string-valued
JSON objects, independent of the source editor's encoding. These adapters plan
through the existing flow, Nenex and Cooperate operations; retained definitions,
cells, attempts and history remain their native records.

### Compose in Nenex

**Discover native operations and reflected definitions** captures a namespace
subtree in an ordinary cell. The default scope contains published flow operations;
compiler mirror subtrees expose their existing native type descriptors, source
and decompiled laws. Declared flow inputs are shown with a selection control that
retains the historical callable. Reflection alone does not grant a raw function
effects or invent an input contract: those require a declared flow operation or
Goo control. Inspection uses the existing capture size limits; inspect a narrower
module subtree when a large compiler mirror exceeds them.

Choose **Compose an operation or child flow**, name the selection, and supply a
published operation or flow path. The callable's kind is explicit. Selection
captures the exact native record in `<page>/cells/<selection>` and the form shows
its declared ports. Each port binds to a named flow input or an earlier step.
Declare any new input names, choose the step name and result, then **Save composed
step**. Reusing an existing step name revises that step.

This edits the existing Semidoc AST through the source editor's native guards.
It preserves unrelated explanation, relationships, repeated bindings and named
work. The whole resulting procedure must compile before the edit is admitted.
The source uses native `/h/x/<case>/<length>/...` references for selected laws;
later publication of the original callable does not retarget them. Publish the
edited procedure separately. To adopt newer behavior, select it explicitly and
revise the step. Editing a flow leaves its existing published definition and
attempts intact until publication.

### Extract a retained run

Page tools show **Extract retained run** for retained previews and completed
automatic runs beneath the page. Choose executed top-level steps and a new flow
name. Extraction creates an editable Semidoc page, the original attempt's
provenance cell, and captured example cells for dependencies outside the selection.
Those cells populate the existing input defaults; the binding fields can select
different evidence before invocation.
The procedure retains original dependency order even if the selection is entered
in another order. Publish it and bind new inputs through the ordinary controls.

Extraction references each exact historical operation or child definition; it
does not copy an operation registry. Missing historical origins, mismatched laws,
unknown or unexecuted steps refuse. Nested calls remain child invocations.
Provider answers remain evidence: they are not turned into hardcoded replay
steps. This is extraction from the existing typed execution trace, not automatic
inference of a procedure from arbitrary agent or user activity.

### Draft a flow from retained work

On a page with Cooperate work, **Page tools → Flows → Extract investigation**
shows its linked retained events in their original order. Select event names
and create a new flow. The selection is checked against the investigation's
sequence; a changed sequence, missing event, duplicate selection, malformed trace,
or occupied destination refuses without creating a partial draft.

Delegated model workers beneath an investigation expose **Extract agent trace**
in the same page tools. Select their native tool-call events to draft from what
the agent actually did. Each selected event retains its exact work record,
including its native effect reference and settled outcome. The tool calls are
examples for authoring; extraction never replays their effects.
Pending tool calls refuse extraction. Failed calls remain selectable evidence
of what was attempted and how it failed.
The sequence counts appended events, not tool settlement. Extraction checks
settlement at admission and captures that settled version; it does not certify
that a result was visible when an earlier form was rendered. Inspect the
resulting draft's captured examples when authoring its procedure.

The draft is ordinary Semidoc. Each selected event has an `evidence_N` input,
a frozen provenance cell, and an example input cell. An explicitly recorded
artifact supplies the example when available. Investigation notes otherwise use
named captured context or inert note text; model tool calls retain their settled
task record. References in the draft point to the provenance cells. Subsequent
changes to the original evidence do not rewrite those examples. Unselected
events are not copied.

The draft deliberately has no executable steps or result yet. Use the existing
callable selection and composition controls, or edit the Semidoc source, to
choose operations, dependencies, and the result. Nothing treats a tool result
or a note as executable code. The ordinary compiler rejects an unfinished draft.
A native authoring hole watches the draft's source. **Review extracted procedure**
checks that the procedure compiles and acknowledges that hole; another source
edit reopens it. Review does not publish or execute anything.
Review and publication forms carrying an older authored source refuse. A change
to the original evidence does not invalidate its frozen example or silently
rebind it to the new source. Live bindings on an occurrence are checked by the
existing work and publication guards when that occurrence executes.

Publish separately, then select and embed the definition in any Nenex document.
Its binding fields can use new evidence instead of the retained examples. The
same maintenance hand, cells, overlays, holes, and attempt history apply.
For a document revision, author a `/flow/page` brief with its `/flow/uses` keys,
then compose the native `revise` operation with `pages` bound to `document` and
`sources` bound to the chosen evidence input. On the host page, **Bind Nenex
source page** creates a live cell at `cells/KEY_source`. Bind an extracted input
such as `evidence_1` explicitly to `/x/<host>/cells/KEY_source`; the source form
only supplies a default for an input named `sources`. Leave the provider empty
for manual revision. **Open draft**, save the authored prose, and **Accept saved
draft** completes the same native work. Editing the evidence page requests a new
revision while retaining the earlier attempt and published document history.

Extraction supports explicitly recorded Cooperate investigation and delegated
model-worker traces, up to 16 selected events per draft. It does not infer
dependencies or capture arbitrary unrecorded browser/agent actions. Retained
flow runs continue to support exact executable extraction through **Extract
retained run**.

### Declared Goo actions in work

Use **Page tools → Flows → Inspect declared Goo actions** to inspect an object
and its published view. Inspection retains their native records in an ordinary
captured cell. The document shows the declared action labels, argument bindings,
and input controls. Declared rich-text inputs use Goo’s existing encoder, so
the form accepts ordinary prose. **Select action for a flow** prepares a captured action cell;
bind its `/x/.../cells/<name>` value to the `actions` port of `request_actions`.
Inspection and selection do not execute anything. A stale inspection is refused;
inspect again deliberately to select changed behavior. Controls requiring Goo
selection captures are shown but must use the existing Goo selection interface.

`request_actions` describes native work. Its provider hand emits a `writ/warp`
for the published `execute_action` namespace operation. Shared admission consumes
that emitted command after the current reaction cascade settles. It checks the
current request, exact evidence capture, hole head, controller/claim, selected
arguments, receiver, view publication and declared Goo bindings before admitting
any effect. Paused, detached, superseded or stale work cannot execute through this
hand. Refused preparations retain a failed outcome and unresolved hole; changed
evidence or an explicit retry uses the existing request lifecycle.

The effect and Goo invocation receipt are planned together through the existing
Goo interpreter and namespace admission. The hand observes that exact receipt,
retains an ordinary result cell, and lets the flow consume the outcome in its next
step. An exact repeated invocation does not repeat the effect. All commands and
reactions share admission's existing bounded transaction; failures discard its
candidate namespace and index. There is no action foot, polling loop or external
work queue. Reading a cell never invokes an action.

The action's argument preview is captured; execution uses the current declared
implementation under Goo's publication guards. Native action work supplies time
zero, as before; it does not introduce an ambient clock. The receipt records
acceptance, invocation identity and receiver path. It is not a claim that the
receiver remained unchanged afterward. The existing receipt journal capacity
still applies. An independently submitted Goo request has ordinary Goo authority;
the work guard does not globally revoke copies submitted outside this hand.

Goo's publication guard versions the `/gov` subtree. Attach the flow before
preparing its actions if attachment changes publication claims. Reusing a
receiver in another action requires preparation against its appropriate revision.
The catalogue reflects compiled Goo declarations; it is not a general PLAN
function browser or automatic preparation of an arbitrary GUI action sequence.

### Embed a published flow on another page

On an existing Nenex page, use **Page tools → Flows → Select published flow**.
Give the occurrence a name and the published definition's namespace path, such as
`/0x11/app/nenex/w/source_outline_flow/flows/source_outline`. Selection captures
that exact publication in the ordinary cell `<page>/cells/<name>` and shows its
input ports. Bind those ports, choose an output path and writer, optionally select
a provider, then choose **Bind and embed flow**.

Attachment and the guarded source edit are admitted together. The added Semidoc
reference uses the existing document embed vocabulary:

```text
;@ /doc/embed ;/0x11/gov/flows/occurrence_view
;/0x11/app/nenex/w/project/work/outline
```

The occurrence is the existing maintenance controller at `<page>/work/<name>`.
Its inline view exposes the same bindings, work cell, working overlay, attempts,
holes and retry actions as Page tools. Two occurrences can select the same
definition with independent inputs and output destinations. Live input changes
wake their existing hands; reading the embedded view does not dispatch work.

Selection retains the definition's exact historical reference. Republishing the
original flow does not change it. Existing **Attach maintenance** controllers keep
their live-publication behavior; both modes retain each attempt's definition.
To adopt a newer publication, select it into a new captured cell on the same
page, then supply that cell to the occurrence's **Adopt selected publication**
control. The command guards the previously selected definition and requires the
same definition address and input names. Destination, input bindings, captured
writer and provider stay with the existing controller. A changed input contract
requires a new occurrence with explicit bindings.

Adoption invalidates current resolution records and pending job references;
native history, old attempts, captures and the old selection cell remain retained.
The existing hand evaluates the adopted definition, and stale attempts cannot
satisfy it. Paused occurrences stay paused. Adoption cannot reattach a detached
controller; create a new named occurrence for that case.

Removing the reference in source or Goo removes the presentation only. Named
cells and work survive document edits and remain discoverable in Page tools.
**Detach and retain history** releases the destination claim and subscriptions while
retaining attempts, captures and history. The output must not overlap the page's
controller subtree, so choose a separate output document when using the Nenex
writer. Selection and controller collisions are refused rather than overwritten.

### Nenex pages as live evidence

For a document revision flow, create and edit an evidence page in Nenex. On the
flow's authoring page, use **Bind Nenex source page**, giving its namespace path
and the evidence key declared in the procedure's `/flow/uses`. This creates an
ordinary spun cell at `<author>/cells/<key>_source` and fills the `sources` input
with `/x/<author>/cells/<key>_source`. Publish and attach using the same page tools.

The cell reads the page's local `x` value. Its source envelope cites the exact
native historical `x` reference; it does not pretend the page is a captured file
or manufacture a SHA-256 digest. Existing native dependency tracking wakes the
maintenance hand when the page changes. Frozen attempts retain their old source
snapshot, draft, overlay and response. An empty revision result leaves a persistent
hole; **Retry revision** creates a linked attempt, and changed evidence resumes
through the same shared lifecycle. There is no page-source hand or scheduler.

The native operation is `bind_page_source` at the author page, with a live `x`
`source` reference and a one-segment `name` path. Rebinding the same source is
idempotent; an occupied cell is refused rather than overwritten.

### Filesystem and HTTP sources

The example catalogue includes **Evidence sources**, **Source outline** and
**Web source guide**. Create and publish Evidence sources before publishing Source
outline; the outline invokes that reusable procedure. Open the examples from Page
tools, save/publish their Semidoc, bind their sources, and
attach it with the existing Nenex writer. The examples are procedures rather
than separate applications or Python launchers.

**Bind filesystem source** selects a captured Markdown record and its existing
filesystem mount. It calls `watch_sources` with `source`, `mount`, `expected`,
a one-segment `name`, and `format: md`. The resulting source cell fills the
`sources` input. Its origin is the exact native historical file reference;
no generated JSON bundle or SHA-256 adapter is needed. The filesystem foot
retains ownership of polling and cancellation. Shared consumers keep the watch
alive. Missing files and detached feeds expose no current evidence; their last
captures and historical records remain.

**Bind web source** writes an ordinary named URL input and fills `urls`.
`web_fetch` declares a native work request, `web_sources` converts an accepted
response to a source envelope, and `decompose`/`documents` prepare the output.
The HTTP foot performs bounded native `Fetch` calls. It owns transport only;
the shared hand owns attempts, guarded completion and retry. Requests already
pending at restart are marked interrupted rather than silently replayed.
Changing a URL input's `revision` slot explicitly requests another capture.
There is no HTTP polling scheduler. HTTP errors remain failed attempts and do
not become current evidence.

The first HTTP flow supports named GET requests and Markdown decomposition.
HTML and other supported text remain literal evidence. Search-engine choice,
registry-specific interpretation, PDF/CSV adapters and source-file write-back
are not implemented by these examples; they require explicit operations and
authored procedures, not an implicit research daemon.

### Native provider steps

Pure operations can return the existing `flow/judgment` task tree containing
ordinary cards with `work/prompt`, `work/schema`, optional `work/provider`, and
optional `work/evidence` (`cell_view`). The evaluation suspends as `flow/pending`.
Document revision tasks keep their existing typed document adapter.

Native request attempts live in the controller's existing `work` subtree.
They retain their definition and task, expose frozen evidence and a live lens,
and use `native_work_ops/dispatch`, provider outcomes and subject-owned holes.
Only the current hole head with matching captured evidence can publish a
resolution. Returning to an earlier equal input does not revive an obsolete
attempt. A failed request stays retained; **Retry work** creates a linked attempt.
Successful steps yield `work/outcome`, a pinned `work/result` reference and the
attempt path for subsequent pure operations. Reading cells never starts I/O.

Native reverse-reference and graph views can supply the same input/context
bindings. Their sovereign-state index changes the core `sov` contract. This
integration is validated in disposable worlds; mounting the flow code is not
an upgrade mechanism for an older retained kernel. No bootstrap patch or
automatic conversion of existing worlds is supplied.

## Definition contract

A section marked `/flow/definition NAME` contains a composition.

| Attribute | Meaning |
| --- | --- |
| `/flow/input NAME` | Named namespace-tree input. |
| `/flow/step NAME ;/operation/path` | Invoke a published native operation. |
| `/flow/invoke NAME ;/document/flows/definition` | Invoke a captured published flow with explicit port bindings. |
| `/flow/bind PORT VALUE` | Bind a port to an input or preceding step. Repeat for each port. |
| `/flow/result NAME` | Select exactly one returned value. |
| `/flow/page RELATIVE_PATH` | Declare a document template or editorial brief. `/` is the root. |
| `/flow/uses SOURCE...` | Declare the evidence used by a document brief. |

The reserved `document` binding holds authored pages. The `documents` operation
uses them as final templates; `revise` uses them as briefs requiring judgment.
The `identity`, `inventory`, `decompose`, `documents`, `revise` and `evidence`
operations are independently published. `decompose` is a bounded Markdown import
operation; it is not an intermediate editing model for Nenex.

### Composing published flows

Publish the child from Nenex first, then refer to its definition in the caller:

```text
;@ /flow/invoke checked ;/0x11/app/nenex/w/evidence_sources_flow/flows/evidence_sources
;@ /flow/bind sources sources
;= Validate the bound evidence
```

Each repeated `flow/bind` supplies one child input. Later steps can bind the returned
value by the invocation's name. Publishing the parent captures the selected child
definition and its native laws. Republishing the child leaves existing parent
definitions and attempts intact. A plain live path selects its current publication
when the parent is republished; an explicit historical path stays pinned until the
authored reference changes. Nenex's composition controls author historical paths.

The evaluator runs the child in authored order inside the same parent invocation.
Each nested step gets a distinct identity, so two calls to the same procedure have
separate resolutions and holes. Pending child work stops evaluation until the
existing hand accepts a current result; retries and stale-result rejection use the
same work lifecycle. The trace retains the child definition, bound inputs, child
steps and call result as separate events. The parent's selected writer applies the
final output. Eight nested calls and 128 total executed steps bound expansion.

Revision drafts carry Semidoc source. A writer may declare its native document form
in `flow/document`; attachment captures that declaration with the selected writer,
and revision requests retain it. The Nenex writer supplies its document form through
this boundary. A writer without it gets source-only drafts. Pinned contract shapes,
including the optional pages payload in `flow/definition`, are unchanged.

The implemented composition is ordered and acyclic. Publication checks names,
bindings and port names and captures the chosen laws. General branching,
and inference from arbitrary exploratory traces are not implemented here.
Declared Goo actions run through shared hands and native admission.
Limits are 16 inputs, 16 steps and 32 authored pages. Names are canonical symbols
up to 64 characters. **Edit source** authors executable declarations; Nenex's Goo
editor preserves those declarations when editing text or moving their blocks.
Repeated bindings occupy one native predicate slot with ordered, typed
occurrences. Their port/value pairs and reference values survive the round trip.

Pure compositions support native `preview` and guarded, idempotent `commit`.
Judgment-bearing compositions use `follow`; a pure preview refuses pending
judgment with `flow_revision_requires_follow`.

## One native work lifecycle

Investigations, answering, document revision and providers use `native_work`:

- `attempt` opens an activity with its captured reading. `event_record` and
  `append` retain the controller's attempt history.
- `dispatch` records the exact provider request on the attempt and creates its
  worker in the same card batch. Repeated dispatch is a no-op; a different request
  cannot reuse its receipt. `start_provider` also serves direct investigation
  delegation.
- `result` freezes a provider outcome once. A late or repeated completion cannot
  replace the retained result. `check_outcome` checks successful execution and
  the captured guard's identity, including its observed case.
- `settle` updates the native activity and reason. A document adapter validates
  document structure and task freshness; answering validates answer structure;
  investigation completion checks its selected evidence. Those are domain
  admission policies, not separate provider lifecycles.
- `retain_hole` keeps a demand on its subject. Its existing hand observes the
  selected live lens and wakes the owner on changed evidence. Attempts retain
  their frozen reading; a resolved hole can reopen.

Flow job flags and answering's old settled field retain their stored layouts for
compatibility with their pinned native contracts. New executions do not use them for dispatch or
settlement: request and worker records own those decisions. Controller serials identify domain requests; the native activity
records their history. No new scheduler, queue service or persistence layer is
introduced.

Current work is selected by the controller's existing crew: exact request and
guard records, current worker subtrees, and document drafts. Retained attempts are
not dispatch candidates. Allocation temporarily probes only the prospective
attempt paths through the same crew before writing them, preserving collision
checks without reading all prior attempts. Replacing a demand settles its active
old attempt; late provider evidence remains retained but cannot publish for the
replacement. Detach releases owned hole subscriptions as well as the controller
subscription and destination claim. Another consumer of the same evidence keeps
its own subscriptions.
Cells displays completed revisions from the existing retained-request projection;
the hand continues to select only current jobs and live hole heads.

The Codex hand owns app-server dispatch and stable turn completion. Its Python
companion transports bytes and owns the child process. On restart an interrupted
external turn becomes a retained failed outcome through `native_work`; uncertain
external execution is not silently replayed. Changed evidence can create fresh
work. Manual document admission remains available for an unresolved revision.

## Document revision adapter

`inventory → revise → evidence` is a document-maintenance composition. Each
brief declares source dependencies. A matching accepted resolution is reused;
changed briefs or selected evidence produce a new request. Model work is serial
per controller. Identical evidence does not retry a failed or unsupported result.

Use **Retry revision** in Nenex Page tools → Flows to explicitly retry a refused
current request. The published native `retry_revision` operation takes the request
path as receiver and its `expected` x case as input. It stages a fresh monotonically
numbered attempt through the same hand, carrying the saved working draft and
linking `/work/retry_of` to the original. The subject keeps its existing hole; the
failed request, evidence, worker outcome and history stay unchanged. Repeating a
retry creates no additional work. Paused, detached, active and obsolete requests
are refused, and replaced attempts cannot submit a late result. Flow details
expose the retained provider failure message for diagnosis.

A request beneath `<controller>/work/revision_N` has an actual Nenex `draft`,
`instructions`, frozen `evidence` and `prior`, a draft `guard`, and a spun `view`.
The view composes the document, brief, prior state, frozen evidence and live demand.
The provider receives the guarded draft's current source. People can edit the same
physical draft and use **Accept saved draft**. Late output cannot overwrite edits
or satisfy another captured task.

Revision results contain `source` and `note`. An empty source leaves a reasoned
hole. Accepted source contains one Semidoc section with inert prose, subsections,
items, quotations, literals and valid rich text. References and executable
attributes are currently rejected. This adapter authors documents; it does not
claim to generate arbitrary executable embedded blocks or establish factual truth.

The writer publishes when all required revisions are ready. It protects edited
generated prose, refuses collisions and page removal requiring migration, and
preserves named notes, cells, work and holes. A destination claim prevents
competing maintainers. Paused and detached controllers retain their evidence.
The writer shares Nenex's source-edit attachment guard: named work beneath
numbered prose prevents structural replacement, while safe text edits remain
possible. Native authoring and source/Goo editing enforce that same rule.
Old attempts keep their captured definition and inputs after later edits.
The maintenance projection at `cells/maintenance` is owned by its controller:
refreshes preserve annotations, foreign cells refuse adoption, and custom
writers cannot publish into this reserved projection.

Goo, native command admission and installation share `namespace_command`
planning/cascade admission, including the same bounded 128-round cascade and
atomic refusal policy. Browser and MCP entry points do not choose separate
reaction limits.

## Handbook example

First use **Page tools → Flow examples → Create Evidence sources reusable flow**
and publish its `evidence_sources` definition. The handbook and Source outline
both invoke this published procedure.

**Page tools → Flow examples → Open or install handbook example** explicitly
creates the authoring page and repository capture feed. Publish the definition,
then bind sources and attach maintenance. An existing handbook is opened without
replacing its authored source or history. Its declared input defaults and capture
control live in the page's named `flows/defaults` child, preserving its Semidoc source.

`examples/handbook.semidoc` holds its briefs and dependency declarations.
`examples.json` declares its repository files, source page, input defaults and
optional capture setup. These remain
in the existing flows extra; the Nenex integration registers the example actions
without instantiating them. Native command installation does not read the catalogue.

Repository capture is host I/O. `host.py` stages each declared file's exact bytes.
Native source hands expose each file beneath the authoring page's `inputs/sources`;
the existing merge cell at `cells/sources` combines their named evidence. The
handbook's declared source dependencies prevent publishing concepts whose required
evidence is missing.
Missing files are omitted from the current scan; they do not prevent installing
or recompiling the harness in another workspace. Each source hand retains its last
good capture. A feed requires its live file to appear in the configured mount's
current scan report and not in its missing-file list. Retained bytes and an old
successful report are not current evidence. Returning identical bytes restores
the feed without deleting its prior captures. Reading a cell never launches a model.
Other flows can bind namespace evidence directly or use native `watch_sources`
to connect one live file under a filesystem mount's destination to a feed.

The filesystem foot reconciles its owned watcher actors whenever its native
binding changes. A capture configuration has one polling actor, shared by all
source feeds bound to it. `watch_sources` attaches a feed or, with its current
native `expected` case, rebinds it. `unwatch_sources` takes that same case guard
and removes the live dependency while retaining the feed, last good capture and
history. Ownership is derived from the existing native dependencies, not stored
in a second owner table. Rebinding releases the old configuration only when no
other source feed still refers to it. Pausing a maintenance controller does not
remove its authored source binding.

The existing configuration retains its interval (`fs/watch_seconds`, default
15 seconds for a newly attached source); `fs/watch_active` records whether its
source bindings still require polling. Removing or changing a configuration
cancels its old actor. Every read needs permission from the foot, with at most
one second between idle cancellation points. An in-flight I/O call may finish,
but its obsolete generation cannot publish. A completion also checks the exact
native configuration assertion inside ordinary supervisor admission, then lets
the existing filesystem hand apply the request and result in one atomic batch.
Two matching captures stabilize changes; unchanged captures produce no event.
No work queue or scheduler is added. Captured records and all x/y/z cases remain.

The disposable-world gate is `tests/check-watch-lifecycle.py` (run with `WISP`
set, or from the core development shell). It uses real file deletion/restoration,
two authored flows sharing a capture, rebind/detach/reattach, read counters after
cancellation, and a deliberately blocked read released after detach. The Python
test driver only changes fixture files; the native supervisor, filesystem foot,
source hands and cells perform the lifecycle. The core `tests/fs_reconcile` suite
also checks the worker's termination acknowledgement and rejection of late
results after an ABA detach/reattach. These tests never open a retained live world.

The small `examples/evidence_resume.semidoc` demonstrates a persistent demand:
missing `GATE_OPEN` evidence leaves a hole; changed relevant evidence resumes it
through the same hand. No wall-clock work scheduler is involved.

## World and operations

Eden saves the complete namespace through its native continuation before
acknowledging writes. Documents, cells, holes, captured laws and work history
restore together. `x/eden` uses `$XDG_DATA_HOME/shrine/worlds/NODE` by default;
`--world PATH` selects another world. Restarts reconnect I/O; completed work is
not replayed. `--ephemeral` and `--check` use disposable worlds.

Source publication and installed runtime bindings are distinct in the existing
mount system. After publishing changed modules, reconnect the HTTP foot with a
restart and use **Page tools → Flows → Refresh harness code**. This uses the same
registration records as initial installation and admits only changed code records
in one native batch. Flow refresh owns flow behavior and its Nenex contribution.
Cooperate and Nenex activate their own hands, document forms and reader; a flow
refresh cannot roll those dependencies back to its captured imports. It does not
replace the supervisor's captured Goo interpreter. It does
not reinstall application seeds or examples, or change controllers,
captures, destination claims, documents or holes. The native operation is
`/<node>/gov/flows/refresh_harness` at `/<node>/gov/flows`. Older worlds need one
initial refresh through the updated flow HTTP handler before their stored page
tool displays the new control. Captured definitions and old attempts retain their
chosen laws. Refresh refuses `flow_runtime_requires_type_migration` when live
controller, claims, question or hole records belong to another nominal type
moment. Persistent contracts are imported from the mount's explicitly selected
`pinned_modules`; source scans rebuild their separate `_ops` implementations.
Once a contract artifact exists, refresh does not read its bootstrap source or
infer identity from a matching schema. The original module root, type moments,
and captured dependency graph remain exact. An older combined module can supply
these types too, so retaining existing work needs no record rewrite.

A deliberately republished contract has new nominal identities. The compatibility
guard still refuses an incompatible activation. Retained providers and current
implementations use the same pinned declarations and their ordinary methods;
there is no cross-revision method fallback or automatic type reuse.

Publish dependencies before their consumers. For Semidoc this includes Web,
Explorer, Nenex, then flows. An unchanged mount-file snapshot skips compilation;
when only an imported library changed, invalidate that mount's native
`/sys/fs/source/snapshot` cache before invoking its existing `op/rescan`.

An existing saved service captures its compiler and core runtime. Restart resumes
that service; publishing mount records does not replace its captured core code.
Bootstrap law patching, `x/eden --upgrade`, and the experimental whole-service
activation API have been removed. The compiler corrections described above apply
to services built with this checkout; ordinary mount publication does not install
them into an older saved compiler. See [the publication boundaries](../../../MOUNTS.md).
Validate core changes in disposable worlds. Republish a flow definition to select
new operation laws; existing attempts retain their pinned definition and writer.
An already captured refresh command still supplies its old registrations. Use
the newly published law, or the handler selected from saved mount images on
restart, to refresh native behavior records. That does not replace the core service.

Operations under `/<node>/gov/flows/` include `author`, `publish`, `preview`,
`commit`, `follow`, `submit_revision`, `set_enabled`, `detach`, `import_source`,
`observe`, `source_failed`, `watch_sources` and `unwatch_sources`. They use existing namespace
admission. Native callers do not require MCP; external callers may use the
existing generic MCP transport. Clients with unrestricted raw namespace writes can
bypass this protocol; the helpers are not an isolation boundary against them.

## Source organization

`install.foil` assembles the native command/law catalogue without importing Nenex
or examples. `sources_ops.foil` owns only source feeds and filesystem ownership.
`nenex_ops.foil` owns page authoring, page-as-evidence binding and the Nenex writer.
`interface.foil` contributes those adapters and forms to Nenex; `examples.foil`
registers optional authored recipes. The mount still packages backend and Nenex
integration together. Public command addresses and pinned contracts are unchanged.

The handbook CLI workflow and bundle adapter have been removed. `tests/client.py`
is only the transport helper used by disposable integration tests. Filesystem
evidence uses native captures directly. See `../../HARNESS.md` for the selected
document-form boundary, captured child-flow composition and its current limits.
