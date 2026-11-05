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

After publishing changes to this mount, **Select published conversation
operations** explicitly admits its current registrations through the existing
namespace boundary. Republish an authored response flow to capture those laws,
then select that definition when creating a conversation. Existing conversations
and attempts retain their selected definitions. This updates native operation
records, not the saved HTTP service or compiler.

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

The selected definition and provider are pinned when the conversation starts.
Earlier messages and available replies are pinned to the versions visible when
a later turn is sent. The current message, wiki subject and explicitly selected
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
  automatic summarization or semantic skill selection. Existing flow/request
  input limits still apply; large contexts fail visibly rather than being
  silently truncated.
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
draft handling. The native cases use controlled provider responses. They cover
literal multiline messages, native reply references, repeated bindings through
source/Goo edits, retained turn order, graph-context removal/restoration, stale
result rejection, holes/retries, occupied-address guards and retained x/y/z
history. Existing document-boundary cases check source ownership and captured
writers alongside those additions.

A separately mounted world is also required for integration validation: the
combined fixture shares one compilation context, whereas deployed mounts must
explicitly import the same Semidoc contract. `codecs` owns that pinned artifact
for both Flows and Web/Nenex. No runtime type matching is involved.

The November 2026 validation passed 48 conversation checks, 43 existing document
boundary checks and six browser-adapter checks. In a separate persisted world,
the live Codex provider read wiki evidence and published a response with a native
reference. A second turn discovered Goo controls, created a named wiki child,
read it back and published a response linking to it. An earlier malformed
response remained in its failed attempt; the declared retry created a linked
attempt, published successfully and resolved the original hole. Those live cases
exercise the provider boundary; they are not a claim of model reliability,
automatic skill selection or broad performance validation.
