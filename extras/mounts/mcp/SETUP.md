# Setup: native snapshots

From the checkout, with Nix on `PATH`, choose an explicit native snapshot directory:

```sh
python3 x/eden --snapshot "$PWD/.check/lab/snap" \
  --mount flow-authoring --extras-root "$PWD/extras" --port 8300
```

The `flow-authoring` mount selects Nenex, Cooperate, Cells, Goo and MCP through its
dependencies. Add `--mount codex` when creating the world to select the native
Codex provider and its existing app-server transport. No separate Python hand
or hand manager is needed. Provider setup is documented in the
[Codex mount](../codex/README.md); the
[harness guide](../../HARNESS.md) describes the shared lifecycle.

`x/eden` prepares its Nix environment. A cold compiler and browser-bundle build
can take several minutes. Wait for the `Eden:` readiness line before opening:

- [Nenex](http://127.0.0.1:8300/nenex)
- [MCP](http://127.0.0.1:8300/mcp)

For the optional [read-only Cells and history inspector](../inspector/README.md),
include `--mount inspector` when creating the world, then open
[`/live?views=/0x11/user`](http://127.0.0.1:8300/live?views=/0x11/user).
It is separate from the declared Goo document and namespace views. Selecting
`mcp` or `flows` alone does not install `/live`; direct native MCP operations
remain usable without that interface. The native root captures its mount contracts;
adding this flag on restart is not an in-place interface upgrade.

Use another free port and a different directory for a separate world. A world
snapshot is exclusively locked by the runtime while running. Compilation and retained arenas
can require substantial memory and disk; do not use an occupied live directory
for a disposable check.

## Resume the same world

Stop with Ctrl-C. Resume with the same snapshot, node and mount selection:

```sh
python3 x/eden --snapshot "$PWD/.check/lab/snap" \
  --mount flow-authoring --extras-root "$PWD/extras" --port 8300
```

The native saved continuation retains records, x/y/z history, cells, work,
holes and captured definitions. Admission saves changed state before
acknowledgement. The launcher reconnects process resources; it does not replay
an export, replace the retained service/compiler, or upgrade old core types.
Supply mount selection and source locations explicitly on each launch. The
native root checks the node and mount descriptors before any new commit.
Behavior publication follows the explicit contracts described in the harness
guide. A checkout update alone is not a saved-core upgrade.

For the smaller MCP/probe/explorer selection, `python3 x/setup --snapshot DIR`
wraps this same launcher. Neither launcher remembers directories or settings.
Without `--snapshot`, the run is disposable. `--ephemeral` explicitly selects
that default; `--check` validates a disposable run. Both reject `--snapshot`.
Only the native arena and its lock files persist at the selected path; temporary
source copies, host credentials and launch logs are cleaned up when the process exits.

## Connect an agent

Connect any HTTP MCP client to `http://127.0.0.1:8300/mcp`. `tools/list`
describes the four tools: `mcp/read`, `mcp/write`, `mcp/history` and
`mcp/apply`. The endpoint is local and has no credential. Native admission
checks writes and operation inputs; accepted reactions share the transaction.

An agent can inspect cells, discover declared controls, invoke native operations
and retain work in the same world as the browser. See
[Cooperate](../cooperate/README.md), [flow authoring](../flows/README.md)
and [Nenex](../nenex/README.md) for those contracts. The optional
[flow examples](../flow-examples/README.md) include authored web-evidence and
cartography procedures using those same contracts. Prose mentions do not create
native references; use typed reference values.

## Check a disposable world

Run selected native suites and the checked mount-entrypoint gate:

```sh
bash x/check foil:tests/namespace_command foil:tests/semidoc
python3 extras/x/check --mount flow-authoring --mount codex --contracts-only
```

These prepare disposable test fixtures. Existing saved worlds are not test
fixtures. Native arena compaction is an explicitly requested offline prototype
maintenance strategy: it preserves the reachable world and retained history,
requires downtime and temporary disk space, and leaves automatic reclamation
and its performance characteristics unresolved.
