# Grove patch application

This is a real, disposable namespace application, not the Mash fixture harness.
`main.grove` publishes an ordinary Goo pane and a typed `@action`. The application
stores placement and a single directed connection on its board record. Its Foil
handler checks current occurrence lifetimes, original positions, topology and port
roles before changing that record; settled routes are calculated on the server.
The small single-connection policy belongs to this example, not to `goo-patch`.

## Run this checkout

Run Reaver with the locked runtime and the published Mash revision selected by
`extras/flake.nix` and `extras/flake.lock`:

```sh
cd /Users/test/dev/reaver
nix develop .#eden --command python3 x/eden --mount patch-demo --port 8092
```

Open `http://127.0.0.1:8092/views/0x11/app/patch_demo/board`.
This launch creates a disposable Eden namespace; reload the browser to verify
saved state within that namespace. It does not edit an existing user installation.

Move nodes with their handles or named buttons. Click `source out`, then `sink in`
to connect. The server returns the settled line. Use the connection table to
reconnect an endpoint or disconnect. The ordinary input/action controls exercise
the same bound operation using JSON arguments.

Explorer's immutable Mash pin includes the patch package at commit
`16b8a9079e8a45dc2681cf3210e1d186e5cbe622`. No local renderer override is needed.
For local Mash development, first run `pnpm --filter @mash/shrine build` in the
Mash checkout, then set `GOO_PATCH_MASH_ROOT=/Users/test/dev/mash` when starting
Eden. That option builds only the patch renderer from the development checkout;
other topoi and the verified Goo profile continue to use the production pin.

## Author a patch pane

The shape used by `main.grove` is:

```grove
editor =
  @pane
  #on ; %/board
  #for ; /sys/slot/content
  board => patch('/canvas, scene = board.scene, label = "Board") {
    patch_node("source") {
      patch_handle("move", label = "Move source")
      show("Source", '/sys/slot/title)
      patch_port("out", label = "Source output")
    }
    patch_connection("wire") {}
    patch_operation("move-nodes", slot = '/0x11/gov/patch_demo/operation) {
      group(on = board, action = %/edit, myth = {
        %/operation = .input("")
      }) {
        input('/0x11/gov/patch_demo/operation)
        action("Apply move")
      }
    }
  }
```

The example is a fragment: every realized node, port and connection label must
have matching declarations. `board.scene` is JSON text containing a complete
resolved `SceneSnapshot`; it is not a graph that the browser lays out. Ordinary
Goo bodies are prepared at each node's supplied width. Ports and move handles
are direct occurrence children, outside scrolling body content. A
`patch_label("caption") { ... }` supplies a connection's ordinary Goo label.

Each `patch_operation` contains one existing bound action and names its declared
input slot. Scene `offers` reference those operation keys (for example
`moveNodes: "move-nodes"`). The input receives the contract's JSON `IntentArgs`.
The server action must validate them against its own current domain state. A
client port hint never grants permission. No JavaScript handler is required in a
Grove application.

The current host integrates move/connect/reconnect/disconnect and group selection.
Domain-specific picker/context/compatibility query presentations are not provided
by this example; leave their offers absent. Unknown compatibility still goes
through real action admission. Creation requires a domain-specific offered choice
and is not offered by this board.

## Shared runtime behavior

- `GooPanes` owns work, input preservation, composition deferral and retirement.
- `GooSession` owns the patch's bounded multiple-selection projection. Scalar
  followers cannot silently treat a group as one accepted subject.
- `GooActions` captures the same receiver, control, evidence and invocation for
  native and graphical operations. Accepted graphical actions call the same
  refresh callback as ordinary controls.
- `/goo/render` snapshots include `projectionSeq` from the namespace event count.
  It orders complete presentations; source/layout revisions remain opaque.
- `coveredOperationIds` comes from the namespace's existing committed invocation
  journal for this target. It is not inferred from geometry or revision equality.
- `/goo/operation-status` consults that journal. Missing receipts mean `unknown`,
  never an invented rejection. The existing journal is bounded at 1024 entries.

## Checks

```sh
nix develop .#eden --command python3 extras/x/check --mount patch-demo
node --test extras/mounts/explorer/tests/*.test.cjs
node extras/mounts/explorer/scripts/check-patch-browser.mjs \
  http://127.0.0.1:8092 /Users/test/dev/mash /tmp/goo-patch-live
```

The browser gate uses actual `/goo/render` and `/goo/act` responses and validates
movement persistence after reload, server-created connections, reconnect and
disconnect, native/graphical binding equivalence, rejected stale lifetimes,
altered receivers and control bindings, operation status and projection coverage.
It does not mock domain decisions.
