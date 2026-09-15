# Codex desk

A flat source bag ported from the Codex driver in the sibling `reaver`
checkout. The original checkout is unchanged. This desk includes the
protocol reducer, JSON boundary validation, I/O foot, mount-aware host
helpers, Python app-server bridge, and regression tests.

## Mount the source bag

Create a filesystem-sync child at `/<self>/io/fs/<text-id>` using:

```foil
| fs/cfg "desks/codex" [self 'desks 'codex]
  (fs/extensions (mop/empty)) [self 'kook 'fs]
```

Poke `/sys/pending` to true on that child. The desk's immediate files
appear at `/<self>/desks/codex/<filename>` with raw byte bars in
`/sys/content`. Nothing in the desk requires recursion or disk folders
below the desk root. The directory operand is relative to Eden's file
root, currently its staged copy of `src`.

The empty extension map mounts source only. Once a Foil compiler hand
is installed, supply its canonical path under the `($ta "foil")` key
to compile these files. The mounted record paths are not automatically
compiler module addresses: a compiler/resolver must give the five module
names in `desk.json` their defining publication locations and resolve
standard-library imports. `desk.json` is an inventory, not an executable
installer. The current FS driver does not yet compile or register feet.

## Activate the driver explicitly

Eden can stage, compile and register this desk automatically:

```sh
x/eden --node 0x11 --codex
```

Add `--srs` to enable both integrations. `--codex-bin` selects the CLI;
`--check --codex` runs against the fake server. The launcher owns bridge
cleanup. For another host, use the manual setup below.

Run `python3 src/desks/codex/bridge.py` from the workspace Codex should
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
approval configuration. No live Codex process is started by mounting or
checking this desk.

## Check the port

```sh
WISP=/path/to/wisp python3 src/desks/codex/check.py
python3 src/desks/codex/codex_bridge_tests.py
```

The Foil check stages the desk as compiler inputs in an isolated source
copy, compiles the host helper, and runs reducer/foot regressions against
this checkout. Results remain under `.check/codex-desk-*`. Transport tests
use local sockets and fake child processes; they need no Codex account.

The driver retains its original limits: one connection, no reconnect or
automatic replay, explicit replies to server requests, 4 MiB frames and
a bounded write queue. Pre-existing commands are marked unresolved at
registration rather than replayed. Multiple Codex threads can share the
connection. Separate mounted driver instances use separate bridges.

### Shrine console

With `x/eden --codex`, open the printed Codex driver URL. Its face is a
prompt composer and a live event log. Leave Thread ID empty to start a
new thread; use the thread ID shown in events to continue it. Steer and
interrupt additionally require the active turn ID.

Pending server requests appear as explicit reply forms. Enter the JSON
result required by the displayed method and parameters, or select Error
and enter a JSON-RPC error object. Nothing approves or answers a request
automatically. Drafts survive polling and failed submissions.

The UI hand converts form submissions into ordinary command children,
and replies into writes on pending request records. `codex_ui.foil`
contains the hand and HTTP face; `codex_driver/install` registers both
beneath the driver. The console does not expose bridge credentials.
`x/eden --check --codex` uses a fake server to exercise prompting,
streaming, answering a request, and interrupting through HTTP.

Run `node src/desks/codex/codex_ui_browser_tests.cjs` to check the
browser submit handler, including form fields that shadow DOM properties.
