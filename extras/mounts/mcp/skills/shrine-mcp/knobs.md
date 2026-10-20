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
find      acme                 the records under path whose name or any slot's text contains it, in tap order,
                               limit of them visited at a time, each with the slot that matched; next continues
referencing  /user/org/deals  the records under path whose reference slots point at that path or beneath it, in tap
                               order, limit visited at a time: each with the slot, the target, cell (it is a cell) and hole
                               (a cell waiting there: the target absent, an ask unanswered, a hole, a fault); next continues;
                               plus watchers, the reactive records whose crews depend on it, from the kernel's crew index
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

## Write only if unchanged

A record in a write may carry `if_case`, the x case the writer read
(`read` answers it in `reference`, `/h/x/<case>/...`). The precondition
rides into the kernel with the writ and is judged in the same commit:
the batch is admitted only while every such record is still at that
case, else it is refused whole, nothing written, and `reason` names the
record and the case it is at now (`if_case: /0x11/user/org/d1 is at
case 4, not 3; nothing was written`). Two agents on one record cannot
lose each other's work: read, write with the case, and on a refusal
read again.

## Hands

A hand is a process beside the world (`extras/mounts/mcp/hands`, with
`hands.md` there). A world runs the hands its `world.json` names, and no
others; the launcher's `Eden:` line lists them. Config is a record at
`/agent/hands/<name>`, changed with a write; where a hand left off is
`/agent/hands/<name>/seen`.

| hand | what runs | how to tell it is not running |
|---|---|---|
| `clock` | writes `/clock {day, timezone}` once a day | `/clock` is behind |
| `watch` | posts to a URL when a watched cell's answer changes (`cells`, `url`) | the value at `/agent/hands/watch/<cell>` is stale |
| `export` | a request record under `/agent/hands/export/` `{folder, format, path}` becomes a file | the request has no `done` |
| `import` | `/agent/hands/import/<source>` `{kind, source, folder, key, every}` plus `/map` and `/refs/<slot>`; writes `who: import:<source>` | `ran` on the config does not move |
| `ask` | answers `ask` cells with a model | `/c/x/<cell>` keeps saying asking |

A line from a hand, or one whose touched paths all sit under `/agent/hands`,
never makes another hand write: an agent reading history can filter them
out the same way (`who` is the hand's name).

## Apply

```
apply    path, operation, inputs, then [a read, ...]     an op a record carries; cells never need it
```

## Values

A slot value is text, a number or a boolean. A number
may be negative or a decimal: `-3` is kept signed, `4.5` is kept as `45`
with `rating/scale: 1` and reads back as `4.5`; formulas add, compare and
rank by the signed value. `{type, value}` makes an exact `nat`, `int`,
`str`, `bool` or `path`; a reference
to another record is `{type: reference, path, care, case}` (care x, y or z,
case 0 for live). A path segment is letters, digits and underscore: `c-7`
is `c_7`, keep the original as a slot. An answer is at most 500 nodes;
`next` continues it. A value that is code or over 8 KB comes back as
`{type, size, reference}`, never inline.

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
there is no text ordering. A slot holding a reference reads as its `/h`
spelling wherever a formula wants text.

Three conventions hold in every formula:

- The rows of an input are every record below its root at the tack's care:
  a `y` input's children, a `z` input's whole subtree, interior records
  included. Reducers (`count`, `sum`, ...) fold over all of them; row
  formulas (`where`, `sort`, `by`, ...) keep each row at its own path, so
  a `z` result keeps the folder structure.
- A child's name is addressable as a slot called `name` in any setting
  (`where key=/name value=beta`, `select slots=/name`, `by key=/name`,
  `lookup key=/name`); a record that carries its own `/name` slot wins.
- A formula sees only its inputs. A reference held in a row's slot is data
  to it until a secondary input holds the folder it points into: then
  `follow` brings the referenced record onto the row (the native join, at
  that input's case), and `lookup` is for matching keys when the data has
  no references yet (`reference` makes them once).

Two worked examples of composition. A chain: cell b reads cell a's answer
live, and carries its own settings:

```
write /user/org/views/closed     sys/weft {type: reference, value: <reference of /weft/stdlib/where>}
                                 sys/tack {type: reference, path: /0x11/user/org/deals, care: y, case: 0}
                                 key /status   value closed
write /user/org/views/revenue    sys/weft {type: reference, value: <reference of /weft/stdlib/sum>}
                                 sys/tack {type: reference, path: /x/0x11/user/org/views/closed, care: y, case: 0}
                                 slot /amount   into /revenue
read /x/user/org/views/revenue   ->  /revenue: 75, live: a deal closing moves it
```

A secondary input: any other slot holding a reference is a view the formula
reaches by that slot's name:

```
write /user/org/views/priced     sys/weft {type: reference, value: <reference of /weft/stdlib/lookup>}
                                 sys/tack {type: reference, path: /0x11/user/org/items, care: y, case: 0}
                                 table {type: reference, path: /0x11/user/org/prices, care: y, case: 0}
                                 key /sku   take /price
read /x/user/org/views/priced    ->  each item row gains /price from the price row with the same /sku
                                     (gather with the same slot nests the view whole under /table instead)
```

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
their output root; `round` rescales to `/places`. A number a row formula
derives (`running`, `change`, `moving`, `percent`) carries its own
`<slot>/scale`, so the row's other numbers keep theirs. Dates and durations are
numbers in their own unit and compare as such; a day is the number
`YYYYMMDD` that `date` makes and `part` and `shift` read.

### The standard cells

| formula | parameters | result |
|---|---|---|
| `count` | `into` (default `/count`) | number of children |
| `sum`, `min`, `max`, `avg` | `slot`, `into` | the figure over the children's `slot`, with `/scale`; `avg` rounds half up |
| `any`, `all` | `slot`, `into` | whether any / every child's `slot` is true |
| `where` | `key`, `value`, `op` (equals, over, under, before, after, contains); or `expr` | the matching rows; a number slot compares by value at its scale (`136` at scale 2 is 1.36), anything else as text |
| `sort` | `slot` (one, or two space separated: the second breaks ties), `order` (asc, desc) | rows re-keyed 1, 2, 3, old key at `/key` (a name, or the path as text for a deeper row) |
| `top` | `slot`, `count` (default 3) | the largest, ranked; fewer rows than `count` gives fewer |
| `latest`, `earliest` | `slot` | the one child, as the root, key at `/key`; no row with a number there gives an empty root |
| `each` | `left`, `op`, `right`, `into` (all four); or `expr`, `into` | a derived slot per child, `/scale` on each row where the sides carried one; sides are literals or the child's slots |
| `lookup` | `key`, `take`, `match` (default `key`), `into`, `from` (default `table`) and a secondary input named by `from` | brings `take` from the matching table row |
| `distinct` | `slot` | one row per distinct value, keyed 1, 2, 3 in order of first appearance, each `/value` and `/count`; the root gains `/count`: how many |
| `select` | `slots` (space separated) | only those slots, on root and children |
| `by` | `key` (one slot, or two space separated: the values joined by an underscore), `op` (count, sum, min, max, avg), `slot`, `into` | one row per group value |
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
| `when` | `key`, `op` (as `where`), `value`, or `expr`; `then`, `else` (optional), `into` | each row gains `into`: `then` when its `key` matches, else `else`; without `else` a row that does not match is left as it is |
| `coalesce` | `slot`, `value`, `into` (default `slot`) | each row gains `into`: its `slot` when present, else `value` |
| `part` | `slot` (a day number `YYYYMMDD` or a text date), `unit` (year, quarter, month, week, weekday), `into` (default `/<unit>`) | each row gains `into`: that part of its day; week counts sevens from January 1st, weekday is 1 Monday to 7 Sunday |
| `shift` | `slot`, `by` (a whole number, signed), `unit` (day default, week, month, year), `into` (default `slot`) | each row gains `into`: its day moved; a month or year move keeps the day, clamped to the month |
| `running` | `slot`, `into` (default `/running`) | each row with `slot` gains `into`: the total so far, in row order (`sort` first) |
| `rank` | `into` (default `/rank`) | each row gains `into`: its position, 1, 2, 3 |
| `change` | `slot`, `into` (default `/change`) | each row with `slot` gains `into`: `slot` minus the previous such row's; the first has none |
| `moving` | `slot`, `window` (default 3), `into` (default `/moving`) | each row with `slot` gains `into`: the mean over the last `window` such rows, half up |
| `percent` | `slot`, `into` (default `/percent`) | each row with `slot` gains `into`: its share of the rows' total, as `34.48` |
| `trim`, `case`, `replace` | `slot`, `into` (default `slot`); `case` takes `to` (lower, upper); `replace` takes `find`, `with` (default nothing) | each row's `slot` text stripped of surrounding whitespace, re-cased (ASCII), or with every `find` replaced |
| `length` | `slot`, `into` (default `/length`) | each row gains `into`: the byte length of its `slot` text |
| `starts`, `ends` | `slot`, `value`, `into` (default `/starts`, `/ends`) | each row gains `into`: whether its `slot` text starts or ends with `value` (`match` filters; these derive) |
| `follow` | `slot` (holding a reference), `into` (default `slot`), `from` (optional) and a secondary input holding the folder the references point into | each row gains, under `into`, the slots of the record its reference points at, found in the secondary input whose root the reference lies under (`from` names one), read at that input's case |
| `reference` | `key`, `match` (default `key`), `from` (default `table`) and a secondary input of that name, `into` | each row gains `into`: a live reference to the first table row whose `match` equals its `key`; the one-time step after an import that turns keys into pointers, kept with a write |
| `median`, `percentile`, `variance`, `stddev` | `slot`, `into` (default `/<name>`); `percentile` takes `at` (0 to 100, default 50) | one figure on the root at the rows' scale: the middle value (the mean of the two middles, half up), the value at the `at`th percentile (nearest rank), the population variance, the population standard deviation (half up) |
| `mode` | `slot`, `into` (default `/mode`) | the most frequent value of `slot` on the root (the first on a tie) |
| `group` | `key` | one folder per value of `key`, the rows under it at their own paths |
| `rename` | `from`, `to` | the slot `from` called `to` on the root and every row, its scale with it |
| `drop` | `slots` (space separated) | the root and every row without those slots: the inverse of `select` |
| `unflatten` | | a child named with underscores lands at the path they spell: the inverse of `flatten` |
| `explode` | `slot`, `with` (default a space) | the pieces of the row's `slot` text as rows `1`, `2`, `3` under the row's name, each the row with its piece at `slot` |
| `validate` | `key`, `op` (as `where`, or `present`), `value`, or `expr`; `reason` (optional) | the rows that break the rule, each with `/reason`: `reason`, else the rule in words (`/amount is not over 40`, `/amount is absent`) |
| `unique` | `key` | the rows whose `key` value another row shares, each with `/count` |

### Expressions

`each`, `when`, `where` and `validate` take `expr` instead of their settings:
a text, parsed once per read and evaluated per row with the row's slots as
the only variables. `each` writes the value at `into` (a number with its own
scale, a text or a boolean); `where` keeps the rows where it is true; `when`
writes `then` or `else` by it; `validate` keeps the rows where it is false,
the expression as the reason unless `reason` is given.

```
amount * 2 + 1                       slot names, whole and decimal numbers, signed; + - * /
status = 'closed' and amount > 30    = != < <= > >=, and or not, in (text inside text), parens
round(amount / 3, 1)                 min max abs round len lower upper trim contains starts ends
```

Usual precedence (`or` below `and` below `not` below comparisons below `+ -`
below `* /` below unary minus). A product or quotient is rounded half up at
the larger of its operands' scales (`50 / 3` is 17; write `50.0 / 3` for
16.7). A slot the row lacks is a hole on that row, noted at
`/sys/view/hole/<row>` in the context: `where` drops the row, `each` and
`when` leave it, `validate` fails it. A bad expression is one fault with
its position; division by zero and a number against a text in arithmetic
fault, naming the row; `expr` beside the old settings faults. A formula
read takes `expr` in its settings like any other.

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
