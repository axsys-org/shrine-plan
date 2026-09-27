# Shrine protocol 5

JSON carries RPC arguments and literal data. Programs are actual Foil. This bridge has no projection, predicate, reaction or grounding expression interpreter.

Nine operations: `status`, `read`, `write`, `compile`, `eval`, `observe`, `source`, `context`, `events`. MCP and authenticated `POST /rpc` share the same implementations. HTTP bodies are `{ "method": "read", "arguments": { "path": "/example" } }`. The shared `Client(connection_file).call(method, **arguments)` uses this endpoint.

`status` reports world identity, protocol, pinned engine identity and owner health. A v5 client refuses an older connection. A v5 owner refuses old journals. Use an older world's compatible archived bridge instead; copying its files into a new world is not migration.

## Native records and values

`write(op, path, fields?, slots?, record?, expected_case?, request_id?, work?)` uses native `make`, `poke` and `cull`. Make replaces a record; poke invokes its attached behavior (the default merges); cull removes it. Case zero requires absence; a positive case must match the current native case. Request identities deduplicate matching inputs and reject mismatched reuse. Authored native cascades may produce further changes; errors can report committed partial cascades. Receipts identify the actual result.

Use `slots: [{key: ["a/b"], value: ...}]` for an opaque slot key containing a slash. `["a", "b"]` is a different slot, not a nested JSON field. Both are unrelated to child node `/a/b`. `fields` is shorthand: a leading slash denotes a segment path; other keys denote one text segment. Native paths also accept explicit aura segments, e.g. `["log", {"tag":"u","value":17}]`. `path_segments` is the authoritative round-trip address when a display path is ambiguous.

Read includes all slots, behavior references, crews, native cases and renderings. `recursive`, `limit` and `after` page a subtree. `case` reads its immutable historical basis. Do not confuse path-local cases with the bridge's global event cursor.

Literal JSON values remain literal data. Values without a lossless literal representation return:

```json
{"$native":{"path":["_shadow","values","immutable-id"],"case":1,"slot":["value"],"unbox":true}}
```

References also carry a `world` identity. Foreign-world handles are rejected. The reference addresses the original native runtime value. It is valid in subsequent writes and evaluations, including after restart. `unbox` is transport metadata for a pinned code carrier, not an expression operation. Read-slot references normally preserve the pail itself. Renderings are only previews. Use `$literal` to escape literal data whose top-level keys collide with `$native`.

For an entire native myth, use `record` with a pinned result instead of fields or slots.

Native text cords cannot contain NUL. Direct unsupported text writes fail before journaling; observed values containing NUL are preserved as content-addressed artifacts. Git observations split NUL-delimited status entries into a structured list. Malformed native wire input returns an error without leaving the owner loop.

Writing a `cpail` to the native `/sys/crew` slot changes dependencies without injecting a behavior. Writing a `kook` to `/sys/limb` binds behavior references. An ordinary node at each referenced path supplies a `form` slot containing the actual native form. Missing or incorrectly typed forms return native errors.

## Compile and evaluate

`compile(source, exports, modules?, request_id?, work?)` invokes the existing Foil compiler. Export names are source paths such as `demo/form`. The result pins the module subject and exported values, records source artifacts, the native import closure and diagnostics, and returns an execution receipt. Additional modules have immutable names under `user/`, such as `user/acme/v1/helpers`; imports use those exact normal Foil names. Choose a new name to revise one. There is no import rewrite or generated language.

`eval(expression, module?, inputs?, request_id?, work?)` elaborates and evaluates real Foil. Omit module to use the pinned native assembly and its libraries. Inputs may be typed pinned exports/results, native pail references, literal pails, or historical record snapshots:

```json
{"original":{"$record":{"path":["invoice"],"case":3}}}
```

The example can be used in `original.nat_at(['total] 0)`. The result is a pinned native value. Returning a writ, card, myth or form does not apply it. Installation and binding require explicit native writes. Failed compilation cannot replace installed behavior. A native attempt that does not commit is retained as failed/uncertain for explicit retry; restart never blindly reruns an unbounded expression.

Snapshots contain the native sovereign, compiler subject, actual values and continuation. Recovery reconciles native commit sequence with an fsynced begin/commit journal; it does not reinterpret historical source code. Each world pins its Wisp binary hash and source closure. The bridge uses the existing baseline bytecode compiler compatible with the supplied runtime. The owner bounds request time and native cascade rounds. Arbitrary native programs remain responsible for their semantics.

## Optional understanding conventions

There is no mandatory application container or node layout. `shadow_forms.foil` provides inspectable native functions for questions/statements, assessments, projection publications, notices, check results and retirement. `shadow_io.foil` provides request/outcome coordination. You can compose, extend or bypass them.

Participating records may use statement/question, anchors, related, evidence, origin_work, scope, meaning_revision, applicability, result, predecessors/successors, generalizes/specializes and ordinary work references. Tags aid optional navigation; they do not install dependencies. Work records preserve objective, trigger, parent, inspected/changed subjects, explicitly used evidence, executions and unfinished understanding. Delivery is not evidence of mental use.

The assessment helper retains its original hydrated basis and scope. Establishment requires evidence and current, noncircular support through the helper's lineage. Changed basis reopens it. Semantic establishment is an authored assessment, not a proof of universal truth. The native check helper publishes `HOLDS`, `FAILS` or `UNKNOWN` for the supplied function's scope. An unresolved broader commitment remains unresolved. Retired records and historical evidence stay readable.

Use native `equal` for structural values; `eq` is scalar equality and does not compare a hydrated basis.

Projection helpers receive actual Foil functions and publish only their outputs. Keep volatile receipts out of these publications. Native initialization sees the runtime's current hydration: on a newly created node the incoming crew may not yet be hydrated. Subsequent native activity supplies it; forms should represent missing input explicitly and may provide their own refresh operation.

## Observation and I/O

`observe` accepts source and subject identity, availability (`available`, `unavailable`, `deleted`), coverage (`complete`, `partial`, `unknown`), optional value/change, revision, environment, timestamp, artifacts and known work/execution references. Receipts are historical facts. A separate per-source subject head retains current factual input. Sources do not implicitly merge identities across external systems. Native authored mappings establish conceptual correspondence.

`source` configures or samples filesystem, Git, process, HTTP or pushed sources. Configuration is concrete physical data. Polling is opt-in through `poll_seconds`; unchanged samples do not advance the subject head. Large values and outputs are content-addressed artifacts. Missing files, partial reads and unavailable sources remain distinguishable. A repository attachment records identity and compact Git observations, not a full import.

Sources default to observation-only. External authority is unchanged by attachment. An outbound-enabled source accepts a concrete request record with driver reference, operation, arguments, status and episode, attached to an appropriate native coordinator. An authored form commits the request and emits a `/io/dispatch` card with a native request path. The driver claims the native case before performing one attempt, records a factual outcome, then reports that attempt back. It never turns a semantic intention into an operation or decides application retries.

`REPORTED` does not mean fulfilled. Independent observations and authored native requirements establish fulfillment. Pending requests deduplicate through their native identity and claim. In-flight requests are not redispatched after restart; their completion remains uncertain until an outcome or investigation resolves it. Late outcomes retain original attempt/request references. Native retry policy must explicitly rearm and emit another request. External effects are not executed during read, eval or historical recovery. Arbitrary outbound moves also retain pinned native values even when no physical driver handles them.

## Context, delivery and inspection

`context(subjects, cursor, limits, include_tags)` follows explicit references, behavior links, crews and child relationships in both directions. Each item explains its route. Unfinished or tentative connections are labeled separately. References may include `world` (a world identity) or `external_world` (an explicit external locator); foreign references never resolve to a same-named local node. Unavailable, foreign and older-case targets appear as `reference_only`, preserving their original basis without borrowing current prose or traversing current relationships. These follow available connections; empty namespace spines do not consume the context budget. Context cursors bind to an index revision; stale cursors ask the caller to restart traversal. Default delivery is at most 12 items and 12 KiB; callers can page and inspect referenced evidence. Context indexes rebuild from committed changes. A route is a navigation fact, not inferred causality.

`events` reads committed attempts/results by cursor. Optional consumers and explicit acknowledgements maintain delivery state outside the watched publications. Native notices remain pending across fresh contexts. The Codex adapter keeps excess notices in a durable pending queue and does not consume them through truncation. It records supported reported executions, materializes compact work identity, observes attached physical subjects and delivers focused context. It does not record private reasoning or start an agent.

The separate inspector is read-only. It shows actual nodes, slots, crews, forms, reference routes, event receipts and artifacts. Continue using normal desktop, terminal, Git and coding tools to perform work.
