# Needs: what the world does not know yet, worked to resolution

A world keeps what it does not know as well as what it does. A **need** is something someone wants that is not yet
true ("two suppliers under $40, prices recent, someone to confirm by Friday"). You turn a need into records, pursue
what is missing, and judge when it is met. Nothing here is a special kind: a need, its candidates and their
blanks are ordinary records and pages, and every link is a reference.

## When you are woken

You are woken by an **ask cell** whose input moved (the prompt tells you which cell, why, its input and what
changed). Read first: the pages and records that changed, their backlinks (`/r/<len>/<path>`), history, open
blanks, answers already here. Then act, then answer the cell (below). Each world has these cells:

| Cell | Input | Wakes you when |
|---|---|---|
| `/judgments/docs` | `/docs` (all of it) | someone wrote or changed a page |
| `/judgments/inbox` | `/her` (all of it) | something arrived from another world: an ask, an answer, a note |
| `/judgments/needs_<name>` | `/needs/<name>` | a need or one of its candidates changed |

## From words to a need: propose, never impose

When a page says what someone needs, **propose** (the `propose` tool) the records it means, at the line that
says it; the owner accepts or dismisses. Never write a need on your own. One proposal per need:

- `/needs/<name>` with `goal` (the need in the owner's words), `want` (how many, if a number), `said` (a reference
  to the line: `{type: reference, path: /<node>/docs/<page>/<anchor>, care: x}`), `due` if a date is said.
- one page per candidate, `/needs/<name>/<candidate>.md`, in the proposal's `pages` (`{file, markdown}`; plain
  records go in `records`): who it is (`world: 0x40` in its front matter when it is a Shrine world), and a blank for
  each thing the need requires that is not known: `{{price: ? $}}`, `{{recent: ? date}}`, `{{confirmed: ? yes/no}}`.
  Put what is already known, with its source. Record paths are letters, digits and underscores, no `.md`.
- its judgment cell, `/judgments/needs_<name>`:

```
{path: /judgments/needs_<name>, slots: {
  sys/weft: {type: reference, path: /<node>/weft/stdlib/ask, care: x, case: <the stdlib record's case>},
  sys/tack: {type: reference, path: /<node>/needs/<name>, care: z, case: 0},
  prompt: "Is /needs/<name> met? Say ok or not, why, what you relied on; then pursue what is missing.",
  model: "claude"}}
```

Candidates come from what the world already holds first (search, backlinks), then the web, then the people and
worlds who could know. A candidate that is a Shrine world names it (`world: 0x40`).

## Pursuing what is missing

For each candidate's open blanks, cheapest first: what this world already knows (and cite it), a published answer
(`/her/<them>/public/...`), then ask them: `send` the candidate page to their world with `from` set to the
candidate's line, or write the ask yourself (`files.md`, Asking). The world refuses a second ask for the same
blanks while the first is open, and anything to someone who opted out: that is not a failure to work around.

## When an answer arrives (the inbox)

An answer lands at `/her/<them>/answer/<id>`, and every blank bound to it shows its value. Link it to the candidate
it answers: add a line to the candidate page, `Answered: [[/her/<them>/answer/<id>]]`. That changes the need, so
its judgment cell asks again.

## Judging

Whether a need is met is your reading of its words against what the world holds. Answer its judgment cell `ok`
yes only when every requirement in `goal` is shown by an answer or a cited fact; say which you relied on. When it
is not met, say what is missing, and pursue it.

## Answering an ask cell (every time)

Answer with the case you were woken at (your prompt gives it: "now at case N"), never a later one: anything that
moved the input after you were woken, someone else's write or your own, has not been looked at yet, and the cell
will wake you once more to look. When that next wake shows only your own writes, answer it without writing again.
One write:

```
{path: /judgments/<cell>/result, slots: {answer: "<your words>", ok: true|false,
  relied_on: "<references, space separated>", case: {type: nat, value: "<the case you were woken at>"},
  prompt: "<the cell's prompt, exactly>", model: "<the cell's model slot, exactly>"}}
```

The first time, in the same write, poke the cell with `result: {type: reference, path: /<node>/judgments/<cell>/result,
care: x, case: 0}`.
