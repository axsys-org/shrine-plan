---
name: shrine-mcp
description: >-
  Operate a Shrine world through its MCP mount: read and write typed records, make cells that derive values from other records, and read history.
---

# Shrine MCP

The world serves `<world-url>/mcp` on localhost only, with no credential:
anything on the machine can read and write the world (booting one and
connecting is `SETUP.md` beside this skill). Three verbs; this page shows
the one form of each you will use most. Every knob is on the
second page, `knobs.md`, read it when you need one (`apply` is there too).
The shape is frozen: a new knob needs a measured round trip it removes.

```
read     path       /user/org/deals            a record, a folder, /x/<cell>, /c/x/<cell>
         -> the tree: root slots, children (each with its pinned reference), nodes, next

write    records    [{path, slots}, ...]       one or many: one event, admitted whole or refused whole
         -> epoch, each record's reference; or the refusal and nothing written

history  after      <epoch>                    every event since then, oldest first
         with       x                          each event's written records inline, as of that epoch
         -> events [{epoch, who, touched, with}], next
```

One example each:

```
read     path=/user/org/deals
write    records=[{path: /user/org/deals/d4, slots: {amount: 120, status: "open"}}]
history  after=312 with=x
```

A read never costs an event; a write costs exactly one, however many
records it carries. A slot value is text, a number or a boolean. A number
may be negative or a decimal: `-3` is kept signed, `4.5` is kept as `45`
with `rating/scale: 1` and reads back as `4.5`; formulas add, compare and
rank by the signed value. `{type, value}` makes an exact `nat`, `int`,
`str`, `bool` or `path`; a reference
to another record is `{type: reference, path, care, case}` (care x, y or z,
case 0 for live). A path segment is letters, digits and underscore: `c-7`
is `c_7`, keep the original as a slot. An answer is at most 500 nodes;
`next` continues it. A value that is code or over 8 KB comes back as
`{type, size, reference}`, never inline.

## Thinking in the world

- Pick a name and write with `who: <name>` every time; history filters by
  it and the page shows it on every event.
- Plan first as a record under `/agent/<name>/plan`: the question and the
  steps, so the plan has a case and a history.
- Try a question with a formula read before keeping it: `read path
  formula settings` runs any standard cell over a folder and writes
  nothing; it answers `{path, formula, result, context}`, the result the
  tree the cell would give; change the settings until it is right.
- Keep what is right as a cell: the same formula and settings written at a
  path (`/sys/weft` the formula's reference, `/sys/tack` the input's). From
  then on `/x/<path>` is the answer, live, and a cell over it composes.
  Keep cells beside the data, never inside the folder they read: a cell
  under its own input is a cycle and reads unknown.
- Scratch under `/agent/<name>/scratch` as one batch, culled as one batch
  at the end; `then` shows the effect in the same call; `from` an earlier
  case changes your mind.
- When stopping, write `/agent/<name>/seen {epoch}`; wake with `history
  after <epoch> with x` and continue from what changed. A world lives as
  long as its process: after a reboot it is a new world, so keep what you
  would not want to retype as one `records` batch you can write again.
- Ask the world instead of reasoning over a copy; page what is left; never
  read the world whole.
- The live page is how the person sees your work. Open
  `<world-url>/live?views=<folder>` in their browser when you start and
  again whenever the folder you work in changes, closing the tab you opened
  before so there is one page and it is the right one. After a world reboot
  open it again, the old tab is stale. If you cannot open a browser, give
  the link in your reply every time it changes, as a line on its own, so it
  is always one click away.

What is not a formula is an `ask` (on the second page): a cell a model
answers, stamped with the input's case. "QA mode on" means the third page,
`qa.md`: expectations as records, checks as diff cells, a score, written
before you read.

