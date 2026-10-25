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
up to 64 characters. Use **Edit source** for executable definitions; preservation
of repeated executable attributes by every block editor is not guaranteed.

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
invalid. The example's ordinary filesystem foot watches every 15 seconds and
requires two matching changed captures. Reading a cell never launches a model.
Other flows can bind namespace evidence directly or use native `watch_sources`
to connect a captured source file and filesystem mount to a feed.

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
in one native batch. It does not reinstall examples or change controllers,
captures, destination claims, documents or holes. The native operation is
`/<node>/gov/flows/refresh_harness` at `/<node>/gov/flows`. Older worlds need one
initial refresh through the updated flow HTTP handler before their stored page
tool displays the new control. Captured definitions and old attempts retain their
chosen laws. Refresh refuses `flow_runtime_requires_type_migration` when live
controller, claims, question or hole records belong to another nominal type
moment. Native source publication compares elaborated type schemes against the
mount's retained artifacts and reuses unchanged types' exact defining moments.
The comparison keeps dependencies and opaque constants exact; a schema change
advances that type and invalidates reuse of its dependent types. Functions and
values are rebuilt, and publication still checks the actual current record cases
atomically. A new artifact's publication case is not automatically a new type
identity. Stored values and captured laws are not rewritten.

An existing saved service captures its compiler. After updating the native
runtime, stop its writer and use `x/eden --upgrade` to replace the private
bootstrap publisher, then restart normally and rescan the source mounts. The
native upgrade verifies the complete retained namespace content hash before
committing its continuation. It preserves compiler identity pins, documents,
work records and every x/y/z history; it does not reinstall the world.

Operations under `/<node>/gov/flows/` include `author`, `publish`, `preview`,
`commit`, `follow`, `submit_revision`, `set_enabled`, `detach`, `import_source`,
`observe`, `source_failed` and `watch_sources`. They use existing namespace
admission. Native callers do not require MCP; the optional CLI client uses the
existing generic transport. Clients with unrestricted raw namespace writes can
bypass this protocol; the helpers are not an isolation boundary against them.
