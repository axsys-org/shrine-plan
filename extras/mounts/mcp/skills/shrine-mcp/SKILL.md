---
name: shrine-mcp
description: >-
  Operate a Shrine world through its MCP mount: read and write typed records, make cells that derive values from other records, and read history.
---

# Shrine MCP

The world serves `<world-url>/mcp` on localhost only, with no credential: it is
reachable from the machine running the world and from nothing else, and
anything that can reach it can read and write the world. Three tools plus
`apply`; every field after the first is optional:

```
read     path                               a record, a folder, /x/<cell>, /c/x/<cell>, /h/...
         care     x | y | z                 how deep; default y
         case     0                         0 live, or a case to read as of then
         formula  where                     run a standard cell over what was read; no record made
         settings {key: "/status", value: "closed"}
         limit    100                       nodes per answer, in tap order (a node, then its children by name); never more than 500
         next     <cursor>                  the next a previous page answered: continue after it
         -> the tree (root slots, children, each with its pinned reference), nodes, next; or unknown with the reason in /c/x

write    records  [{path, slots, action}, ...]   one or many, one event, admitted whole or refused whole
         from     /h/x/3/<path>             on a record: copy it as it was at that case (undo, redo)
         then     [/x/<cell>, /c/x/<cell>]  paths to read after the commit, in the same answer
         -> epoch, each record's new reference, then the reads; or the refusal and nothing written

history  path                               a record's cases newest first with references and slots
         before, limit                      without a path: the event log newest first, each epoch with
                                            the paths it touched, and a next cursor

apply    path, operation, inputs, then      an op a record carries; cells never need it
```

Slot values are plain text, numbers and booleans, or `{type, value}` for an
exact `nat`, `str`, `bool`, `path` or `reference`; a reference is spelled
`/h/<care>/<case>/<len>/<path>` and case 0 means live. A cell is a record
whose slots include a formula reference and an input reference; nothing in
the schema knows the word cell.

A read is inert (no event): it returns the record's slots as text, its
children, whether it exists, and a pinned reference `/h/x/<case>/<len>/<path>`
that always reads the same value. The root of an answer also carries
`reference_y` and `reference_z`, the pinned y and z views a tack uses to
freeze an input; children carry `reference` only (read a child to pin it). `care` chooses how much: `x` the record,
`y` the record and its children (default), `z` the whole subtree.

An answer is at most `limit` nodes (default 100, never more than 500),
counted in tap order: a node, then its children by name, so a page is the
tree cut at the same place for the same case and can be re-read. When
nodes remain the answer names `next`, the last path it rendered; the same
read with that `next` continues from there, and a node an earlier page
rendered that still has children comes back as a shell (`paged: true`,
path and children only). The cap is what bounds the cost of any one call
to the world: ask a folder a question with `formula` and page what is left,
never read the world.

A write is one event, however many records it carries: `properties` (or
`slots`) maps slot names to values.
Plain text, numbers and booleans are stored as such; `{type, value}` makes
an exact `nat`, `str`, `bool`, `path` or `reference`. A write creates or
replaces the whole record; `action: poke` merges slots into an existing
record and `action: cull` deletes the subtree. A culled path refuses writes
beneath it until the culled record is written again, so delete-and-recreate
is one batch: `records: [{path: <folder>, slots: {}}, {path: <folder>/a, ...}]`
revives the folder and refills it in one event. History keeps every case on
either side of the cull.

Fewer calls:

- Several records in one call: `records: [{path, properties, action}, ...]`
  are one event, admitted whole or refused whole, and one history entry
  naming every path (a derived path refuses the batch before any event).
  Seed a folder or lay down a three-cell chain in one write.
- To see what a write changed, name the cells in `then`: the answer carries
  their `/x` and `/c/x` on the admitted state, in the same call.
- Undo and redo are writes from history: `records: [{path, from: <reference
  of an earlier case>}]` writes that case's content back as a new event, so
  history keeps everything. A path with no record at that case is refused
  and nothing is written.
- Reads cost nothing and do not depend on each other: issue them together.
- To search without making a cell, read a folder with a formula:
  `read path=/user/org/deals care=y formula=where settings={key: "/status",
  value: "closed"}`. No event, no record, the same evaluation as a cell; to
  keep the question answered, write the same formula and settings as a cell.
- The formulas and their settings are listed below; there is no need to read
  `/weft/stdlib` to discover them, only to fetch a reference for a cell's weft.
- The answer is the result; nothing needs narrating back.

## Cells

A cell is a record that derives its value from other records. It has
three kinds of slots:

- `/sys/weft`: a reference to a standard cell under `/weft/stdlib` (read the
  standard cell first and use its `reference`).
- `/sys/tack`: a reference to the input at a care: `x` the record alone,
  `y` the record and its children, `z` the whole subtree (interior records
  included). Case 0 is live: `/h/y/0/<len>/<path>` makes the cell follow the
  input; a pinned case freezes it. A folder with no record of its own is a
  fine input (its children are the rows) but has no case of its own to pin
  or stamp against: write a record at the folder (even an empty one) and
  its cases track its children from then on.
- parameters: the cell's own slots, named per formula below. A number
  parameter is a literal (`"12.5"`), a slot of the input root (`/total`), or
  `/views/<name>/<slot>` of a secondary input. Any other slot holding a
  reference is a secondary input, reachable as `/views/<slot name>`.
  A live secondary input that resolves to nothing is an empty view, noted at
  `/sys/view/empty/<name>` in `/c/x`; a pinned one, and the tack, must exist.

Ranking (`sort`, `top`, `latest`, `earliest`) and the reductions (`sum`, `min`,
`max`, `avg`) are by number: a row whose slot is absent or text is left out;
there is no text ordering.

Three conventions hold in every formula:

- The rows of an input are every record below its root at the tack's care:
  a `y` input's children, a `z` input's whole subtree, interior records
  included. Reducers (`count`, `sum`, ...) fold over all of them; row
  formulas (`where`, `sort`, `by`, ...) keep each row at its own path, so
  a `z` result keeps the folder structure.
- A child's name is addressable as a slot called `name` in any setting
  (`where key=/name value=beta`, `select slots=/name`, `by key=/name`,
  `lookup key=/name`); a record that carries its own `/name` slot wins.
- A formula sees only its inputs. It cannot follow a reference held in a
  slot: a `reference` value is data to it, nothing more. To bring in another
  record, make it a secondary input and use `lookup` against that named
  view; that is the join.

Read `/x/<cell path>` for the result and `/c/x/<cell path>` for its context:
the parameters it ran with, `/sys/view/missing` when a parameter was absent
(the input then passes through unchanged), `/sys/view/fault` for a cycle, a
bad reference, or a live cell read at a pinned case. A faulted cell reads
unknown at `/x`; its context says why. A cell whose input is another cell's
`/x` composes. Results are computed on read and never stored.

### Numbers and dates

A number slot holds a natural. A record may carry `/scale`: every number in
that record is an integer scaled by ten to that power (`1250` with `/scale 2`
is 12.50); `<slot>/scale` scales one slot only (`amount/scale: 2` leaves
`/when` whole). Formulas align scales to the larger one and write `/scale` on
their output root; `round` rescales to `/places`. Dates and durations are
numbers in their own unit and compare as such.

### The standard cells

| formula | parameters | result |
|---|---|---|
| `count` | `into` (default `/count`) | number of children |
| `sum`, `min`, `max`, `avg` | `slot`, `into` | the figure over the children's `slot`, with `/scale`; `avg` rounds half up |
| `any`, `all` | `slot`, `into` | whether any / every child's `slot` is true |
| `where` | `key`, `value`, `op` (equals, over, under, before, after, contains) | the matching rows; a number slot compares by value at its scale (`136` at scale 2 is 1.36), anything else as text |
| `sort` | `slot`, `order` (asc, desc) | rows re-keyed 1, 2, 3, old key at `/key` (a name, or the path as text for a deeper row) |
| `top` | `slot`, `count` (default 3) | the largest, ranked; fewer rows than `count` gives fewer |
| `latest`, `earliest` | `slot` | the one child, as the root, key at `/key`; no row with a number there gives an empty root |
| `each` | `left`, `op`, `right`, `into` (all four) | a derived slot per child; sides are literals or the child's slots |
| `lookup` | `key`, `take`, `match` (default `key`), `into`, `from` (default `table`) and a secondary input named by `from` | brings `take` from the matching table row |
| `distinct` | `slot` | rows with `/value` and `/count` |
| `select` | `slots` (space separated) | only those slots, on root and children |
| `by` | `key`, `op` (count, sum, min, max, avg), `slot`, `into` | one row per group value |
| `grid` | `row`, `col`, `op`, `slot` | rows by `row`, a slot per `col` |
| `flatten` | | every record below the root as a direct child, keyed by its path with underscores (`a_x_deep`) |
| `merge` | secondary inputs | the input's children plus theirs |
| `except` | `from` (default `other`) naming a secondary input, `key` (optional) | the rows the other view does not have. A row's identity is its path, or with `key` its value there (a row without one is kept) |
| `intersect` | as `except` | the rows the other view also has (with `key`, a row without a value is dropped) |
| `diff` | as `except` | `/added/<row>`, `/removed/<row>`, `/changed/<row>` (each differing slot as `<slot>/from` and `<slot>/to`), counts on the root; with `key`, rows without a value are ignored and `changed` compares a row with the first row of the same value; every row counts. Against a `/h` reference of the same path it is the change since that case |
| `add`, `subtract`, `multiply`, `divide` | `left`, `right`, `into` | one figure on the root |
| `pick` | `from`, `into` | copies a slot (also `/views/...`) onto the root |
| `put` | `into`, `value` | sets a literal on the root |
| `round` | `slot`, `places`, `into` | rescales a root number |
| `since` | `slot`, `from`, `into` | `slot` minus `from` |
| `between` | `slot`, `from`, `to` | children within the range |
| `amend` | `notes` (default `notes`) and a secondary input of that name | the input with notes laid over it |

### Hand edits that survive recomputation

Keep overrides beside a cell, in a notes folder: each note is a record with
`/slot` (the answer slot it changes), `/value`, and `/case` (the input
data's case when the note was written: read the computed cell's `/c/x` and
copy `/sys/tack/case`). Make a cell with `amend`: its tack is the computed cell's
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
