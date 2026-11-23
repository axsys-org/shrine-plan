# Namespace agents

Server commands below run from the Reaver root. Cargo commands and native
render artifacts refer to the separate `shrine-goo-native` checkout. Historical
validation counts are not a substitute for the current branch’s PR checks.

Agents live at `/[node]/app/agents/[agent-id]`. Their Goo interface is
`shuin-chat/agents.grove`; their loop, policy, provider protocol and tool
implementation are Shrine code. The native GUI has no Agents-specific code.

Set `OPENROUTER_API_KEY` in the environment used to launch
`python3 extras/shuin/run-chat-server.py`. The default model is
`google/gemini-4-neon`, editable in the scene. The host hook only provisions a
mode-0600 temporary credential file and passes its filename to Shrine. The key
is not a slot, model message, request journal field, or command-line argument.
Restart Shrine after changing the environment credential.

The left sidebar lists current agents and their status. **+ Add agent** opens
an empty creation form in the main pane without creating a record or contacting
the provider. Enter a name, model, instructions, separate Read and Write dependencies and
an optional first task. **Create agent** opens its detail page; an empty first
task leaves it idle. Existing names are rejected rather than overwritten.

Select a sidebar row to open that agent's tasks, answer and provider reasoning.
**Send task** appends an inbox item. **Resume / retry** starts another bounded run;
a nonempty task is also enqueued. Namespace Explorer exposes the underlying
records. The list is capped at 128 agents.

The sidebar uses reusable Goo data composition: `group(each = item.catalog,
as = "agent")` expands a bounded `goo_composition/items` value, and
`group(when = item.mode, is = "new")` gates the creation form. Both expand inside
Shrine's shared `matching_view` path, so rendering and action admission see the
same controls. Repeated rows own no editors and their buttons act on the enclosing
receiver with source-declared literal arguments. The generic native editor now rebuilds clean controls when the accepted state
changes within the same publication; dirty drafts, composition, pending actions
and incompatible hot publications retain their existing guards. No GUI-specific
agent list or conditional renderer was added. The generic composition support is included in this Reaver checkout.

## One turn

1. Capture typed read/write grants and bundle their union with the live agent
   subtree using each hunt’s care. Capture each inbox item's exact record version.
2. Commit a pending turn and an HTTP request beneath `/[node]/io/http/outbound/[agent-id]`.
   The request has method, URL, JSON body and a credential name, never the key.
3. A separate Shrine foot registered at `/io/http/outbound` claims and performs the
   request. The agent waits for its recorded response. The UI remains responsive.
4. Validate a complete provider response. Retain its assistant message verbatim,
   including provider `reasoning_details`, and preserve tool call IDs on replies.
5. Execute tools in order. Each failed tool produces an error receipt and leaves
   that tool's namespace changes unapplied. Commit successful writes, receipts,
   provider output, and inbox acknowledgements in one namespace transaction.
6. Remove only captured inbox records whose versions still match. New or edited
   items remain. Tool results enqueue a continuation. With no inbox items, the
   agent is idle.

HTTP failures, incomplete responses and export failures leave the inbox intact.
There is no automatic network retry. A run is capped at 16 turns, a response at
16 tool calls, and an export at 512 records / 256 KiB. Resume is explicit after
failure, interruption or the turn limit. Idle actors wait for namespace facts. HTTP completion records a response pointer
on the caller’s record to wake it; no GUI timer drives the loop. Eden’s existing `/io/http` listener remains intact; outbound requests live in
its `outbound` child. The HTTP service and the initial agent scheduler each process one request at
a time. Other namespace clients can submit the same request records. The HTTP
service only attaches its OpenRouter credential to the configured endpoint, and
rejects changed request records before committing a response.

Tools:

- `namespace_read`: request File (`x`, default), Folder (`y`) or Subtree (`z`)
  within the union of this agent’s read and write grants.
- `namespace_write`: typed literal slots within this agent’s `workspace` or
  declared write grants; Folder creation stops at intervening records.
- `grove_actions`: matching published Grove actions for a readable record.
- `grove_invoke`: an action from that catalog, with exact receiver, publication
  and role versions. Arguments are typed literal data, never evaluated Foil.

The provider can write workspace data and invoke receiver actions; it cannot
rewrite its runner configuration, inbox or turn receipts through these tools.
Separate typed read/write grants can be picked from the visible namespace.
See [Care-aware path inputs](path-inputs.md) for search, actual frontier semantics,
save preflight, legacy migration, and per-agent changes deferred until a turn ends.

## Namespace text v1

`namespace_text.foil` is independent of agents. `encode(root, namespace)` emits
flattened Rex records (`+ .`, `+ relative/path`) and literal slot assignments
(`= /absolute/slot (fully/qualified/constructor literal)`). Record and slot order
is canonical namespace order. Empty records are preserved; absent intermediates
are not invented. Constructor names omit publication cases. Text uses Rex
escaping and column-aware indentation. Leading newlines and control characters
use an exact packed-atom literal with a `str` type ascription, avoiding Rex tape
whitespace normalization. Constructor names are definition paths without a
leading slash (for example `sys/types/pails/t`); a seed reader resolves them
against published definitions. Only typed paths beneath the exported root become `'~/…`; strings are
never rebased, and external paths remain absolute. Empty paths use `[]`, because
a bare `'/` can absorb the next expression in Rex.

The default encoder is type-directed: it resolves each nominal value's published
`/sys/mold` at the constructor's exact definition version, substitutes concrete
generic arguments, and recursively encodes records, variants, tuples, rows and
scalar atoms. Application records need no registration. Nested generic containers
(such as options, lists and maps) use their field's reflected type arguments.
Paths keep their semantic spelling and root rebasing; text keeps exact bytes.

Native type publication exposes the declaration body, including generic
parameters, rather than a self-reference. The reflected-data encoder and its
compiler metadata support are included in this Reaver checkout.

Executable fields, pins, missing definition versions, opaque descriptors and
erased generic arguments are explicit errors, with the record, slot and nested
field/item context. A nominal brand alone does not recover erased type arguments;
`walk(namespace, root, descriptor, value, fuel)` accepts a concrete descriptor
when the caller has one. No field is silently omitted, and there is no clipped
`show/value` fallback. Values are bounded to 128 traversal levels, 4,096 items per
row/record and 256 KiB; exports retain the 512-record / 256-KiB limits.
`encode_with` remains available for an explicit alternate representation.

This implements the **writer** portion of `namespace.seed.rex` / `seed_notes.txt`.
The general seed loader, module import resolution and arbitrary generic
constructor decoding are not implemented here. Tool writes use a deliberately
small typed JSON literal decoder (text, natural number, boolean, path), rather
than interpreting model-supplied Foil. A generic seed loader should remain a
separate data-only transaction API.

## Verification

`test-agents.py` supplies a deterministic mock OpenRouter and drives the real
Shrine actor through a disposable test mount. It covers Rex record parsing and
exact text literal round trips (including multiline text and control characters),
credential exclusion, a write → action discovery → action invocation → read
sequence, scope rejection, provider failures, and inbox arrivals during HTTP.
The mock uses `SHUIN_AGENT_TEST=1` to permit a loopback endpoint; ordinary runs
only accept the OpenRouter chat-completions URL.

Start these in separate terminals, using a fresh mock and disposable world for
each full run:

```sh
python3 extras/shuin/test-agents.py --mock-only
```

```sh
SHUIN_AGENT_TEST=1 \
SHUIN_OPENROUTER_URL=http://127.0.0.1:8342/api/v1/chat/completions \
OPENROUTER_API_KEY=shuin-test-key \
python3 extras/shuin/run-chat-server.py --port 8341 --test-fixtures
```

After the server reports ready:

```sh
python3 extras/shuin/test-agents.py --server http://127.0.0.1:8341
GOO_DISPOSABLE=1 SHUIN_AGENT_TEST=1 GOO_TEST_SERVER=http://127.0.0.1:8341 \
CC=/usr/bin/clang CXX=/usr/bin/clang++ \
cargo test --offline -p shuin-widgets --test agents -- --ignored --nocapture --test-threads=1
```

Provider protocol follows OpenRouter's [chat completions API](https://openrouter.ai/docs/api/api-reference/chat/send-chat-completion-request)
and [reasoning details guidance](https://github.com/OpenRouterTeam/docs/blob/main/guides/best-practices/reasoning-tokens.mdx).
Reasoning shown by the scene is only what the provider returns; the full
assistant message is retained for tool continuations.

Generic encoder acceptance uses a disposable test mount:

```sh
python3 extras/shuin/test-namespace-text.py --server http://127.0.0.1:8374 \
  --output artifacts/generic-codec-roundtrips.json
GOO_DISPOSABLE=1 GOO_TEST_SERVER=http://127.0.0.1:8374 \
  CC=/usr/bin/clang CXX=/usr/bin/clang++ cargo test --offline -p shuin-widgets \
  --test paths create_agent_with_reflected_talmud_dependency -- --ignored
```

The round-trip fixture evaluates only trusted generated literals in the test
module's compiled context, adapting canonical seed names to imported names while
preserving Rex columns. It is not an agent tool or a general seed decoder.
The kernel check is `x/check reflected-data-tests foil-system-core-tests`.

### Creating records with Grove stencils

Agents discover creation contracts with `grove_stencils({path})`, then call
`grove_create` with the returned stencil path, parent `recordVersion`, declaration
`publication`, `roleVersion`, `resultRoleVersion`, and typed arguments. Discovery
is paginated: pass `next` as `after` together with `epoch`. A stencil is separate
from `@action`: it creates a fresh child and never updates its parent.

The chat declaration is in `shuin-chat/chat.grove`:

```text
post_message =
  @stencil
  #on ; %/channel
  #for ; %/message
  content: text
  author: text
  ! foil
  \ body=str by=str parent=channel created_at=nat
  ^ message
  ; (? (and body.len by.len) 0 (error (pails/t "Message content and author must not be empty.")))
  | message body by created_at myth/new
```

`#on` declares the parent role; `#for` declares the created record's role. The
compiler generates typed argument decoding and publishes `/sys/grove/stencil`
and `/sys/grove/stencil_handler`. An implementation receives the declared
arguments, the typed parent, and trusted Unix seconds, in that order. The
`created_at` argument name is reserved for the generated runtime binding.

Shrine checks declaration/parent/role versions, validates the completed result,
allocates an unoccupied `entry_<number>` child, checks the agent's captured write
grants against that exact destination, and commits it with the tool receipt in
the existing turn transaction. The driver samples the clock after HTTP returns;
the model cannot supply or override that provider value. A completed turn is
idempotent when its provider response is delivered again. Failed creation leaves
no partial record. Separate, deliberately repeated calls create separate names.

For chat posting, give the agent Folder or Subtree write care on the channel.
File care cannot create its children. Read-only grants are insufficient. The
receipt contains the created path; the message includes content, author and
`/sys/now`, making it eligible for the existing Goo chat entry view. No Rust or
chat-specific agent tool is involved. Existing incomplete records are not
silently repaired or reposted.

Verification: `test-stencils.py --server URL --actor` uses a disposable fixture
world and the mock provider from `test-agents.py --mock-only --mock-port 8343`.
The server must use that same mock endpoint. The general agent regression suite
accepts `--mock-port 8343` as well. Japanese IME testing remains independent.
