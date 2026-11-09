# Conversations are projected Nenex

A turn's user message and response are ordinary Nenex documents. The conversation
surface arranges their existing Goo projections inline; it stores no second copy
of the assistant's text or block tree. Open a reply as a wiki page and it is the
same content, with the same source/Goo editing, relationships and history.

The application binds each turn to an ordinary published flow with `context` and
`provider` inputs. The supplied `conversation_response` recipe is in
`flow-examples`. Its request step uses the existing interactive request hand;
its result goes through the existing guarded Nenex writer. Captures, cells,
provider outcomes, persistent holes, retries and tool traces belong to those
shared records. The conversation layer only allocates document addresses, binds
context and retains turn order and admission receipts.

## Use

Select the `conversation`, `flow-examples` and `codex` mounts in a disposable
world. From the Nenex example catalogue, create `conversation_response`. Publish
its `respond` definition with the existing page actions. Then open
`/conversation`, choose a new wiki page name, that published definition, and the
interactive provider (normally `/<node>/io/codex/surface_provider`). The composer
and creation form are declared Goo actions, also discoverable headlessly.

The chat history scrolls independently of the docked composer. Enter activates
the declared Send control; Shift+Enter inserts a newline. Keyboard submission
waits for text composition and pending editor operations, and uses Goo's normal
in-flight/receipt handling. The composer accepts plain multiline messages;
formatted runs are still rejected by the native message input contract.

New responses follow the bottom while you are there. Reading or editing earlier
documents pauses following; **Jump to latest** or sending a message resumes it.
Window resizing prepares Goo at its new allocation while preserving drafts.
Each turn's disclosure opens the existing work projection, with links to its
response document and native trace. Closing the tab stops presentation reads
and disconnects layout observation.

The chat shell takes its layout reference from Astryx's
[AI Chat Conversation playground template](https://astryx.atmeta.com/playground):
a white canvas, centered reading column, trailing message bubbles, rounded
composer and collapsible work summaries. It uses the existing native Goo and
Nenex renderers rather than importing Astryx's React chat components.
The native manifest derives status
from the controller and its current crew-selected requests and workers:

- **Working**: provider preparation, active execution or result admission.
- **Waiting for input**: an unresolved answer, manual revision or waiting provider.
  A retained clarification note is shown when available.
- **Blocked**: admission, allocation, provider, validation or publication failure.
- **Watching for changes**: the flow has published and is following its evidence.
- **Paused**: the native controller is disabled or detached.

The browser renders these labels directly. It stores no status transitions and
does not inspect the retained attempt subtree to infer progress. Old failed
attempts cannot override a current retry; a published reply can still have a new
blocker. The manifest retains the raw controller status/reason for inspection.

An unresolved conversation response offers **Answer and resume** inline, beside
the retained explanation. Its rich-text input and action are declared Goo
controls. The docked **Send** button still starts a new turn.

Answering writes a Nenex clarification beneath the original message and binds
it into that turn's existing context lens. The native operation checks the
request version, current hole head, controller ownership and destination claim;
it refuses paused, superseded or non-clarification work and occupied addresses.
The same hole and maintenance hand react to the changed evidence and create a
new attempt. The answer itself does not resolve the hole or overwrite the old
attempt, message, provider result or captured definition. Validated completion
publishes to the original response document. Another missing-input response can
ask for another clarification through the same path.

One request accepts one answer receipt; repeating the same admission is a no-op,
and a conflicting duplicate is refused. Receipts retain the original request
and hole references. Later conversation turns pin the clarification documents
visible when they begin. Replies are scoped to their original context cell,
so answering one turn does not broadcast new evidence to every conversation
occurrence. Goo preserves an unsent draft if its request is superseded; it does
not silently move that text onto a different request.

Nenex is still projected by `GooDocument`: chat requests compact content without
the wiki header or tool catalogue. The writer's terminal section containing only
the page's own flow receipt is omitted from this projection; **Work and trace**
opens the full response document and retained work. No source or history is
deleted. Text, embeds, edit guards, local drafts and native actions remain in the
same renderer. Send's row has an 8 px gap above it, a 6 px inset and aligns right
at all widths. Its padding fits within the prepared width rather than enlarging
the row. The dock reserves 12 px on each side and 16 px below the composer,
honoring device safe areas. It participates in the page layout, so growing the
draft reduces the history viewport instead of covering messages. The reading
column is capped at 720 px; phone gutters are 16 px below 600 px viewport width.
Message bubbles use a leading gutter in pixels so fractional widths do not introduce
scrollbars around prepared blocks. Rich inputs measure wrapped content on their
existing bind step, once the prepared DOM is mounted at its actual width.
Feedback prepares at the available width and reflows with the composer. A
fulfilled, hidden clarification form uses its parent allocation for its notice.
The small **I** inspector retains its accessible name.
CSS supplies host layout and control paint, while Goo owns measured typography,
control geometry, input contracts and action dispatch. Only supported controls
are shown; the reference's attachment, mention and mode controls are not added.

**Wiki** and **Work and trace** open a panel beside the chat. Below 960 px the
panel occupies the reading area; **Chat** returns to the retained composer.
These navigation controls are declared Grove views using Goo's existing
`become` transitions. Selection is local presentation state and writes nothing
to the namespace. Switching views keeps the mounted controls and drafts.

Wiki mounts the existing Nenex page tree at the conversation's wiki address.
Child pages, source editing and creation use its existing native controls and
paged frontiers. The visible tree follows native subtree versions, refreshing
changed clean documents and keeping dirty documents untouched. Hidden wiki
views stop presentation reads. No copied wiki, navigation index or document
renderer is introduced.

Work moves each turn's existing disclosure into the panel and opens the latest
turn initially. The ordinary occurrence controls and crew-selected current
requests expose their holes and native actions. The work cell and native history
overlay are lazy inspections; a link opens retained attempts and tool traces in
the existing namespace browser. Reopening
a disclosure refreshes its native version; closing it stops work-view reads.
Current status still comes from the native manifest, independently of whether
any inspection is open.

After publishing changes to this mount, **Select published conversation
operations** explicitly admits its current registrations through the existing
namespace boundary. Republish an authored response flow to capture those laws,
then select that definition when creating a conversation. Existing conversations
can explicitly advance future turns with `conversation/select_definition`, supplying
the previous and new pinned definition references. Existing occurrences adopt a
new definition separately through the ordinary flow operation. Start receipts,
attempts and prior publications retain their selections. This updates native operation
records, not the saved HTTP service or compiler.
JS/CSS assets follow the published source bundle. The HTTP view handler is
selected when serving the world: after publishing a handler change, an ordinary
restart from the same native continuation selects it. Publishing alone does not
replace the running foot's captured route closure.

The response policy asks for Semidoc with a heading and accepts sections, rich
text, native references and declared embed relationships. It validates and
publishes those authored nodes, preserving repeated attributes. Writing source
does not implicitly publish its flow declarations or execute embedded examples.
The selected interactive provider can inspect/invoke existing declared actions
to do requested work. Its authority is the provider's namespace authority;
the prompt and wiki scope are context policy, not an authority sandbox.
The ordinary Nenex authoring view also exposes **Create child document**, so a
person or agent can grow the conversation's wiki through the same guarded source
authoring operation. Named children are documents; positional source blocks and
internal work/flow/cell branches are not document destinations.

## Named wiki roots at startup

The declared **Start conversation** action accepts **Wiki roots**, a JSON object
from names to existing namespace record paths, for example:

```json
{"procedures":"/0x11/app/nenex/w/team_procedures","project":"/0x11/app/nenex/w/customer_onboarding"}
```

The native `conversation/start` operation accepts the same selection as typed
`roots/<name>` references. Each must select one record (`x`); native callers may
select a live or historical reference. The GUI selects live records. Aliases are
canonical flow names, at most sixteen; missing roots, duplicate GUI aliases,
subtree captures and roots within the newly allocated conversation are refused.
An existing conversation cannot silently adopt a different startup selection.

The selection stays on its ordinary configuration record at
`<conversation>/conversation`, under `chat/roots/<name>`. Every turn adds those
references to its existing Cooperate context lens at `roots/<name>`. Its `startup`
binding pins the configuration record observed for that turn, exposing the root
addresses without a second inventory. A root edit updates current context through
native cell dependencies; deleted roots contribute no current content, and
restoration reconnects the same binding. Captured attempts retain their readings.
The startup binding is pinned so advancing the conversation sequence does not
invalidate old work. Root records are read shallowly; children are browsed with
`shrine_read` rather than eagerly imported into every prompt.

An agent can browse a selected root, discover another agent's authored child,
read its Semidoc and exact published definition, inspect its ports, and invoke the
existing declared flow controls. Creating a child does not publish or invoke its
flow implicitly. Other agents see shared documents through the same native paths;
there is no per-agent copy or skill registry. The mounted example catalogue is
optional and is not required for discovering user-authored flows.

Root selection provides navigation and evidence, not additional authority or
instructions overriding the task. The existing scoped `/r` context still selects
explicitly related evidence independently. Selecting a root does not recursively
follow every link or subscribe to every child; graph traversal and selection
policy can be authored as flows. Ordinary source edits, published definitions,
work records, action receipts and x/y/z history remain the existing representations.

An invocation which edits its own watched wiki can invalidate its answering
attempt. The lifecycle retains that attempt and resumes against the new context.
Every interactive request exposes `<attempt>/resumption`, an ordinary work cell
linking the hole's previous attempt and that worker's action trace. The provider
prompt directs the agent to inspect it before further effects. The predecessor
retains its own resumption address, so older work remains navigable without
scanning or copying the complete execution history into each prompt.

This work view is separate from the evidence lens. Appending action receipts or
reading prior work does not invalidate the current demand. The wiki record and
explicitly bound evidence still participate in freshness checks: a self-edit or
external evidence change must be revalidated before publishing an answer.
An accepted action remains accepted when its surrounding answer becomes stale.

Reuse the existing selection cell and occurrence address when resuming the same
intended work. Identical selection, attachment and existing embedding requests
are no-ops; changed bindings conflict, detached controllers remain detached,
and stale source/view guards still refuse writes. Different occurrence names
represent deliberately different work; these rules do not infer semantic
identity between arbitrary model-generated actions. Goo continues to retain
receipts for individual invocations.

## Native layout

For a conversation page `P`:

| Address | Existing representation |
|---|---|
| `P` | Nenex document linking its wiki |
| `P/wiki` | Nenex working wiki, with ordinary named descendants |
| `P/messages/<id>` | User's Nenex message document |
| `P/replies/<id>` | Response published by the selected Nenex writer |
| `P/cells/<id>` | Native context lens, with ordinary graph membership hand |
| `P/work/<id>` | Existing flow maintenance controller and retained work |
| `P/conversation` | Selected definition/provider references and next sequence |
| `P/conversation/turns/<id>` | Idempotent receipt, sequence and document/work references |
| `P/messages/<id>/clarifications/<request>` | Nenex answer, explicitly bound to the original context lens |
| `P/conversation/turns/<id>/clarifications/<request>` | Answer receipt with retained request/hole references |

The selected definition and provider are pinned when the conversation starts.
Earlier messages and available replies are pinned to the versions visible when
a later turn is sent. The response prompt includes the current message; the full
context is exposed through the request's ordinary frozen `context` cell, linked
from `work/context`. The interactive provider reads relevant branches through
`shrine_read`. No history is truncated or copied wholesale into the prompt, and
later source changes cannot alter an earlier attempt's captured context.
The current message, wiki subject and explicitly selected
incoming evidence remain live. Editing them changes the demand through native
cell dependencies. Old attempts retain their readings; obsolete provider results
cannot satisfy current work. Edited generated response prose is protected by the
writer's existing conflict guard.

Graph membership comes from native `/r` observations, filtered by an explicit
scope. The hand reconciles only its `evidence` aliases; cells subscribe to holder
contents. Removing a reference releases its live binding. Retained captures and
history remain. The default subject/scope is the conversation wiki; ordinary
records under that wiki can explicitly reference the subject to join the context.
The native start operation also accepts an external subject and scope. Scope may
not include this conversation's reply/work trees.

## Boundaries and current limits

- Conversation sends plan native document writes and `follow` in one admission.
  Duplicate native turn IDs with equal input are harmless; conflicting input or
  occupied addresses are rejected. Goo adds its existing invocation receipts and
  selected receiver/publication guards.
- Work inspection projects the existing occurrence, request, hole and cell
  records. Retry invokes the same shared native operation used by other flows.
- The browser periodically reads presentation state while visible. These reads
  never dispatch work. Closing the browser stops them; native work continues.
- This first view reads conversation turn metadata and explicitly selected
  message context. It does not claim unbounded chat history, automatic relevance,
  automatic summarization or semantic skill selection. Prompt/schema limits
  still apply to instructions. Evidence is read from retained cells rather
  than silently truncated; selecting relevant context is still model work.
- Wiki edits during an active turn can invalidate its evidence and start a fresh
  attempt. Agents must treat that wiki as shared evidence, not a private scratch
  buffer. Retained prior-turn captures stay unchanged.
- Provider execution is a separate existing mount. A UI/controlled-provider test
  does not establish a live Codex model run.

All state uses the existing world and native x/y/z history. This mount has no
host process, filesystem store, scheduler, provider loop or save format.

## Validation

Run `extras/x/check --mount conversation --suite conversation_tests
--suite flow_document_boundary_tests` with the native runtime available, and
`node --test extras/mounts/conversation/app.test.cjs` for presentation refresh and
draft handling (also included in `extras/x/check-goo`). The native cases use controlled provider responses. They cover
literal multiline messages, native reply references, repeated bindings through
source/Goo edits, retained turn order, graph-context removal/restoration, stale
result rejection, holes/retries, occupied-address guards and retained x/y/z
history. Status cases distinguish active workers, clarification, provider and
validation failures, retries, pause, allocation collisions and publication
guards without treating historical work as current. Input/resumption checks cover same-hole
resumption, the declared Goo adapter, guarded and duplicate submissions,
clarification capture in subsequent turns, and retained x/y/z history. The edited
response case delivers to the crew-selected current request and checks the exact
`flow_generated_page_edited` refusal, not merely the overloaded controller status.
Document-boundary cases check source ownership and captured writers.

A separately mounted world is also required for integration validation: the
combined fixture shares one compilation context, whereas deployed mounts must
explicitly import the same Semidoc contract. `codecs` owns that pinned artifact
for both Flows and Web/Nenex. No runtime type matching is involved.

Controlled provider responses do not establish live-model reliability, automatic
skill selection or performance. Check the retained native reports for the actual
suites and outcomes of each validation run.
