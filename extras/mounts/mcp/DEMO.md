# Cells over MCP: a ten-minute walkthrough

A Shrine world is a namespace of typed records. A cell is a record that
derives its value from other records, computed on read and never stored.
Agents make and read cells through four MCP tools: `mcp/read`, `mcp/write`,
`mcp/history`, `mcp/apply`.

## 1. Boot a world

From this checkout, with Nix on the PATH (`x/eden` enters its own Nix shell;
the first boot with the explorer builds the browser bundles and takes a few
minutes):

```bash
python3 x/eden --ephemeral --mount mcp --mount probe --mount explorer --mount inspector --extras-root "$PWD/extras" --port 8300
```

The world prints `Eden: http://127.0.0.1:8300; mounts: ...` when it is up. The
MCP endpoint is `http://127.0.0.1:8300/mcp`, local only, no credential. This
creates a disposable world. [SETUP.md](SETUP.md) explains durable worlds, resuming them
and connecting native providers. This walkthrough writes sample data; use a
free port and a disposable world.

## 2. Connect an agent

Claude Code:

```bash
claude mcp add --transport http shrine http://127.0.0.1:8300/mcp
```

Any MCP client that speaks JSON-RPC over HTTP works the same way. Use
`tools/list` for the current tool schemas and read `/weft/stdlib` to inspect the
installed cell definitions. The [harness guide](../../HARNESS.md) explains
captures, cells and the native work lifecycle.

## 3. The walkthrough, as tool calls

Write some data (one call, one event, one history entry naming the four paths; the folder gets a record of its own so its cases track its children):

```
mcp/write  records=[{path: /user/demo/deals,    slots: {title: "Deals"}},
                    {path: /user/demo/deals/d1, slots: {amount: 50, status: "closed", owner: "ann"}},
                    {path: /user/demo/deals/d2, slots: {amount: 70, status: "open",   owner: "bo"}},
                    {path: /user/demo/deals/d3, slots: {amount: 25, status: "closed", owner: "ann"}}]
```

Find the standard cell to use and keep its reference (no event):

```
mcp/read   path=/weft/stdlib/sum care=x        ->  reference: /h/x/1/4/0x11/weft/stdlib/sum
```

Make a cell, beside the data and never inside the folder it reads: weft is
that reference, tack is a reference to the input at a care (case 0 is live),
parameters are plain slots:

```
mcp/write  records=[{path: /user/demo/cells/revenue, slots: {
  "sys/weft": {type: "reference", value: "/h/x/1/4/0x11/weft/stdlib/sum"},
  "sys/tack": {type: "reference", path: "/0x11/user/demo/deals", care: "y", case: 0},
  slot: "/amount", into: "/revenue"}}]
```

Read it (no event), then change the input and read again:

```
mcp/read   path=/x/user/demo/cells/revenue care=x   ->  /revenue: 145
mcp/write  records=[{path: /user/demo/deals/d1, action: poke, slots: {amount: 60}}]
mcp/read   path=/x/user/demo/cells/revenue care=x   ->  /revenue: 155
```

Compose: a cell whose input is another cell's `/x`:

```
mcp/write  records=[{path: /user/demo/cells/closed, slots: {sys/weft: <where>, sys/tack: <deals, care y>, key: "/status", value: "closed"}}]
mcp/write  records=[{path: /user/demo/cells/closed_revenue, slots: {sys/weft: <sum>, sys/tack: {type: "reference", path: "/x/0x11/user/demo/cells/closed", care: "y", case: 0}, slot: "/amount"}}]
```

Ask why when something is off (no event):

```
mcp/read   path=/c/x/user/demo/cells/revenue care=x   ->  the parameters it ran with; /sys/view/missing or /sys/view/fault when it could not
```

Freeze an answer: the `reference` on any read of `/x/<cell>` is a pinned
view that always reads the same value.

Override by hand without losing the formula: write a note beside the cell
with the answer slot, the value and the input's case (`/sys/tack/case` in
the computed cell's `/c/x`), then an `amend` cell over it:

```
mcp/write  records=[{path: /user/demo/cells/notes/n1, slots: {slot: "/revenue", value: 80, case: 1}}]
mcp/write  records=[{path: /user/demo/cells/amended, slots: {sys/weft: <amend>, sys/tack: </x/.../closed_revenue, care y>, notes: <.../cells/notes, care y>}}]
mcp/read   path=/x/user/demo/cells/amended care=x     ->  /revenue: 80
mcp/read   path=/c/x/user/demo/cells/amended care=x   ->  /sys/view/note/n1 when the input has moved past the note's case
```

## 4. See it

The live page at `http://127.0.0.1:8300/live?views=/0x11/user/demo/cells`
is the optional read-only inspector selected above. It shows cells and retained
history; `mcp/history` also exposes that history as records. Authoring and work
controls belong to the declared Goo surfaces in Nenex and the native MCP tools.

## 5. Check the whole library in one go

`tests/library.py` makes one cell per formula and checks every answer, the
error paths, a live write, pinning and amend, through MCP:

```bash
python3 -I -c "import runpy; runpy.run_path('extras/mounts/mcp/tests/library.py')['check']('http://127.0.0.1:8300', '0x11', 120)"
```
