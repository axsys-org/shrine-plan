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

- `/sys/weft`: a reference to a standard cell under `/weft/stdlib` (read the
  standard cell first and use its `reference`).
- `/sys/tack`: a reference to the input, y care. Case 0 is live:
  `/h/y/0/<len>/<path>` makes the cell follow the input; a pinned case freezes it.
- parameters: the cell's own slots, named per formula below. A number
  parameter is a literal (`"12.5"`), a slot of the input root (`/total`), or
  `/views/<name>/<slot>` of a secondary input. Any other slot holding a
  reference is a secondary input, reachable as `/views/<slot name>`.

Read `/x/<cell path>` for the result and `/c/x/<cell path>` for its context:
the parameters it ran with, `/sys/view/missing` when a parameter was absent
(the input then passes through unchanged), `/sys/view/fault` for a cycle, a
bad reference, or a live cell read at a pinned case. A faulted cell reads
unknown at `/x`; its context says why. A cell whose input is another cell's
`/x` composes. Results are computed on read and never stored.

### Numbers and dates

A number slot holds a natural. A record may carry `/scale`: every number in
that record is an integer scaled by ten to that power (`1250` with `/scale 2`
is 12.50). Formulas align scales to the larger one and write `/scale` on
their output root; `round` rescales to `/places`. Dates and durations are
numbers in their own unit and compare as such.

### The standard cells

| formula | parameters | result |
|---|---|---|
| `count` | `into` (default `/count`) | number of children |
| `sum`, `min`, `max`, `avg` | `slot`, `into` | the figure over the children's `slot`, with `/scale`; `avg` rounds half up |
| `any`, `all` | `slot`, `into` | whether any / every child's `slot` is true |
| `where` | `key`, `value`, `op` (equals, over, under, before, after, contains) | the matching children |
| `sort` | `slot`, `order` (asc, desc) | children re-keyed 1, 2, 3, old key at `/key` |
| `top` | `slot`, `count` (default 3) | the largest, ranked |
| `latest`, `earliest` | `slot` | the one child, as the root, key at `/key` |
| `each` | `left`, `op`, `right`, `into` | a derived slot per child; sides are literals or the child's slots |
| `lookup` | `key`, `take`, `match` (default `key`), `into`, `from` (default `table`) and a secondary input named by `from` | brings `take` from the matching table row |
| `distinct` | `slot` | rows with `/value` and `/count` |
| `select` | `slots` (space separated) | only those slots, on root and children |
| `by` | `key`, `op` (count, sum, min, max, avg), `slot`, `into` | one row per group value |
| `grid` | `row`, `col`, `op`, `slot` | rows by `row`, a slot per `col` |
| `flatten` | | every record below the root, keyed by path |
| `merge` | secondary inputs | the input's children plus theirs |
| `add`, `subtract`, `multiply`, `divide` | `left`, `right`, `into` | one figure on the root |
| `pick` | `from`, `into` | copies a slot (also `/views/...`) onto the root |
| `put` | `into`, `value` | sets a literal on the root |
| `round` | `slot`, `places`, `into` | rescales a root number |
| `since` | `slot`, `from`, `into` | `slot` minus `from` |
| `between` | `slot`, `from`, `to` | children within the range |
| `amend` | `notes` (default `notes`) and a secondary input of that name | the input with notes laid over it |

### Hand edits that survive recomputation

Keep overrides beside a cell, in a notes folder: each note is a record with
`/slot` (the answer slot it changes), `/value`, and `/case` (the input's x
case when the note was written; read the input cell and copy its
reference's case). Make a cell with `amend`: its tack is the computed cell's
`/x`, and a slot named `notes` references the folder. On read, `amend` lays
each note over the answer. A note whose case equals the input's current case
applies quietly; a note behind it still applies and `/c/x` reports it at
`/sys/view/note/<key>` ("note at case N, input now at case M").
`/sys/view/amended` counts the notes. Removing a note is deleting its
record. Nothing is cached or replayed.

A note's `/slot` is a slot of the answer's root (`/revenue`), or a path into
the answer tree with the slot last (`/d1/amount` corrects one row of a
`where` result, `/eng/total` one leaf of a `by` breakdown). The record at
that path must already exist in the answer; otherwise `/c/x` reports the
note as dangling ("no record at /d9 in the answer") and nothing is created.

Example: count the members of a team.

```
write /user/org/views/headcount
  sys/weft  {type: reference, value: <reference of /weft/stdlib/count>}
  sys/tack  {type: reference, value: /h/y/0/4/0x11/user/org/members}
  into      /headcount
read /x/user/org/views/headcount   ->  /headcount: 2
```
