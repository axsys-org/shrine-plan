# Shrine MCP: every knob

The first page (`SKILL.md`) is the form you use most. This page is the whole
shape of the three verbs plus `apply`. Nothing else exists: no session, no
subscribe, no mode flag.

## A read

A read is `"/path"` or `{path, care, case, formula, settings, limit, next,
present}`:

```
path      /user/org/deals      a record, a folder, /x/<cell> (a cell's answer), /c/x/<cell> (its context), /h/... (pinned)
care      x | y | z            x the record, y the record and its children (default), z the whole subtree
case      0                    0 live (default), or a case to read as of then
formula   where                run a standard cell over the tree read, settings as its context; nothing written
settings  {key: "/status", value: "closed"}
limit     100                  nodes per answer, in tap order (a node, then its children by name); never over 500
next      <cursor>             the next a previous page of this same read answered: continue after it
present   true                 answer as usual and push {shown: {path, care, case}} on the stream; nothing journaled
```

The answer is one tree: `{path, exists, reference, reference_y, reference_z,
properties, children, nodes, next}`. Every node carries its pinned x
reference; the root carries the y and z ones a tack pins. A node an earlier
page rendered that still has children comes back as a shell (`paged: true`,
path and children only). A value that is code or over 8 KB is `{type, size,
reference}`. A reply that would pass 2 MB is refused with "too large, page
it" before it is built. A folder with no record of its own is a fine input
(its children are the rows) but has no case to pin or stamp against: give it
a record.

```
read     reads [a read, ...]   one or many, one snapshot, zero events, answers in order, each the
                               shape a single read gives; a failed entry answers {path, error}
                               without failing the call. A single path still works: read path=...
```

## A write

```
write    records [{path, slots, action}, ...]   action make (default: the whole record, creating or
                                                 replacing it), poke (merge slots), cull (delete the subtree)
         from    /h/x/<case>/<len>/<path>        on a record: copy it as it was at that case (undo, redo)
         then    [a read, ...]                   reads answered on the admitted state, in the same reply
         who     <short id>                      the writer's tag, default mcp; the event carries it
         -> {epoch, records: [{path, written, reference}], refused, then: {...}}
```

One event, however many records; admitted whole or refused whole; a derived
path (`/x`, `/c/x`, `/h`) refuses the batch before any event. A culled path
refuses writes beneath it until the culled record is written again, so
delete-and-recreate is one batch (revive the folder with its children in
one event); history keeps every case on either side of the cull. An undo is
`from` an earlier case; redo is `from` the case after it.

## History

```
history  path     /user/org/deals/d1   a record's cases, newest first, with references and slots
         before   <epoch>              the event log before that epoch, newest first (next continues)
         after    <epoch>              the event log after that epoch, oldest first (next = the last epoch given)
         limit    40                   never over 200
         with     x | y                each event's written records inline, as they were at that epoch
                                       (a written cell's /x and /c/x too: the cell as it was then, over a live
                                       input as it is now; not ancestors, never the system folders)
         who      all | <id>           which writers: absent, every writer but system; all; one writer
         -> {events: [{epoch, who, touched, touched_count, with}], next}
```

A refused write or apply answers `refused: true` with `reason`: the kernel's
word for it (`warp_op_unknown`, `write_outside_authority`, a tombstone).

`who` on an event is its writer: the `who` the write carried (every MCP
write carries one), `system` for an untagged event that wrote nothing under
`/user` or `/agent` (boot, the filesystem sync, a mount's seeds), `world`
for an untagged write from another mount. By default history lists every
writer but system, so `history after 0` on a fresh world is empty and
cheap. `touched` lists the first hundred paths the event touched and
`touched_count` the number. `with` inlines at most 500 nodes and 256 KB of
records per event; past that the rest of that event's records are left
out, and a page of events stops before the reply ceiling. A presented read leaves no trace here: the
stream line is its only one.

## The stream

`GET <world-url>/mcp/stream` keeps the connection open as `text/event-stream`
and receives one line per admitted write, `{epoch, label, who, touched,
with}` (the written records rendered on the admitted snapshot, the same
page render `then` uses), and one per presented read, `{shown: {path, care,
case}}`. A commit never waits on a stream; a stream that stalls is dropped.
`hands/stream.py` follows it from Python and polls `history after … with x`
whenever the stream is not there, yielding the same lines either way; the
ask hand runs on that.

## Apply

```
apply    path, operation, inputs, then [a read, ...]     an op a record carries; cells never need it
```

## Numbers in slots

A slot number may be an integer of either sign or a decimal. A negative is
kept as a signed value and reads back as written (`-3`). A decimal is kept
as the natural at a scale, `4.5` as `45` with `<slot>/scale: 1`, and a slot
with its own scale reads back as the decimal (`4.5`); a record-level
`/scale` reads raw, as it always did. Every formula reads the sign and the
scale: `subtract` below zero gives a negative, `sum` and `min` keep signs,
`sort` and `top` rank by signed value. `{type: int, value: "-3"}` is the
exact form.

## Cells

A cell is a record that derives its value from other records. It has
three kinds of slots:

- `/sys/weft`: a reference to a standard cell under `/weft/stdlib` (read the
  standard cell first and use its `reference`).
- `/sys/tack`: a reference to the input at a care: `x` the record alone,
  `y` the record and its children, `z` the whole subtree (interior records
  included). Write it as `{type: reference, path, care, case}`; case 0 is
  live and makes the cell follow the input, a pinned case freezes it. The
  spelled form `/h/<care>/<case>/<len>/<path>` is what reads answer and is
  accepted too (`<len>` counts every segment after it, the `x` of another
  cell's answer included). A culled input faults the cell (`tack: the input
  was culled`); a live cell read at a pinned case reads unknown. A folder with no record of its own is a
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
| `each` | `left`, `op`, `right`, `into` (all four) | a derived slot per child, `/scale` on each row where the sides carried one; sides are literals or the child's slots |
| `lookup` | `key`, `take`, `match` (default `key`), `into`, `from` (default `table`) and a secondary input named by `from` | brings `take` from the matching table row |
| `distinct` | `slot` | one row per distinct value, keyed 1, 2, 3 in order of first appearance, each `/value` and `/count` |
| `select` | `slots` (space separated) | only those slots, on root and children |
| `by` | `key`, `op` (count, sum, min, max, avg), `slot`, `into` | one row per group value |
| `grid` | `row`, `col`, `op`, `slot` | rows by `row`, a slot per `col` |
| `flatten` | | every record below the root as a direct child, keyed by its path with underscores (`a_x_deep`) |
| `merge` | secondary inputs | the input's children plus theirs, one flat list |
| `gather` | secondary inputs | the input with each secondary input nested under its slot name (`/<slot>/...`): several cells' answers as one tree |
| `except` | `from` (default `other`) naming a secondary input, `key` (optional) | the rows the other view does not have. A row's identity is its path, or with `key` its value there (a row without one is kept) |
| `intersect` | as `except` | the rows the other view also has (with `key`, a row without a value is dropped) |
| `diff` | as `except` | `/added/<row>`, `/removed/<row>`, `/changed/<row>` (each differing slot as `<slot>/from` and `<slot>/to`; the two roots' slots as `/changed/root`), counts on the root; with `key`, rows without a value are ignored and `changed` compares a row with the first row of the same value; every row counts. Against a `/h` reference of the same path it is the change since that case |
| `add`, `subtract`, `multiply`, `divide` | `left`, `right`, `into` | one figure on the root |
| `pick` | `from`, `into` | copies a slot (also `/views/...`) onto the root |
| `put` | `into`, `value` | sets a literal on the root |
| `round` | `slot`, `places`, `into` | rescales a root number |
| `since` | `slot`, `from`, `into` | `slot` minus `from` |
| `between` | `slot`, `from`, `to` | children within the range |
| `amend` | `notes` (default `notes`) and a secondary input of that name | the input with notes laid over it |
| `join` | `slots` (space separated), `with` (default a space), `into` (default `/joined`) | each row gains `into`: its slots' texts joined by `with`; a row with none of the slots is left as it is |
| `match` | `key`, `value`, `op` (contains default, starts, ends) | the rows whose `key` text contains, starts with or ends with `value` |
| `split` | `slot`, `with` (default a space), `into` (default `slot`) | each row gains `into/1`, `into/2`, … , the slot's text cut at `with` |
| `date` | `slot`, `into` (default `/day`) | each row gains `into`: the text date `YYYY-MM-DD` (anything after the day ignored) as the natural `YYYYMMDD`, which `sort`, `between`, `latest` and `since` can use |
| `ask` | `prompt`, `model` (default the hand's) | the stored answer at `<cell>/result` while its stamp (input case, model, prompt) is current; else empty, with `/sys/view/asking` in the context |

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
