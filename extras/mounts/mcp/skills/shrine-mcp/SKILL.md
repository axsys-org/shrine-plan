---
name: shrine-mcp
description: >-
  Operate a Shrine world through its MCP mount: read and write typed records, make cells that derive values from other records, and read history.
---

# Shrine MCP

The world serves `<world-url>/mcp` (local only, no credential). Four tools:
`mcp/read`, `mcp/write`, `mcp/history`, `mcp/apply`. Everything else is a path.
Paths are segmented namespace addresses: `/0x11/user/org/teams` or, relative
to the node, `/user/org/teams`. Keep the exact paths Shrine returns.

A read is inert (no event): it returns the record's slots as text, its
children, whether it exists, and a pinned reference `/h/x/<case>/<len>/<path>`
that always reads the same value. `care` chooses how much: `x` the record,
`y` the record and its children (default), `z` the whole subtree.

A write is one event: `properties` maps slot names to values. Plain text,
numbers and booleans are stored as such; `{type, value}` makes an exact
`nat`, `str`, `bool`, `path` or `reference`. A write creates or replaces the
whole record; `action: poke` merges slots into an existing record and
`action: cull` deletes the subtree.

## Cells

A cell is a record that derives its value from other records. It has
three kinds of slots:

- `/sys/weft`: a reference to a standard cell under `/weft/stdlib`
  (`count`, `sum`, `where`, `add`, `subtract`, `multiply`, `divide`). Read the
  standard cell first and use its `reference`.
- `/sys/tack`: a reference to the input, y care. Case 0 is live:
  `/h/y/0/<len>/<path>` makes the cell follow the input; a pinned case freezes it.
- parameters: the cell's own slots (`slot`, `into`, `key`, `value`, `left`,
  `right`). A number is a literal; a path reads a slot of the input's root;
  `/views/<name>/<slot>` reads a secondary input, which is any other slot
  holding a reference.

Read `/x/<cell path>` for the result and `/c/x/<cell path>` for its context:
the parameters it ran with, `/missing` when a parameter was absent, `/fault`
for a cycle, a bad reference, or a live cell read at a pinned case. A cell
always reads: a failed cell is an empty tree with the reason in its context. A cell whose input is another
cell's `/x` composes. Results are computed on read and never stored.

Example: count the members of a team.

```
write /user/org/views/headcount
  sys/weft  {type: reference, value: <reference of /weft/stdlib/count>}
  sys/tack  {type: reference, value: /h/y/0/4/0x11/user/org/members}
  into      /headcount
read /x/user/org/views/headcount   ->  /headcount: 2
```
