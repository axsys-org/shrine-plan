# Codex desk

See the [shared harness ownership map](../../HARNESS.md) for responsibilities
and integration boundaries.

A flat source bag in `extras/mounts/codex`. This desk includes the
protocol reducer, JSON boundary validation, I/O foot, mount-aware host
helpers, Python app-server bridge, and regression tests.

## Mount and activate

From the core checkout:

```sh
x/eden --mount codex
x/eden --mount codex --mount srs --check
```

Source records live at `/<node>/io/fs/codex/source`, published definitions
retain their logical module identities, and the driver runs at
`/<node>/io/codex`. `mount.json` declares module mappings, dependencies,
activation and the host companion. Set `CODEX_BIN` to select the executable.
`--check` uses the fake server. The host entrypoint owns bridge cleanup.
Rescans publish source changes; replacing the live driver requires a restart.

For manual embedding, use the bridge and driver entrypoints below.

Run `python3 /path/to/shrine/extras/mounts/codex/bridge.py` from the workspace Codex should
operate in. It prints a private loopback port and token, then waits for
the foot. `--codex /path/to/codex` selects the executable. The bridge starts
`codex app-server --listen stdio://` only after the foot authenticates.
Keep it running for the connection; Ctrl-C closes the child process.

After compiling the desk, use an existing trusted namespace supervisor:

```foil
| codex_driver/install server [self 'io 'codex] port token
```

The runtime home is supplied explicitly and may be elsewhere under the
same node. It is independent of the mounted source location. `install`
creates the runtime record and explicitly registers `codex_foot/run`;
it is for a fresh, unregistered home. It does not start another sovereign.

All host helpers take `server home`: `submit` also takes a fresh command
key and record; `reply` takes an effect key, JSON payload and error flag;
`snapshot` returns the home's current care-y view. Build command records
with `codex/start`, `codex/steer` and `codex/interrupt`. Start takes a JSON
input array, an options object, and an optional existing thread ID.

Slot paths are exported by `codex_slots`; do not use bare global keys
such as `/kind` or `/payload`. They are publisher-owned and preserve their
identity when a driver instance is mounted elsewhere. JSON-RPC field
names remain the app-server's ordinary strings.

Approval and question requests appear as `request-effect` records.
Reply explicitly; the bridge never approves requests or interprets RPC.
The installed Codex CLI retains its existing authentication, sandbox and
approval configuration. A normal mount starts the configured Codex server; checks use a fake child.

## Check the port

```sh
WISP=/path/to/wisp extras/x/check --mount codex
python3 extras/mounts/codex/codex_bridge_tests.py
```

The Foil check stages the desk as compiler inputs in an isolated source
copy, compiles the host helper, and runs reducer/foot regressions against
this checkout. The runner prints its temporary results directory. Transport tests
use local sockets and fake child processes; they need no Codex account.

The driver retains its original limits: one connection, no reconnect or
automatic replay, explicit replies to server requests, 4 MiB frames and
a bounded write queue. Pre-existing commands are marked unresolved at
registration rather than replayed. Multiple Codex threads can share the
connection. Separate mounted driver instances use separate bridges.

### Shrine console

With `x/eden --mount codex`, open `/ns/0x11/io/codex` on Eden’s URL. Its face is a
prompt composer and a live event log. Leave Thread ID empty to start a
new thread; use the thread ID shown in events to continue it. Steer and
interrupt additionally require the active turn ID.

Pending server requests appear as explicit reply forms. Enter the JSON
result required by the displayed method and parameters, or select Error
and enter a JSON-RPC error object. Ordinary console requests remain manual;
the explicitly selected native surface provider answers its own tool calls as
described below. Drafts survive polling and failed submissions.

The UI hand converts form submissions into ordinary command children,
and replies into writes on pending request records. `codex_ui.foil`
contains the hand and HTTP face; `codex_driver/install` registers both
beneath the driver. The console does not expose bridge credentials.
`x/eden --check --mount codex` uses a fake server to exercise prompting,
streaming, answering a request, and interrupting through HTTP.

Run `node extras/mounts/codex/codex_ui_browser_tests.cjs` to check the
browser submit handler, including form fields that shadow DOM properties.

## Shared harness provider

The mount also publishes `/<node>/io/codex/work_provider`, a native
`native_work/provider`. `codex_work` is a hand that dispatches one normal bridge
command, watches its acknowledgment, then subscribes to a stable typed turn
completion record. It returns a shared work outcome and frozen result with the
original guard capture. Both `cooperate/delegate` and authored flows can use it.
There is no additional Python worker loop.

Provider requests select the bridge's internal `retainDeltas: false` option.
Their final messages, lifecycle events, errors and explicit server requests are
retained; streamed text/reasoning deltas do not create a namespace write per
token. Ordinary console requests retain streaming. This option is consumed by
the native reducer and is not sent as an app-server protocol field.

The reducer records final agent-message text by thread and turn; completion can
arrive before the start acknowledgment. Failed/interrupted/disconnected turns do
not become successful work. The default `work_provider` does not automatically
replay uncertain commands or answer server requests. Domain admission remains
with the caller.

## Interactive document work

`/<node>/io/codex/surface_provider` is an explicit native agent capability for an
open Cooperate investigation or a deliberately authored interactive flow task. Select it through `cooperate/delegate` (also exposed by Nenex's
declared **Delegate native work** control). Supply a guard on the evidence or
instructions that authorize the activity. Editing that guard invalidates further
tool calls; editing the working document need not invalidate an independent guard.
The ordinary `work_provider` and the inert document-revision policy keep their
existing behavior.

The surface provider supplies three app-server dynamic tools:

- `shrine_read` reads native records, evaluated cells and overlay projections.
  Care remains native: x is one record, y its nearest live frontier, z its
  subtree. Existing `/x` and `/o` paths select computed cells and overlays.
  Child pages carry a retained local-world epoch and use the existing frozen
  namespace reader, including its selected system publication, so tool receipts
  do not invalidate the continuation. An unavailable current source returns failure;
  an explicitly retained epoch is historical evidence.
- `shrine_actions` reflects matching published Goo controls, input encodings and
  the object's current version guards. It uses the browser's catalogue cache
  when installed. Rich text inputs include an example using the existing codec.
- `shrine_act` invokes one of those controls through Goo and shared admission.
  Native work supplies the invocation identity and retains the action receipt.

Each server request remains an ordinary bridge request record. Its initialization
creates one native task in `<worker>/trace/<effect-key>` and links it into the
worker’s trace. That hand subscribes to the exact worker, start command and I/O
request; `/io` itself remains outside native observer indexes. The hand waits for
the turn acknowledgement, validates thread/turn identity and emits the existing
native command. Accepted effects, the tool reply and the settled task are admitted
together. A bridge failure settles the task and removes its subscriptions before
a retried acknowledgement can replay it. The transport sends the retained reply;
it does not choose the next action. Codex's existing turn makes that choice.
Recovery settles retained workers before reinstalling their forms, and uncertain
turns are never replayed automatically.

Flows select this capability through `flow_request_ops/interactive_requests`, with
`tasks` and `provider` inputs. Each task is an ordinary record containing the
existing `work/prompt` and `work/schema` fields; the provider input is the selected
record containing `work/provider`. The operation captures the selection in the
same native request, hole, worker, evidence and result records as other flow steps.
A captured native authorization operation checks that the controller remains
attached and enabled, the task is still current and the hole still selects this
attempt before each tool call. Pausing, detaching, changing evidence or settling
the request removes that authority. Failures and retries retain the same normal
work history. Document-revision requests do not acquire this delegation.
It operates under the mounted sovereign's existing application authority;
investigation ownership is not a per-document sandbox. There is no additional
tool registry, provider scheduler or Python agent loop. App-server dynamic tools
are an experimental protocol feature; the checked schemas come from the installed
`codex app-server generate-json-schema --experimental` command.

Discovery currently covers ordinary matching views. Hosted pane navigation and
controls requiring an active Goo selection are not yet a complete headless path;
selection inputs are marked as such and have no synthetic example. Reads page
immediate children without counting the whole subtree, but rendering one record's
values is not a bound on total evaluation or response size.
