---
name: shrine-mcp
description: >-
  Operate a Shrine world through its MCP mount: read and write typed records, make cells that derive values from other records, and read history.
---

# Shrine MCP

The world serves `<world-url>/mcp` on localhost only, with no credential:
anything on the machine can read and write the world. Three verbs; this
page shows the one form of each you will use most. Every knob is on the
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
records it carries. A slot value is text, a number or a boolean; `{type,
value}` makes an exact `nat`, `str`, `bool`, `path` or `reference` (a
reference is `/h/<care>/<case>/<len>/<path>`; case 0 is live). An answer is
at most 500 nodes; `next` continues it. A value that is code or over 8 KB
comes back as `{type, size, reference}`, never inline.

## Thinking in the world

- Plan first as a record under `/agent/<name>/plan`: the question and the
  steps, so the plan has a case and a history.
- Try a question with a formula read before keeping it: `read path
  formula settings` runs any standard cell over a folder and writes
  nothing; change the settings until the answer is right.
- Keep what is right as a cell: the same formula and settings written at a
  path (`/sys/weft` the formula's reference, `/sys/tack` the input's). From
  then on `/x/<path>` is the answer, live, and a cell over it composes.
- Scratch under `/agent/<name>/scratch` as one batch, culled as one batch
  at the end; `then` shows the effect in the same call; `from` an earlier
  case changes your mind.
- When stopping, write `/agent/<name>/seen {epoch}`; wake with `history
  after <epoch> with x` and continue from what changed.
- Ask the world instead of reasoning over a copy; page what is left; never
  read the world whole.
- When you connect, open `<world-url>/live?views=<the folder you work in>`
  in the person's browser once; if you cannot, give them the link.

What is not a formula is an `ask` (on the second page): a cell a model
answers, stamped with the input's case.

