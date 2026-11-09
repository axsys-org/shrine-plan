# Flow authoring in Nenex

Select `flow-authoring` to add the Nenex/Goo document interface to the native
[`flows`](../flows/README.md) executor. The mount depends on `flows` and `nenex`.
It adds no scheduler, separate work store or background provider process.
The optional Goo action adapter currently ships in this package because its
declaration interpreter is Explorer-owned. Thus generic headless flow execution
is independent of Nenex, while selecting these Goo actions still selects this
integration and its Nenex dependency; packaging them independently remains work.

The existing `/gov/flows/authoring` controls author and publish Semidoc, compose
captured operations, attach occurrences, inspect declared actions and turn
selected retained traces into editable source. Their namespace operations,
receiver guards, cells, holes and attempts are the same ones used by headless
invocation. `/gov/flows/nenex` supplies the final writer and the captured draft
writer; the latter applies Nenex's existing source/attachment protection.

Attach inputs to the values they consume. A computed evidence collection lives
at `/x/<cell path>`; the physical cell record describes the computation. Inspect
the computed collection before attaching. An occurrence keeps its original
bindings. Use a fresh selection name to replace bindings or a detached occurrence;
the previous controller, captures and attempts remain addressable.
A retained `work/<run>/result` belongs to that run even when read through `/x`.
Use `/flow/invoke` with current source inputs when a maintained flow must rerun
a captured child definition. Reading an old result does not subscribe to future
runs of a separate occurrence.

`bind_page_source` accepts named documents inside a conversation wiki as well as
top-level pages. It projects the selected document's current Semidoc into an
ordinary source cell and records its exact historical origin. A missing document
produces no current evidence. For example, bind an owner's clarification as
`policy`, decode a separate JSON collection, then invoke
`/gov/flows/operations/combine_sources` with `left` and `right` before `revise`.
Include both source names in `/flow/uses`. The pure operation validates both
collections and refuses duplicate names; it does not fetch sources or own work.
These names are the source collection keys, not the input port names: binding
an `owner_policy` source collection to a `policy` input still requires
`/flow/uses owner_policy`.
Changes to either binding wake the existing maintenance hand, while each attempt
retains the policy and data it actually read.

Interactive requests with captured evidence expose it as an ordinary frozen cell
at `<request>/context`. Read `/x/<request>/context` to inspect the exact evidence
given to that attempt, selecting branches and paging through children. The
provider prompt carries this address instead of repeating the whole evidence
tree. Later wiki edits and retries do not replace the earlier cell or its history.
An admission rejected before a request was allocated has no such cell; inspect
the occurrence's reason instead (`flow_prompt_limit` identifies oversized
instructions).

The vocabulary and authoring Grove units share this mount's publication owner.
Public addresses and logical module names remain unchanged. Persistent flow
contracts remain in `flows`, so installing document integration does not create
another nominal version of work records.

Refreshing the flow commands checks the existing destination claims, their
controllers/views and bound source feeds. It does not validate or replace
unrelated answering, Nenex or provider behavior. Orphan source records are
validated by their source hand when it reads them; an unrecognized retained feed
is left untouched and yields no current evidence, rather than being rebranded.
A refresh does not update a
captured attempt's writer or replace a running world's reader/compiler.

A revision with a document form but no captured draft writer is refused. A newly
selected writer applies to newly attached work; historical attempts retain their
original values. The executor never borrows a current writer to rescue an old
capture. For application-independent requests, no document form is required.
Existing controllers have no writer-policy update operation; selecting new
policy needs a new attachment. A retained publication receipt can also require
a new destination, since provenance handoff is not implemented.

Use `extras/x/check --mount flow-authoring --suite flow_document_boundary_tests`
for document guards and `--suite flow-authoring-only-tests` for the compiled Grove
surface. Integration test fixtures may select examples or controlled providers;
those selections do not become runtime dependencies of the native `flows` mount.

HTTP source work is optional: select [`flow-web`](../flow-web/README.md) separately,
or use `flow-examples`, which selects both integrations.

## Attach a captured flow

Use **Select published flow** on the containing page, choosing a stable occurrence
name. This captures the exact published definition in `<page>/cells/<name>`.
Open that cell's **Attach selected flow** Goo view. Its only inputs are the result
destination, writer, optional provider, and port-to-evidence bindings. New
selection cells include a JSON binding template derived from their captured
ports; native validation always checks the captured definition itself. The
selection cell is the guarded action receiver. No source text or definition
version has to be copied into the form.

The controller lives at `<page>/work/<name>`, the same address used by embedding
that selection. Repeating an identical attachment reuses the controller.
Replaying an embed with current source guards leaves an already present
reference unchanged. Changed requests are conflicts; detached work is not
reactivated. Removing a reference does not silently authorize a retry to add it
back. Existing pause/resume, detach and deliberate adoption operations retain
their roles.

Binding identity compares slots and values, independent of map construction
order. Retained request maps and captures keep their original representation.

Selection captures remain pinned when a definition is republished. Deliberately
select another publication to adopt it; refreshing a form does not replace the
captured contract. The form's binding template is advisory presentation metadata
on the existing cell, not a second definition or a catalogue.

## Connect an action to cells and a wiki

**Inspect declared Goo actions** still creates a frozen catalogue at
`<page>/cells/<name>`. Each declared action now retains the existing native
receiver contract, its Grove argument schema when present, the action declaration,
and exact view/action references plus the receiver-role record observed during inspection.
The observed role is documentation context; the retained view contract is the
actual receiver constraint, not an inferred match to that role record. These are native values and
historical references, not a separately authored schema. Inline `poke` controls
have no independent action declaration and cannot be the subject of this lens.

**Connect action context** selects a control from that catalogue and creates
another ordinary cell. Supply:

- **Catalogue** and **Control**: the retained catalogue name and its control path.
- **New context cell name**: an unoccupied name under this page's `cells`.
- **Wiki subtree**: the scope in which incoming native references count as evidence.
- **Additional bindings**: a JSON object from input names to namespace paths.
  For example, `{"calculated":"/x/0x11/app/quotes/cells/total"}` reads a computed
  cell; `/0x11/app/quotes/cells/total` reads its definition instead.

The new lens uses the same scoped-reference hand as conversations, now housed in
Cooperate. Its primary `subject` is the captured action declaration. `publication`
and `selection` retain the view and catalogue; `receiver` follows the live object.
Additional named bindings use normal native cell resolution. Reading `/x/<cell>`
projects these inputs together. Bind that projection to another flow's input with
the existing attach/embed controls. It is not a new execution environment.

For a concrete starting point, inspect **Publish flow** on a Semidoc flow page
using `/0x11/gov/flows/authoring/publish_flow`. Connect its control to a wiki subtree.
A Semidoc page in that subtree can refer to the action using an ordinary attribute:

```text
;. /publication_guide
  ;@ /about ;/0x11/gov/flows/authoring/publish
  ;= Publishing an authored flow
    Review the input names and repeated bindings before publishing.
    A publication selects a definition; existing attempts retain theirs.
```

That authored path is a navigable Semidoc relationship. To include this page in
native `/r` evidence, use **Set action relationship** on the page, give the
relationship a name, and enter `/0x11/gov/flows/authoring/publish`. This attaches
`safe 0 .x <action>` at `/work/about/<name>` on the same page record. It does not
rewrite its source or create a separate graph store. Reusing the name rebinds it;
leaving the action field empty removes it. Source and Goo text edits retain this
native attachment. Ordinary path links are not silently promoted to typed
references. More pages can refer to supporting definitions, output cells or preparation flows;
those references remain inspectable relationships. Only typed references to the
selected action or its descendants within the chosen holder scope automatically
join this lens, following the existing `/r` subtree semantics. Transitive
traversal and relevance policy belong in an explicitly authored flow.

`/r` supplies membership. The hand reconciles the lens's `evidence` bindings;
ordinary cell dependencies supply their current contents. Several references from
one holder select it once. Removing the last typed reference or deleting the holder
removes current evidence; restoration reconnects it. The lens excludes itself even
when the scope contains it. Additional bindings cannot overwrite its reserved
subject, selection, publication, receiver or evidence slots.

Connecting metadata tolerates a change to the displayed tree, since writing an
inspection cell beneath the page itself advances that tree. It still checks the
receiver's own record version, source identity, publication and control. It does
not refresh or replace the captured invocation request or its stricter guards.

Context changes do not invoke the action or replace its captured contract. Action
selection, argument preparation, invocation, receipts and stale guards retain
their existing behavior. Republishing an action requires deliberate rediscovery
before connecting a new context. Existing contexts retain their selected subject,
while live evidence continues to change; consumers still capture their reading in
each native work attempt. A reference to an action is evidence to inspect, not a
claim that a guide or another flow is compatible with every version.

Codex's existing `shrine_actions` also exposes the same schema, exact historical
read/documentation addresses, and `/r` navigation paths. It does not execute a
planner to infer business meaning or effects. Authored guidance and native
validation remain distinct; there is no new action registry or automatic binding
of a cell's value to an invocation argument.
