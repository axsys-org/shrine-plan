---
name: shrine-mcp
description: >-
  Keep the person's records, lists, plans, numbers and notes in their world, and answer questions about them from there. Use it whenever the work is data or state: a tracker, a budget, a pipeline, a roster, a log, a decision, anything to remember across sessions, any question whose answer should stay current, anything to show someone. Start every session by reading your plan and what changed since you last looked; keep what matters as records, keep answers worth keeping as cells. Not for one-off code questions or text nobody needs again.
---

# Shrine MCP

## Reach for it

The world is where the person's things live, and where your memory
lives. Default to it:

- Something they track, count or compare belongs in the world: a
  folder. Answer from existing records and views first, try a new
  computation as a read, and keep only what is worth reusing as a cell.
- Someone says a fact they will want back: a record, now, at a path they
  would guess.
- You find something out about their data: a cell or a reference that
  keeps answering, never a sentence copied into a slot.
- You answer a question about their data: read the world, not your
  memory of it.
- A session starts: read `/agent/<name>/plan` and `history after seen`
  before anything else, and say where things stand.
- The world does not answer: run `x/setup` from the checkout, a kept
  world resumes in seconds; continue from `seen`, reopen the live page,
  and say you did.

Say "kept it" when you keep something, and give the live page link once.
Never name the tools or the formulas to the person unless they ask how.

## What you leave behind

The namespace is not your transcript, scratchpad or progress report. It
is the persistent computational state of the world, and its history
keeps everything forever.

Read and compute without writing whenever you can. When you write,
prefer primary facts, references to existing records, and executable
views over copied results or descriptions. Do not persist a plan merely
because you formulated one, a status merely because you completed a
step, or an answer merely because someone asked for it. Persist
something only when future work benefits from its continued existence.
Keep operational state (`seen`, scratch) only where the protocol needs
it, under your own folder, apart from the person's data.

| what it is | what to do with it |
|---|---|
| a primary fact, a durable decision, an expectation | a record, at its authoritative path |
| a reusable computation or relationship | a cell, or a reference slot, never the number it gives |
| reasoning, exploration, coordination, confirmation | nothing, unless recovery or audit needs it |

The unit of accomplishment is not "I did it, here is a record saying
so." It is: the world can now answer, do or maintain something it could
not before. That may be a cell, a reference, a source brought in, an
authoritative fact corrected, or no write at all. A wake that only
verifies a number the world already answers leaves zero new domain
records; the cursor the protocol requires (`seen`) is exempt, and
skipping it is not hygiene, it is losing your place. At the
end of a task ask what another agent can now compute, inspect or reuse
that it could not before; if the answer is nothing, you wrote too much.

The order of operations: discover before creating (find the thing, the
view, the source that already exists); bind before copying (reference
it, do not reproduce its name, value or summary); compose before
duplicating (a cell's answer is an input to the next cell; reuse the
chain where its meaning and scope fit); resolve authority before
mutating (which source does the change concern); keep live dependencies
before concluding (a view or a reference over a recorded result; pin a
case only when the work must reproduce a past reading). Never invent a
fact to close a hole: fill down into data you own when the computation
needs it, point outward to a record or view that already answers, and
otherwise leave the hole, which is the honest state of the computation.

Text is the devil in this system unless it is metadata: a `notes` or a
`description` slot for a person or a search to find, a legal name, a
decision someone made, a source document. Text pretending to be state
is slop: a `status`, a `result`, a `calculation`, a sentence saying a
number was verified. Observing something true is not a reason to write
it. A check that was written as prose:

```
/checks/revenue   actual_revenue: 21   expected_revenue: 21   passed: true
                  calculation: "8 + 13 = 21"   status: "verified"
```

depends on nothing and goes stale the moment a deal moves. The same
check, alive:

```
/checks/revenue   actual: ref /views/revenue
                  expected: ref /expectation/revenue
                  passed: a diff cell over the two
                  notes: "revenue against the expectation"
```

The expectation stays a literal at its authoritative source; `passed`
is computed; when the deals change, the answer changes. A receipt of
what a check said once is a different thing: pin the cases it read, do
not copy its numbers. When text identifies another thing the computation
depends on, prefer a reference or an unresolved binding over copying its
name: `customer: "Northwind"` on a deal is weak, a reference to the
customer's record or to an exposed view of it is better, and a hole at
the path where it will be keeps the computation hungry for what it
needs. A literal that describes a thing at its own record stays text:
`legal_name: "Northwind Industries LLC"` on the customer is an
authoritative fact, not a pronoun. Build relationships and derivations,
filling down into your namespace or pointing outward to an existing
view; the aim is not zero literals, it is that the namespace accumulates
reusable computation rather than textual claims about work done.

### Slots

A record's slots are the thing's own facts: a number as a number, a
date as a date, a quotation in the source's words, another thing as a
reference. Four slots is normal, eight is a lot, and a slot longer than
a line is not a fact. One vocabulary per folder, chosen once: every row
of `deals` has the same `amount` and `status`, so a cell can read them;
a name invented for one record (`date_range_as_pleaded` beside
`date_range_as_published`, `year_start` beside `year_end`) is a sign
the thing was not understood yet. Pick the plainest word and reuse it.

Commentary is not a slot. What you think about a thing, its
`interpretation`, `assessment`, `scope_note`, `reporting_chain`,
`epistemic_status`, `inspection`, belongs in the chat, or in one
`notes` slot of metadata, or, if it must survive, in one note record in
your own folder that references the thing. A word that means absence
(`not assessed`, `open`, `pending`) is not a fact either: an unanswered
question is a cell with a hole, and the context says so. A status is a
fact only when the source says it, in a small vocabulary the folder
shares (`alleged`, `found`), never a sentence.

Views compute; they do not narrate. A cell that carries a `title` and
an `interpretation` is a document pretending to be a computation. If
the person asks for a reading of the evidence, that is a text for the
chat, or at most one record under your folder with one text slot and
references to what it reads from, and the page's job to lay out, not a
tree of lettered sections. The test, before writing any slot: would a
cell want to read this, or would only a person want to read it? The
first is a slot; the second is a note or nothing.

### One object, many scopes

A thing mentioned in more than one place, or with facts of its own,
gets one record at one path (`/user/people/jane`,
`/user/customers/northwind`); that path is its identity, and every
other mention is a reference to it. A thing mentioned once with nothing
of its own stays a literal; make the shared object at the second
mention or the first fact, not before. Imported names become pointers
once with `reference`; `find` locates the object you suspect exists
before you make a second one; a move is a new path and a `moved_to`
reference on the old record, never a cull. Bind a mention to an object
only when the evidence says it is the same thing; two names that look
alike are not evidence, and a wrong merge corrupts unrelated facts.
When identity is not established, keep the observed name as source
evidence and leave the relationship unresolved.

The shared object holds only what is true of the thing everywhere. What
is true of it within a scope lives as a record in that scope's folder
pointing at the object: `/user/org/acme/people/jane {person: ref
/user/people/jane, role: lead, rate: 120}`. So changing Jane in respect
to the org changes the org's record; removing her from the org culls
the org's record; the shared object changes only for a fact true of her
everywhere. Editing the object to fix one scope's view is a write in
the wrong place. A computed answer is never edited: if a view says
three projects and the person wants two, the change is to a
relationship at its source, never `count: 2` poked into the view; when
the edit is ambiguous, find which source fact must change before
writing anything. A reference grants no right to change what it points
at.

Views cross the boundary, data does not: a view over the scope uses
`follow` to bring the object's slots onto the row at read time, and
`gather` puts several scopes' answers in one tree; nothing is copied. A
scope that disagrees with a computed answer keeps a note beside the
cell, laid over by `amend` and stamped with the input's case, and never
edits the answer or the source. Culling a scoped record removes the
thing from that scope and nothing else; culling the object faults every
cell that read it, so read what points at a thing before retiring it:
`read path=<folder> referencing=<thing>` lists the cells and rows under
the folder whose references point at it, each with its slot and whether
a cell is waiting there (the page shows the same under an open record). Pin where you
cite, point live where you depend. Every question is then a read over
structure, nothing is said twice, nothing drifts, and the history is
of facts and decisions, not activity. A live view is not free: a chain
recomputes on read, so reuse what consolidates a computation many would
repeat, not views for their own sake, and measure a slow chain before
inventing a cache for it.

The world serves `<world-url>/mcp` on localhost only, with no credential
(booting one is `SETUP.md` beside this skill). Three verbs; this page is
the contract and the one form of each verb you use most. Every knob,
every standard cell and every value rule is on the second page,
`knobs.md`: read it when you need one, never from memory.

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
records it carries. What a slot may hold, how numbers, references and
path segments are spelled, and how big an answer gets are on the second
page under Values.

## Thinking in the world

- Pick a name and write with `who: <name>` every time; history filters by
  it and the page shows it on every event.
- A plan is a record under `/agent/<name>/plan` only when the work
  outlives this session: the question and the steps, replaced as they
  change, culled when done. Never a status, a result or a summary of what
  you did; the journal already has that.
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
  after <epoch> with x` and continue from what changed. Which kind of
  world you are in is a record: `read path=/agent/launcher/world` answers
  `kept: true` with its directory for a world that survives reboots, and
  `kept: false` for a temporary one that is gone with its process. In a
  temporary world keep what you would not want to retype as one `records`
  batch; in a kept one, nothing is lost and `seen` is where you left it.
- Chains first: a question is usually two or three standard cells over
  each other. `expr` (`each`, `when`, `where`, `validate`) is for a rule a
  chain cannot say: `amount * 2 + 1`, `status = 'closed' and amount > 30`,
  the row's slots as the only variables.
- An expectation is a record at its source, written before the read that
  checks it; a check is a cell comparing the live answer to it, not a
  copied number with "passed" beside it. A reading that comes first is a
  description, not a check.
- Ask the world instead of reasoning over a copy; page what is left; never
  read the world whole. To find a record you do not know the folder of,
  `read path=/user find=<text>`: the records whose name or a slot holds it.
- Name folders for keeps: a path is what every reference and every cell
  points at. To move something, make the new path and point the old record
  at it (a `moved_to` reference slot), rather than culling it.
- The live page is how the person sees your work. Open
  `<world-url>/live?views=<folder>` in their browser when you start and
  again whenever the folder you work in changes, closing the tab you opened
  before so there is one page and it is the right one. After a world reboot
  open it again, the old tab is stale (a kept world has the same records
  and URL; a temporary one starts over). If you cannot open a browser, give
  the link in your reply every time it changes, as a line on its own, so it
  is always one click away.
- The person can click any path or reference on the page. A click writes
  `/agent/person/cursor {path}` signed `person`, a line on the stream like
  any other. When it moves, read it, open the page at that folder, and
  work there until they click again or say otherwise.

## Working with others

Nobody converses through the namespace. Another agent's work is cells
and records you read and point at, never notes you exchange: no inbox,
no acknowledgements, no copied answers. Do not ask another agent for
what the world can compute; a count, a sum, the oldest of a folder is a
cell you write. A step for another agent is a line in their plan with
`if_case` set to the plan's case, and nothing else goes in another
agent's folder. `if_case` is judged by the kernel in the same commit
as the write, so a stale write is refused, never raced. Sign everything with your `who`, and read `history`
before you act on what you remember; never assume a session is the only
one.

What is not a formula is an `ask` (on the second page): a cell a model
answers, stamped with the input's case. "QA mode on" means the third page,
`qa.md`: expectations as records, checks as diff cells, a score, written
before you read.

