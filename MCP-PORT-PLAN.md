# Porting %urbit-mcp to Shrine

Source: `github.com/gwbtc/urbit-mcp` at 2026-09-23 (`bm/scry-marks` merge). 2,138 lines for the agent, about 1,750 for libraries and 33 tools, 9 prompts, resources and templates, one skill. Target: this checkout at `ic-latest` (latest `main` + `lf/goo-frontend` + `lf/bat-support`), Enki `main` 25b51fd.

Line counts are estimates from reading both sides. Kernel facts below were checked by running them on 5 October (the agent worker, native fetch, worker messages, the Codex mount's check).

## What %urbit-mcp is

- A Gall agent bound to `/mcp` on the ship's HTTP server, behind the ship's login cookie, speaking MCP over streamable HTTP: JSON-RPC by POST, SSE for notifications; `initialize`, `tools/list`, `tools/call`, `resources/list`, `resources/read`, `resources/templates/list`, `prompts/list`, `prompts/get`, `list_changed`.
- Its registry is state, not code: sets of tools, prompts, resources, templates. A tool is `[name desc parameters required thread-builder]`; the builder makes a Spider thread from the arguments; the thread returns `[%error tag (unit json)]` or a result. Everything the ship can do is reached through threads.
- 33 tools: `mcp/*` (identity, scry, poke, files, commit, build, test, install, permissions, add and import features), `dojo/*` (commands with named sessions, desks, agents, threads, pills), `aqua/*` (virtual ships).
- Run-time extension: `add-mcp-tool` compiles a gate from text; `import-mcp-*` pulls what other apps publish at `/x/mcp/{tools,prompts,resources,resource-templates}`. Resources resolve `beam://`, `scry://`, `fine://`, `https://` on the ship.

## How it maps

| %urbit-mcp | Shrine | State |
|---|---|---|
| Agent on Eyre `/mcp` | A mount, `extras/mounts/mcp`, with a route on the world's HTTP foot | Mounts register routes today |
| Login cookie | A token the mount's host file issues, sent as `Authorization: Bearer`; checked in the route | The foot does not pass headers to routes today; step 1 adds them |
| Threads | A worker (foot) registered by the mount; it issues the kernel's worker messages: read a path at a care, write, press a view's control, recompile a mount, inspect, history | Verified 5 Oct |
| Registry in agent state | Records under `/<node>/io/mcp/{tools,prompts,resources,templates}` | Workers read and write records; verified |
| `scry-agent` | `inspect` / `peek` of a path, projected to JSON | Exists |
| `poke-our-agent` | make / poke / cull at a path, refused by the record's contract when it breaks it | Exists |
| `list-files`, `get-file` | Mount source records under `/io/fs/<mount>/source` | Exists |
| `insert-file`, `commit-desk` | Write a mount file, rescan with the full compile failure | Rescan exists; the file write needs the host (outbox) until compile-from-text |
| `test-build`, `add-mcp-tool`, `dojo/command` | Compile a Foil module or function from text; evaluate Foil | Not in the kernel yet (Enki `Pure` op is written on `ic-pure-op`; the endpoint is not) |
| `install-app`, `revive-desk` | Grove install, instance replace | Exists |
| `new-desk`, `mount-desk` | A new mount folder, loaded into the running world | Needs the restart today; step 4 removes it |
| `/x/mcp/*` publish convention and `import-mcp-*` | Each mount publishes `mcp/tools` records; the server imports them | New |
| `beam://`, `scry://`, `https://` | Source records, path reads, native fetch | Fetch verified 5 Oct |
| `fine://` | Remote read | No networking; left out |
| SSE, `list_changed`, progress | The HTTP foot has no streaming responses | Step 1 adds a streaming action to the foot |
| `aqua/*` | None | Left out |

## Kernel changes, all in step 1 except the last

The HTTP foot was built for one action per request and one reply per connection: a route handler returns a single kernel action, the request type carries no headers, and every response closes the connection. Four changes, measured against `src/foil/http_foot.foil` as it is (704 lines):

1. **`ask`.** A route handler hands the request record to a named worker's home and the HTTP request completes when that record carries a response. About 60 lines. This is what lets a tool call run several kernel operations.
2. **Headers.** `http_foot/request` gains `headers=row[[str str]]`; the parser already walks them for `Content-Length`. About 40 lines, plus the three constructors in the web mount that build a request. This is what makes a bearer token or a cookie possible.
3. **Streaming.** Deferred on 5 October at Ian's call. The server answers JSON only; clients re-list tools when the registry changes, and `tools/call` answers when the work is done. When wanted: a `stream` action with the connection kept open as `text/event-stream`, events poked onto the stream's record written to the socket as they arrive; about 170 lines plus 60 of tests.
4. **Local binding.** The world listens on every interface with no authentication. Enki `pkg/plan/src/rplan.c`, about 5 lines, binds `Listen` to localhost unless told otherwise.

Step 4 adds the fifth: loading a mount into a running world without a restart.

```
client --POST /mcp (bearer token)--> http foot --ask--> /io/mcp/r17 (request record)
                                                          |  fact
                                                       mcp worker --peek/poke/develop/interact--> kernel
                                                          |  poke response onto /io/mcp/r17
                                     http foot <--completion-- reply JSON-RPC

client --GET /mcp (SSE)--> http foot --stream--> /io/http/s3 (stream record, open socket)
                                                       mcp worker --poke event--> /io/http/s3
                           http foot --write event--> socket, until the client closes
```

## Status, 6 October

Step 1 is built on branch `ic-mcp` and verified in a running world through curl: the token is enforced; `initialize`, `ping`, `tools/list` and `tools/call` answer; every one of the twelve tools has run against the live world (`get-our-id`, `read`, `write` creating and changing, `delete`, `press` on a button and on a form with inputs, `list-mounts`, `list-files`, `get-file`, `commit`, `insert-file` with a compile that failed and one that passed, `install-app` with `replace`, `history`). A contract-refused write comes back as a refusal. A tool call takes about 150 ms; a commit about 2 seconds. Kernel changes: `ask` and request headers in `http_foot.foil` (64 lines); streaming deferred. Known gaps: `history` reports version counters only, because the kernel's inspect read leaves an application path's versions unreported; `insert-file` goes through the host companion until compile-from-text exists.

## Steps

Each step is usable on its own and ends with Claude Code or Codex connected: `claude mcp add --transport http shrine http://127.0.0.1:8440/mcp/<token>`.

### Step 1. The server and the node tools

**Kernel, existing files changed**

| File | Lines | What |
|---|---|---|
| `src/foil/http_foot.foil` | ~100 | `ask`; headers on `request` (done: 17 + 47 lines) |
| `src/foil/tests/http_foot.foil` | ~60 | Cases for ask and headers |
| `extras/mounts/web/browser_routes.foil`, `browser_request.foil` | ~10 | Request constructors gain the headers field |
| **Enki** `pkg/plan/src/rplan.c` | ~5 | Bind to localhost by default |

**New files, `extras/mounts/mcp/`**

| File | Lines | What |
|---|---|---|
| `mount.json` | 50 | Modules, `http` hook, `start` hook, route `/mcp`, host file |
| `host.py` | 40 | Issues the token into `~/.local/share/shrine/mcp/token`, prints the client command, copies the worker's outbox into the checkout at scan time |
| `mcp_mount.foil` | 110 | Install home and registry records; register the worker; the `/mcp` route: bearer check, POST to `ask`, GET to `stream` |
| `mcp_rpc.foil` | 150 | JSON-RPC 2.0 framing and MCP envelopes: initialize result, tool and resource listings, call results, error codes |
| `mcp_types.foil` | 220 | Tool, prompt, resource, template records and their JSON; parameter types string, number, boolean, array, object |
| `mcp_foot.foil` | 420 | The worker: request records in, one kernel message at a time, correlation of replies, response records out; open streams, `list_changed` and progress events poked onto them |
| `mcp_tools.foil` | 420 | Built-ins: `mcp/get-our-id`, `mcp/read` (scry), `mcp/write` (poke, make, cull), `mcp/press` (a view's control), `mcp/list-files`, `mcp/get-file`, `mcp/insert-file`, `mcp/commit` (rescan with located failures), `mcp/install-app`, `mcp/replace`, `mcp/list-mounts`, `mcp/history` |
| `mcp_tests.foil` | 160 | Framing, dispatch, each built-in against a fixture binding |
| `skills/shrine-mcp/SKILL.md` | 120 | The port of the skill: ground rules and workflows in Shrine terms |

Step 1: about 1,700 new, 200 changed (205 with Enki). Done when a client lists the tools, reads a record, writes one, and recompiles a mount with the failure text coming back.

### Step 2. Resources and prompts

| File | Lines | What |
|---|---|---|
| `extras/mounts/mcp/mcp_resources.foil` | 260 | `shrine://<path>` reads at a care; `file://<mount>/<name>` source records; `https://` by native fetch; templates with `{+path}` |
| `extras/mounts/mcp/mcp_prompts.foil` | 90 | Prompts as records; `prompts/get` fills arguments |
| `extras/mounts/mcp/defaults.foil` | 150 | Default resources (Foil reference, Grove example, the skill) and prompts mirroring the common tools |
| `mcp_rpc.foil`, `mcp_foot.foil` | ~80 changed | The four resource and prompt methods |

Step 2: about 500 new, 80 changed.

### Step 3. Other mounts publish their own tools

| File | Lines | What |
|---|---|---|
| `extras/mounts/mcp/mcp_import.foil` | 140 | `mcp/import-tools` and friends: read `/<node>/gov/<mount>/mcp/*` or a mount's `mcp` slot, register, dedupe by name |
| `extras/mounts/grove-dev/demo.grove` or a new `mcp.grove` | 60 | The first published tool set, as the worked example |
| `doc/mcp-publish.md` | 80 | The convention, with the Urbit `/x/mcp/*` paths beside it |

Step 3: about 280 new.

### Step 4. Code from text: `add-tool`, `test-build`, `dojo/command`

This is the Spider-thread half of the port and it needs the compiler reachable from a running world.

| File | Lines | What |
|---|---|---|
| **Enki** merge `ic-pure-op` | 158, written | Effect-free evaluation |
| `src/reaver/eden.rvr` | +150 | Compile a Foil module from text, compile one function, parse only, evaluate under `Pure` |
| `src/foil/helm.foil`, `src/foil/http_foot.foil` | +60 | A `compile` message for workers and its reply |
| `src/foil/grove_authoring.foil`, `src/foil/interaction_runtime.foil` | 93, port from `ic-wip` | Request and endpoint types |
| `extras/mounts/mcp/mcp_dojo.foil` | 160 | `dojo/command` with named sessions over `Pure`; `mcp/test-build`; `mcp/add-tool` from a Foil function body |
| `x/eden_mounts.py`, `x/eden` | ~120 | Accept a new mount while the world runs: scan bag, manifest check, scan bridge registration |
| `src/reaver/eden.rvr`, `src/foil/source_mount.foil`, `src/foil/eden.foil` | ~160 | Load, publish and activate a mount after boot; register its routes and worker |

Step 4: about 320 new, 490 changed, plus 158 written in Enki. The run-time mount is what makes `new-desk` and `mount-desk` live.

### Step 5. Chorus

Slips as records under `/<node>/chorus/cabinet/<drawer...>/<slug>` with author, time and text; `chorus/publish-slip`, `fetch-slip`, `discard-slip` published through step 3's convention; the daemon from `gwbtc/skills` pointed at a world. The spec for a ship and a world to share a cabinet waits on reading `gwbtc/chorus`, which is not public, and on Shrine networking for cross-node fetch.

| File | Lines | What |
|---|---|---|
| `extras/mounts/chorus/chorus.grove` | 120 | Slip and drawer types, views |
| `extras/mounts/chorus/chorus.foil` | 220 | The three tools, revision addressing, the 2,048-character rule |
| `doc/chorus-shrine.md` | 100 | The shared spec |

## Totals

| Step | New | Changed |
|---|---|---|
| 1 | 1,700 | 400, plus 5 in Enki |
| 2 | 500 | 80 |
| 3 | 280 | 0 |
| 4 | 320 | 490, plus 158 written in Enki |
| 5 | 440 | 0 |
| All | about 3,250 | about 970, plus 163 in Enki |

## Risks, in order

1. **The streaming change is the largest piece of kernel work in step 1** and the per-connection actor was written for one reply; the open-stream loop and the event forwarding are new ground on this foot.
2. **Compile-from-text does not exist.** Steps 1 to 3 do not need it; step 4 is the Spider half and is kernel work.
3. **Loading a mount at run time** touches the launcher, the scan bridge and the boot path; it is sized, not designed.
4. **Compile time grows with publications** in a long-lived world (about 0.1 s each, measured 5 Oct). Not understood; to be measured properly once the server runs for a day.
5. **Remote reads and shared cabinets across nodes** wait on networking, which is outside this plan.

## Not in this plan

Aqua, `fine://`, pills, remote ships, and anything from the earlier harness plan not listed here.
