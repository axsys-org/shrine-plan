# Cells over MCP: a ten-minute walkthrough

A Shrine world is a namespace of typed records. A cell is a record that
derives its value from other records, computed on read and never stored.
Agents make and read cells through four MCP tools: `mcp/read`, `mcp/write`,
`mcp/history`, `mcp/apply`.

## 1. Boot a world

From this checkout (Nix on the PATH for the explorer's bundle build; the
first explorer boot builds a Mash workspace and takes a while):

```bash
PATH=/nix/var/nix/profiles/default/bin:$PATH _EDEN_NIX_ROOT=$PWD WISP=<path to wisp> python3 x/eden --mount explorer --mount mcp --extras-root $PWD/extras --port 8300
```

Without the explorer, `--mount mcp` alone needs no Nix. The world prints
`Eden: http://127.0.0.1:8300; mounts: ...` when it is up. The MCP endpoint is
`http://127.0.0.1:8300/mcp`, local only, no credential.

## 2. Connect an agent

Claude Code:

```bash
claude mcp add --transport http shrine http://127.0.0.1:8300/mcp
```

Any MCP client that speaks JSON-RPC over HTTP works the same way. The skill
at `skills/shrine-mcp/SKILL.md` tells the agent the shape of a cell, every
standard formula and its parameters, the numbers convention and the notes
convention. Point the agent at it, or paste it into the system prompt.

## 3. The walkthrough, as tool calls

Write some data (one event each):

```
mcp/write  path=/user/demo/deals/d1  properties={amount: 50, status: "closed", owner: "ann"}
mcp/write  path=/user/demo/deals/d2  properties={amount: 70, status: "open",   owner: "bo"}
mcp/write  path=/user/demo/deals/d3  properties={amount: 25, status: "closed", owner: "ann"}
```

Find the standard cell to use and keep its reference (no event):

```
mcp/read   path=/weft/stdlib/sum care=x        ->  reference: /h/x/1/4/0x11/weft/stdlib/sum
```

Make a cell: weft is that reference, tack is a live reference to the input
(`/h/y/0/<segments>/<path>`), parameters are plain slots:

```
mcp/write  path=/user/demo/cells/revenue  properties={
  "sys/weft": {type: "reference", value: "/h/x/1/4/0x11/weft/stdlib/sum"},
  "sys/tack": {type: "reference", value: "/h/y/0/4/0x11/user/demo/deals"},
  slot: "/amount", into: "/revenue"}
```

Read it (no event), then change the input and read again:

```
mcp/read   path=/x/user/demo/cells/revenue care=x   ->  /revenue: 145
mcp/write  path=/user/demo/deals/d1 action=poke properties={amount: 60}
mcp/read   path=/x/user/demo/cells/revenue care=x   ->  /revenue: 155
```

Compose: a cell whose input is another cell's `/x`:

```
mcp/write  path=/user/demo/cells/closed   properties={sys/weft: <where>, sys/tack: <live deals>, key: "/status", value: "closed"}
mcp/write  path=/user/demo/cells/closed_revenue  properties={sys/weft: <sum>, sys/tack: {type: "reference", value: "/h/y/0/5/0x11/x/user/demo/cells/closed"}, slot: "/amount"}
```

Ask why when something is off (no event):

```
mcp/read   path=/c/x/user/demo/cells/revenue care=x   ->  the parameters it ran with; /sys/view/missing or /sys/view/fault when it could not
```

Freeze an answer: the `reference` on any read of `/x/<cell>` is a pinned
view that always reads the same value.

Override by hand without losing the formula: write a note beside the cell
with the answer slot, the value and the input's case (the case in the
cell's reference), then an `amend` cell over it:

```
mcp/write  path=/user/demo/cells/notes/n1  properties={slot: "/revenue", value: 80, case: 1}
mcp/write  path=/user/demo/cells/amended   properties={sys/weft: <amend>, sys/tack: <live /x/.../closed_revenue>, notes: <live .../cells/notes>}
mcp/read   path=/x/user/demo/cells/amended care=x     ->  /revenue: 80
mcp/read   path=/c/x/user/demo/cells/amended care=x   ->  /sys/view/note/n1 when the input has moved past the note's case
```

## 4. See it

The explorer at `http://127.0.0.1:8300/ns/0x11/user/demo` shows the records;
`/ns/x/0x11/user/demo/cells/revenue` shows a cell's current answer.

## 5. Check the whole library in one go

`tests/library.py` makes one cell per formula and checks every answer, the
error paths, a live write, pinning and amend, through MCP:

```bash
python3 -I -c "import runpy; runpy.run_path('extras/mounts/mcp/tests/library.py')['check']('http://127.0.0.1:8300', '0x11', 120)"
```
