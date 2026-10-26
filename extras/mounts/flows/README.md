# Semidoc flows

A flow is an authored Semidoc composition of published native operations.
Definitions capture their operation laws; attempts retain inputs, intermediate
values and results. Cells expose that work and hands react to dependencies.
The generic installation publishes these capabilities without creating a
handbook, choosing its evidence, or attaching a provider.

## Author and run

With `flows` mounted, open Nenex and use **Page tools → Flows**:

1. Choose **Author a new flow**. **Composition** starts with an ordinary input
   and identity operation. **Document revision** explicitly selects the document
   adapter and its evidence/brief starter.
2. Edit and save the Semidoc source. Ordinary prose and literal examples stay
   inert. Only the marked definition is compiled.
3. **Publish flow** captures the saved definition and selected native laws.
4. Bind the inputs to namespace paths, choose a destination and a published
   writer, and **Attach maintenance**. `/x/...` can bind a cell or overlay result.
   A document composition suggests the Nenex writer and installed Codex provider;
   a plain composition requires an explicit writer. Providers are optional.
5. Inspect the work cell, attempts and output. Pause, resume and detach use the
   same native operations as other namespace clients.

These forms call `namespace_command/plan` and supervisor admission. They do not
run Python commands or maintain a browser-owned work queue. Generic Nenex embeds
and the shared Cells surface remain available to authored documents.

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
idempotent; an occupied cell is refused rather than overwritten. File evidence
continues to use its existing capture digest and source hand.

## Definition contract

A section marked `/flow/definition NAME` contains a composition.

| Attribute | Meaning |
| --- | --- |
| `/flow/input NAME` | Named namespace-tree input. |
| `/flow/step NAME ;/operation/path` | Invoke a published native operation. |
| `/flow/bind PORT VALUE` | Bind a port to an input or preceding step. Repeat for each port. |
| `/flow/result NAME` | Select exactly one returned value. |
| `/flow/page RELATIVE_PATH` | Declare a document template or editorial brief. `/` is the root. |
| `/flow/uses SOURCE...` | Declare the evidence used by a document brief. |

The reserved `document` binding holds authored pages. The `documents` operation
uses them as final templates; `revise` uses them as briefs requiring judgment.
The `identity`, `inventory`, `decompose`, `documents`, `revise` and `evidence`
operations are independently published. `decompose` is a bounded Markdown import
operation; it is not an intermediate editing model for Nenex.

The implemented composition is ordered and acyclic. Publication checks names,
bindings and port names and captures the chosen laws. General branching,
reflective extraction and model operation through Goo are not implemented here.
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
explicit native type reuse. New executions do not use them for dispatch or
settlement: request and worker records own those decisions. Controller serials identify domain requests; the native activity
records their history. No new scheduler, queue service or persistence layer is
introduced.

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
Old attempts keep their captured definition and inputs after later edits.
The maintenance projection at `cells/maintenance` is owned by its controller:
refreshes preserve annotations, foreign cells refuse adoption, and custom
writers cannot publish into this reserved projection.

Goo, native command admission and installation share `namespace_command`
planning/cascade admission, including the same bounded 128-round cascade and
atomic refusal policy. Browser and MCP entry points do not choose separate
reaction limits.

## Handbook example

**Page tools → Flow examples → Open or install handbook example** explicitly
creates the authoring page and repository capture feed. Publish the definition,
then bind sources and attach maintenance. An existing handbook is opened without
replacing its authored source or history. Its declared input defaults and capture
control live in the page's named `flows/defaults` child, preserving its Semidoc source.

`handbook.semidoc` holds its briefs and dependency declarations. `sources.json`
is its repository inventory. `examples.json` declares its source page, input defaults and optional capture
setup. These remain in the existing flows extra; the generic installer only
registers the declared example actions.

Repository capture is host I/O. `host.py` captures and hashes configured source
bytes. Missing evidence is published as a capture fault; it cannot prevent
installing or recompiling the harness in another workspace. The native source
hand retains the last good collection and blocks publication while a capture is
invalid. A feed requires its live file to appear in the configured mount's
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
in one native batch. This includes Nenex's declared document behaviors and reader;
it does not replace the supervisor's captured Goo interpreter. It does
not reinstall application seeds or examples, or change controllers,
captures, destination claims, documents or holes. The native operation is
`/<node>/gov/flows/refresh_harness` at `/<node>/gov/flows`. Older worlds need one
initial refresh through the updated flow HTTP handler before their stored page
tool displays the new control. Captured definitions and old attempts retain their
chosen laws. Refresh refuses `flow_runtime_requires_type_migration` when live
controller, claims, question or hole records belong to another nominal type
moment. Native source publication compares elaborated type schemes against each
source module's explicitly selected predecessor from that mount. It preserves
unchanged types' exact defining moments. Shared dependencies use pinned imports;
other mounts' structurally identical types do not replace existing identities.
Ambiguous predecessor selections are rejected.
The comparison keeps dependencies and opaque constants exact; a schema change
advances that type and invalidates reuse of its dependent types. Functions and
values are rebuilt, and publication still checks the actual current record cases
atomically. A new artifact's publication case is not automatically a new type
identity. Stored values and captured laws are not rewritten.
Method lookup also follows that exact native moment when a retained provider
returns a type through an older private compiler key. It uses the current
source-visible declaration; a different schema moment cannot supply its methods.
If identity fallback finds competing visible method keys it refuses the ambiguous
call. Multiple aliases of the same pinned method remain valid.

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
admission. Native callers do not require MCP; the optional CLI client uses the
existing generic transport. Clients with unrestricted raw namespace writes can
bypass this protocol; the helpers are not an isolation boundary against them.
